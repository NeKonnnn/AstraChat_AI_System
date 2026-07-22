"""
socket_handlers.py - все @sio.event обработчики Socket.IO
Регистрируется в main.py:
    from backend.socket_handlers import register_handlers
    register_handlers(sio)
"""

import asyncio
import concurrent.futures
import contextvars
from datetime import datetime
from typing import Any, Dict, Optional


from backend.settings.rag_client import RagReindexInProgress
import backend.app_state as state
from backend.app_state import (
    ask_agent,
    context_prompt_manager,
    get_agent_orchestrator,
    get_current_model_path,
    get_model_comparison_models,
    get_rag_chat_top_k,
    get_recent_dialog_history,
    rag_client,
    save_dialog_entry,
    stop_generation_flags,
    stop_transcription_flags,
)
from backend.database.memory_service import save_assistant_response
from backend.auth.jwt_handler import decode_token, decode_token_signature_only
from backend.llm_providers import split_model_path
from backend.rag_query.post_generation import maybe_replace_ungrounded
from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE, merge_strict_rag_system_prompt
from backend.realtime.helpers import (
    _is_structure_query,
    _resolve_agent_chat_params,
    _terminal_chat_inference_banner,
    kb_search_agent_documents,
)
from backend.services.user_feedback_context import (
    build_user_feedback_system_block,
    merge_feedback_into_system_prompt,
)
from backend.services.user_llm_settings import (
    enrich_agent_profile_with_user_settings,
    get_user_prompt_manager,
)
from backend.services.user_rag_settings import (
    bind_user_rag_runtime,
    get_user_rag_settings,
    reset_user_rag_runtime,
    runtime_agentic_max_iterations,
    runtime_agentic_rag_enabled,
    runtime_rag_strategy,
    runtime_rag_system_prompt,
)
from backend.realtime.rag_evidence import (
    build_rag_id_to_filename,
    filter_rag_hits_by_score,
    format_rag_fragments,
    maybe_rag_no_evidence_message,
    rag_guard_env,
    rag_reindex_blocks_active_sources,
    resolve_active_rag_sources,
)
from backend.settings.cef_logger.cef_audit_context import cef_socket_remote_from_environ
from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress
from backend.mcp.resolvers import resolve_chat_tool_ids

logger = get_logger(__name__)


def _get_set_tool_context():
    try:
        from backend.tools.prompt_tools import set_tool_context
    except ModuleNotFoundError:
        try:
            from tools.prompt_tools import set_tool_context
        except ModuleNotFoundError:
            from backend.tools.tool_context import set_tool_context
    return set_tool_context

async def _notify_reindex_wait(sio, sid) -> None:
    """UI-уведомление: база переиндексируется, поиск временно без документов."""
    try:
        await sio.emit(
            "chat_info",
            {
                "message": (
                    "База документов переиндексируется — поиск временно "
                    "недоступен, ответ будет без источников. Повторите вопрос "
                    "через пару минут."
                )
            },
            room=sid,
        )
    except Exception:
        logger.exception("notify reindex")

REINDEX_WAIT_MESSAGE = (
    "База документов сейчас переиндексируется - поиск по документам "
    "временно недоступен. Повторите вопрос через пару минут."
)

async def _abort_chat_reindex(
    sio, sid, conversation_id, project_id, current_user
) -> None:
    """Вместо генерации без контекста - штатный ответ «подождите» + сохранение."""
    stop_generation_flags[sid] = False
    await sio.emit(
        "chat_complete",
        {
            "response": REINDEX_WAIT_MESSAGE,
            "timestamp": datetime.now().isoformat(),
            "was_streaming": False,
        },
        room=sid,
    )
    try:
        await save_assistant_response(
            REINDEX_WAIT_MESSAGE,
            {"reindex_wait": True},
            conversation_id=conversation_id,
            user_id=(current_user or {}).get("user_id"),
            project_id=project_id,
        )
    except Exception:
        logger.exception("Сохранение reindex-wait ответа")

async def _abort_multi_llm_reindex(
    sio, sid, multi_llm_models, conversation_id, project_id, current_user
) -> None:
    """Multi-LLM: закрыть все слоты сообщением «подождите» + сохранить."""
    for i, model_name in enumerate(multi_llm_models):
        await sio.emit(
            "multi_llm_complete",
            {
                "model": model_name,
                "response": REINDEX_WAIT_MESSAGE,
                "error": False,
                "index": i,
                "total": len(multi_llm_models),
            },
            room=sid,
        )
    try:
        if conversation_id and multi_llm_models:
            slots = [
                {"model": m, "content": REINDEX_WAIT_MESSAGE, "error": False}
                for m in multi_llm_models
            ]
            combined = "\n\n".join(f"{s['model']}:\n{s['content']}" for s in slots)
            await save_assistant_response(
                combined,
                {"multi_llm_responses": slots, "reindex_wait": True},
                conversation_id=conversation_id,
                user_id=(current_user or {}).get("user_id"),
                project_id=project_id,
            )
    except Exception:
        logger.exception("Сохранение multi-LLM reindex-wait ответа")

async def _compute_and_emit_rag_metrics(
    sio,
    sid,
    *,
    query: str,
    document_search_trace: Optional[dict],
    context_text: str,
    answer: str,
    context_added: bool,
) -> Optional[dict]:
    """Считает online RAG-метрики (RR/Context Precision/Faithfulness) и шлёт их в UI.

    Fail-safe: любая ошибка гасится, основной ответ уже отдан пользователю.
    """
    if not context_added or not document_search_trace or not answer:
        return None
    try:
        from backend.rag_query.metrics import compute_online_rag_metrics

        metrics = await compute_online_rag_metrics(
            query=query,
            hits=(document_search_trace or {}).get("hits") or [],
            answer=answer,
            context_text=context_text,
        )
        if metrics:
            with logged_suppress(logger):
                await sio.emit("chat_rag_metrics", {"metrics": metrics}, room=sid)
        return metrics
    except Exception:
        logger.exception("rag online metrics")
        return None


def _regen_save_kwargs(data: Optional[dict]) -> dict:
    """Параметры regenerate из socket payload для save_assistant_response."""
    if not isinstance(data, dict):
        return {"regenerate": False}
    alts = data.get("alternative_responses")
    if not isinstance(alts, list):
        alts = data.get("alternativeResponses")
    idx = data.get("current_response_index")
    if not isinstance(idx, int):
        idx = data.get("currentResponseIndex")
    return {
        "regenerate": bool(data.get("regenerate")),
        "assistant_message_id": str(data.get("assistant_message_id") or "").strip() or None,
        "alternative_responses": alts if isinstance(alts, list) else None,
        "current_response_index": idx if isinstance(idx, int) else None,
    }


def _run_sync_preserving_cef_audit(factory):
    """Устаревший вариант: copy_context() вызывался внутри потока (там контекст пустой).
    Оставлен для совместимости; для новых вызовов используй _make_ctx_runner."""
    return contextvars.copy_context().run(factory)


def _make_ctx_runner(factory):
    """Захватывает текущий contextvars.Context прямо здесь (в asyncio-задаче)
    и возвращает нуль-аргументный callable для передачи в run_in_executor.

    Правило: вызывать СТРОГО в asyncio-задаче, до передачи в executor:
        runner = _make_ctx_runner(lambda: ask_agent(...))
        await loop.run_in_executor(ex, runner)
    """
    _ctx = contextvars.copy_context()

    def _runner():
        return _ctx.run(factory)

    return _runner


_VALID_RAG_STRATEGIES = {"auto", "hierarchical", "hybrid", "vector", "lexical", "graph"}


def _extract_socket_token(auth: Any, environ: Optional[Dict[str, Any]]) -> Optional[str]:
    """Извлекает bearer-токен из Socket.IO handshake auth/environ."""
    token: Optional[str] = None
    if isinstance(auth, dict):
        raw = auth.get("token") or auth.get("access_token")
        if isinstance(raw, str) and raw.strip():
            token = raw.strip()
    if not token and isinstance(environ, dict):
        auth_header = environ.get("HTTP_AUTHORIZATION")
        if isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    return token if token else None


async def _get_socket_user_context(sio, sid: str) -> Optional[Dict[str, Any]]:
    """Возвращает user context, сохранённый в Socket.IO сессии.

    Проверяет, что сессия всё ещё активна (не была вытеснена новым логином
    с другого устройства/браузера). При ревоцированной сессии возвращает None
    — вызывающий код эмитирует ошибку «Сессия завершена» и фронтенд
    перенаправит пользователя на страницу входа.
    """
    try:
        session = await sio.get_session(sid)
    except Exception:
        logger.exception("Ошибка операции")
        return None
    if not isinstance(session, dict):
        return None
    user_ctx = session.get("user")
    if not isinstance(user_ctx, dict):
        return None
    token = user_ctx.get("token")
    if token:
        try:
            decode_token(token)
        except Exception:
            logger.exception("Socket.IO msg rejected: сессия ревоцирована sid= user_id=")
            return None
    return user_ctx


def _multi_llm_llm_svc_pool_style_path(model_path: str) -> bool:
    """Пути multi-LLM через llm-svc: не держим глобальный model_load_lock — пул и load на стороне llm-svc."""
    provider_id, _model_id = split_model_path(model_path or "")
    return bool(provider_id)


async def get_conversation_project_id(conversation_id: str) -> "Optional[str]":
    """Возвращает project_id диалога из MongoDB, или None если диалог не привязан к проекту."""
    if not conversation_id:
        return None
    try:
        from backend.database.init_db import get_conversation_repository

        repo = get_conversation_repository()
        conv = await repo.get_conversation(conversation_id)
        return conv.project_id if conv else None
    except Exception:
        logger.exception("_get_conversation_project_id()")
        return None


def _build_user_inline_attachments_metadata(raw: Any) -> Optional[Dict[str, Any]]:
    """Метаданные вложений для MongoDB (без base64 — только MinIO-ссылки и имена)."""
    if not isinstance(raw, list) or not raw:
        return None
    items: list = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "file").strip() or "file"
        ct = entry.get("contentType") or entry.get("content_type")
        if ct not in ("text", "image"):
            continue
        item: Dict[str, Any] = {"name": name, "contentType": ct}
        mo = entry.get("minio_object")
        mb = entry.get("minio_bucket")
        if mo:
            item["minio_object"] = str(mo)
        if mb:
            item["minio_bucket"] = str(mb)
        sz = entry.get("size")
        if isinstance(sz, (int, float)) and sz > 0:
            item["size"] = int(sz)
        items.append(item)
    return {"inline_attachments": items} if items else None


async def _handle_chat_image_generation_request(
    sio,
    sid: str,
    *,
    user_message: str,
    conversation_id: Optional[str],
    project_id: Optional[str],
    current_user: Optional[dict],
    streaming: bool,
    image_gen_preset_id: Optional[str] = None,
    regenerate: bool = False,
    assistant_message_id: Optional[str] = None,
):
    """Генерация изображения по фразе «нарисуй …» без вызова LLM."""
    from backend.services.comfyui_image_generation import ComfyImageGenError
    from backend.services.image_generation_service import (
        handle_chat_image_generation,
        is_image_generation_chat_request,
        save_image_generation_assistant_message,
    )

    if not is_image_generation_chat_request(user_message):
        return False

    await sio.emit(
        "chat_thinking",
        {
            "status": "processing",
            "message": "Генерирую изображение в ComfyUI…",
            "image_generation": True,
        },
        room=sid,
    )

    try:
        result = await handle_chat_image_generation(
            user_message,
            preset_id=image_gen_preset_id,
        )
    except ComfyImageGenError as exc:
        err_text = f"Не удалось сгенерировать изображение: {exc}"
        logger.warning("Chat image generation failed: %s", exc)
        await sio.emit("chat_complete", {
            "response": err_text,
            "timestamp": datetime.now().isoformat(),
            "was_streaming": streaming,
            "image_generation_error": True,
        }, room=sid)
        try:
            meta = {"image_generation_error": True}
            if project_id:
                from backend.database.memory_service import save_dialog_entry_to_project
                await save_dialog_entry_to_project(
                    "assistant",
                    err_text,
                    project_id,
                    conversation_id,
                    metadata=meta,
                    user_id=(current_user or {}).get("user_id"),
                )
            else:
                await save_dialog_entry(
                    "assistant",
                    err_text,
                    meta,
                    None,
                    conversation_id,
                    user_id=(current_user or {}).get("user_id"),
                )
        except Exception as save_exc:
            logger.warning("Не удалось сохранить ошибку image gen: %s", save_exc)
        stop_generation_flags[sid] = False
        return True

    response = result.get("response") or ""
    meta = result.get("metadata") or {}
    inline_attachments = result.get("inline_attachments") or []

    try:
        await save_image_generation_assistant_message(
            content=response,
            metadata=meta,
            conversation_id=conversation_id,
            project_id=project_id,
            user_id=(current_user or {}).get("user_id"),
            regenerate=regenerate,
            assistant_message_id=assistant_message_id,
        )
    except Exception as save_exc:
        logger.warning("Не удалось сохранить ответ image gen: %s", save_exc)

    stop_generation_flags[sid] = False
    payload = {
        "response": response,
        "timestamp": datetime.now().isoformat(),
        "was_streaming": streaming,
        "inline_attachments": inline_attachments,
        "image_generation": True,
    }
    await sio.emit("chat_complete", payload, room=sid)
    return True


def register_handlers(sio):
    """Регистрирует все Socket.IO обработчики на переданный sio-сервер"""

    @sio.event
    async def connect(sid, environ, auth = None):
        token = _extract_socket_token(auth, environ)
        if not token:
            logger.warning("Socket.IO connect rejected: отсутствует токен sid=%s", sid)
            raise ConnectionRefusedError("Не авторизован")
        try:
            # Проверяем ТОЛЬКО подпись и срок действия JWT, без _is_active_session.
            # Это позволяет переподключиться после рестарта пода (когда in-memory словарь
            # сессий пуст, но JWT ещё валиден). Проверка активности сессии выполняется
            # при обработке каждого сообщения (_get_socket_user_context).
            user_data = decode_token_signature_only(token)
        except Exception as e:
            logger.warning("Socket.IO connect rejected: невалидный JWT sid=%s reason=%s", sid, e)
            raise ConnectionRefusedError("Неверный или просроченный токен")

        _cef_remote = cef_socket_remote_from_environ(environ if isinstance(environ, dict) else None)
        _sess: Dict[str, Any] = {
            "user": {
                "username": user_data["username"],
                "user_id": user_data["user_id"],
                "session_id": user_data.get("session_id"),
                "token": token,
            }
        }
        if _cef_remote:
            _sess["cef_remote"] = _cef_remote
        await sio.save_session(sid, _sess)
        logger.info(
            "Socket.IO client connected: sid=%s user_id=%s session_id=%s",
            sid,
            user_data.get("user_id"),
            user_data.get("session_id"),
        )
        stop_generation_flags[sid] = False
        await sio.emit("connected", {"data": "Connected to astrachat"}, room=sid)

    @sio.event
    async def disconnect(sid):
        logger.debug(f"Socket.IO client disconnected: {sid}")
        stop_generation_flags.pop(sid, None)

    @sio.event
    async def ping(sid, data):
        try:
            await sio.emit(
                "pong", {"timestamp": data.get("timestamp", 0), "server_time": datetime.now().isoformat()}, room=sid
            )
        except Exception:
            logger.exception("Ошибка обработки ping")

    @sio.event
    async def stop_generation(sid, data):
        logger.info(f"Socket.IO: команда остановки генерации от {sid}")
        stop_generation_flags[sid] = True
        await sio.emit(
            "generation_stopped",
            {"content": "Генерация остановлена", "timestamp": datetime.now().isoformat()},
            room=sid,
        )

    @sio.event
    async def stop_transcription(sid, data):
        logger.info(f"Socket.IO: команда остановки транскрибации от {sid}")
        stop_transcription_flags[sid] = True
        await sio.emit(
            "transcription_stopped",
            {"message": "Транскрибация остановлена", "timestamp": datetime.now().isoformat()},
            room=sid,
        )

    @sio.event
    async def chat_message(sid, data):
        if not ask_agent or not save_dialog_entry:
            await sio.emit("chat_error", {"error": "AI services not available"}, room=sid)
            return
        rag_runtime_token = None
        try:
            user_ctx = await _get_socket_user_context(sio, sid)
            if not user_ctx:
                await sio.emit("chat_error", {"error": "Не авторизован"}, room=sid)
                await sio.disconnect(sid)
                return
            try:
                validated_user = decode_token(user_ctx.get("token", ""))
            except Exception:
                logger.exception("Socket.IO chat rejected: session invalid sid= reason=")
                await sio.emit(
                    "chat_error", {"error": "Сессия завершена: выполнен вход с другого устройства/окна"}, room=sid
                )
                await sio.disconnect(sid)
                return
            try:
                user_rag = await get_user_rag_settings(validated_user.get("user_id"))
                rag_runtime_token = bind_user_rag_runtime(user_rag)
            except Exception:
                logger.exception("Не удалось загрузить персональные RAG-настройки")
                user_rag = {}
                rag_runtime_token = bind_user_rag_runtime({})
            user_message = data.get("message", "")
            streaming = data.get("streaming", True)
            _et = data.get("enable_thinking", False)
            if isinstance(_et, bool):
                enable_thinking = _et
            elif isinstance(_et, (int, float)) and _et == 0:
                enable_thinking = False
            elif isinstance(_et, str) and _et.strip().lower() in ("0", "false", "no", "off", ""):
                enable_thinking = False
            else:
                enable_thinking = bool(_et)
            stop_generation_flags[sid] = False
            user_message_id = data.get("message_id", None)
            conversation_id = data.get("conversation_id", None)
            use_kb_rag = bool(data.get("use_kb_rag", False))
            use_memory_library_rag = bool(data.get("use_memory_library_rag", False))
            _raw_inline_ctx = data.get("inline_context") or ""
            inline_context = str(_raw_inline_ctx).strip() if _raw_inline_ctx else ""
            _raw_inline_imgs = data.get("inline_images")
            inline_images: list = [str(x) for x in _raw_inline_imgs if x] if isinstance(_raw_inline_imgs, list) else []
            user_message_metadata = _build_user_inline_attachments_metadata(data.get("inline_attachments"))
            requested_rag_strategy = str(data.get("rag_strategy") or "").strip().lower()
            fallback_strategy = str(
                (user_rag or {}).get("rag_strategy") or runtime_rag_strategy() or "auto"
            )
            effective_rag_strategy = (
                requested_rag_strategy
                if requested_rag_strategy in _VALID_RAG_STRATEGIES
                else fallback_strategy
            )
            agent_profile = await _resolve_agent_chat_params(
                data.get("agent_id"), validated_user.get("user_id") if validated_user else None
            )
            agent_profile = await enrich_agent_profile_with_user_settings(
                agent_profile, validated_user.get("user_id") if validated_user else None
            )
            agent_kb_enabled = bool(agent_profile.get("file_search_enabled"))
            agent_kb_doc_ids = agent_profile.get("kb_document_ids") or []
            use_agent_scoped_kb = (
                agent_kb_enabled and isinstance(agent_kb_doc_ids, list) and (len(agent_kb_doc_ids) > 0)
            )
            is_regenerate = bool(data.get("regenerate"))
            skip_user_save = is_regenerate
            if conversation_id:
                import backend.database.memory_service as mem_mod

                mem_mod.current_conversation_id = conversation_id
            with logged_suppress(logger):
                from backend.settings.cef_logger.cef_audit_context import cef_audit_set

                cef_rem = None
                with logged_suppress(logger):
                    _sess = await sio.get_session(sid)
                    if isinstance(_sess, dict):
                        _cr = _sess.get("cef_remote")
                        if isinstance(_cr, dict) and _cr.get("src"):
                            cef_rem = _cr
                cef_audit_set(user=validated_user, conversation_id=conversation_id, socket_remote=cef_rem)
            project_id = data.get("project_id") or None
            if project_id:
                logger.debug(f"[chat_message] project_id из payload: {project_id}")
            else:
                project_id = await get_conversation_project_id(conversation_id)
                if project_id:
                    logger.debug(f"[chat_message] project_id из MongoDB: {project_id}")
            project_memory = data.get("project_memory") or "default"
            project_instructions = data.get("project_instructions") or ""
            if project_id and project_memory == "project-only":
                from backend.database.memory_service import get_project_memory_history

                history = await get_project_memory_history(project_id, max_entries=state.memory_max_messages)
                logger.debug(f"[chat_message] project-only история: {len(history)} сообщений из проекта {project_id}")
            else:
                history = await get_recent_dialog_history(
                    max_entries=state.memory_max_messages, conversation_id=conversation_id
                )
            if not skip_user_save:
                try:
                    if project_id:
                        from backend.database.memory_service import save_dialog_entry_to_project

                        await save_dialog_entry_to_project(
                            "user",
                            user_message,
                            project_id,
                            conversation_id,
                            user_message_id,
                            metadata=user_message_metadata,
                            user_id=validated_user["user_id"],
                        )
                    else:
                        await save_dialog_entry(
                            "user",
                            user_message,
                            user_message_metadata,
                            user_message_id,
                            conversation_id,
                            user_id=validated_user["user_id"],
                        )
                except RuntimeError as e:
                    if "MongoDB" in str(e):
                        await sio.emit("chat_error", {"error": "MongoDB недоступен."}, room=sid)
                        return
                    raise
            handled_image = await _handle_chat_image_generation_request(
                sio,
                sid,
                user_message=user_message,
                conversation_id=conversation_id,
                project_id=project_id,
                current_user=validated_user,
                streaming=streaming,
                image_gen_preset_id=(data.get("image_gen_preset_id") or None),
                regenerate=is_regenerate,
                assistant_message_id=str(data.get("assistant_message_id") or "").strip() or None,
            )
            if handled_image:
                return

            orchestrator = get_agent_orchestrator()
            use_agent_mode = orchestrator and orchestrator.get_mode() == "agent"
            use_multi_llm_mode = bool(data.get("model_comparison_enabled", False))
            chat_mode = "model-comparison" if use_multi_llm_mode else "agent" if use_agent_mode else "direct"
            logger.info(
                "[RAG] chat_message mode=%s effective_strategy=%s payload_rag_strategy=%r settings_rag_strategy=%s agentic_rag_enabled=%s use_kb_rag=%s use_memory_library_rag=%s use_agent_scoped_kb=%s project_id=%s",
                chat_mode,
                effective_rag_strategy,
                requested_rag_strategy or "",
                (user_rag or {}).get("rag_strategy") or runtime_rag_strategy(),
                runtime_agentic_rag_enabled(),
                use_kb_rag,
                use_memory_library_rag,
                use_agent_scoped_kb,
                project_id,
            )

            async def async_stream_cb(chunk, acc, stream_role="content"):
                with logged_suppress(logger):
                    if stream_role == "reasoning":
                        await sio.emit(
                            "chat_thinking",
                            {"chunk": chunk, "accumulated": acc, "thinking": chunk, "stream_role": "reasoning"},
                            room=sid,
                        )
                    else:
                        await sio.emit("chat_chunk", {"chunk": chunk, "accumulated": acc}, room=sid)

            loop = asyncio.get_event_loop()

            def sync_stream_cb(chunk, acc, stream_role="content"):
                if stop_generation_flags.get(sid, False):
                    return False
                asyncio.run_coroutine_threadsafe(async_stream_cb(chunk, acc, stream_role), loop)
                return True

            if use_multi_llm_mode:
                slot = str(data.get("multi_llm_slot_regenerate") or "").strip()
                models_subset = [slot] if bool(data.get("regenerate")) and slot else None
                await _handle_multi_llm(
                    sio,
                    sid,
                    data,
                    user_message,
                    streaming,
                    conversation_id,
                    use_kb_rag,
                    use_memory_library_rag,
                    loop,
                    use_agent_scoped_kb,
                    agent_kb_doc_ids,
                    project_id=project_id,
                    project_instructions=project_instructions,
                    rag_strategy=effective_rag_strategy,
                    models_subset=models_subset,
                    enable_thinking=enable_thinking,
                    inline_context=inline_context,
                    inline_images=inline_images,
                    current_user=validated_user,
                    agent_profile=agent_profile,
                )
                return
            if use_agent_mode:
                await _handle_agent_mode(
                    sio,
                    sid,
                    data,
                    user_message,
                    streaming,
                    conversation_id,
                    history,
                    use_kb_rag,
                    use_memory_library_rag,
                    orchestrator,
                    use_agent_scoped_kb,
                    agent_kb_doc_ids,
                    agent_profile=agent_profile,
                    project_id=project_id,
                    project_instructions=project_instructions,
                    rag_strategy=effective_rag_strategy,
                    current_user=validated_user,
                    enable_thinking=enable_thinking,
                    inline_context=inline_context,
                    inline_images=inline_images,
                )
                return
            await _handle_direct(
                sio,
                sid,
                data,
                user_message,
                streaming,
                conversation_id,
                history,
                use_kb_rag,
                use_memory_library_rag,
                agent_profile,
                sync_stream_cb,
                loop,
                use_agent_scoped_kb,
                agent_kb_doc_ids,
                project_id=project_id,
                project_instructions=project_instructions,
                rag_strategy=effective_rag_strategy,
                current_user=validated_user,
                enable_thinking=enable_thinking,
                inline_context=inline_context,
                inline_images=inline_images,
            )
        except Exception as e:
            logger.exception("Ошибка операции")
            logger.error(f"Socket.IO chat error: {e}", exc_info=True)
            with logged_suppress(logger):
                await sio.emit("chat_error", {"error": str(e)}, room=sid)
        finally:
            stop_generation_flags[sid] = False
            if rag_runtime_token is not None:
                with logged_suppress(logger):
                    reset_user_rag_runtime(rag_runtime_token)


async def _handle_multi_llm(
    sio,
    sid,
    data,
    user_message,
    streaming,
    conversation_id,
    use_kb_rag,
    use_memory_library_rag,
    loop,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    models_subset=None,
    enable_thinking=False,
    inline_context: str = "",
    inline_images: list = None,
    current_user=None,
    agent_profile=None,
):
    multi_llm_models = get_model_comparison_models()
    if not multi_llm_models:
        await sio.emit("chat_error", {"error": "Модели не выбраны"}, room=sid)
        return
    if models_subset is not None:
        allowed = set(multi_llm_models)
        multi_llm_models = [m for m in models_subset if m in allowed]
        if not multi_llm_models:
            await sio.emit("chat_error", {"error": "Указанная модель не входит в список multi-LLM"}, room=sid)
            return
    _terminal_chat_inference_banner(
        sid=sid,
        conversation_id=conversation_id,
        user_preview=user_message,
        mode_label=f"MULTI-LLM - модели: {', '.join(multi_llm_models)}",
        extra_line="Ниже для каждой модели - отдельный блок перед вызовом LLM.",
        enable_thinking=enable_thinking,
    )
    min_sim, rag_block = rag_guard_env()
    sources = resolve_active_rag_sources(
        project_id=project_id,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        use_memory_library_rag=use_memory_library_rag,
        use_kb_rag=use_kb_rag,
    )
    if await rag_reindex_blocks_active_sources(sources, rag_client, project_id=project_id):
        await _notify_reindex_wait(sio, sid)
        await _abort_multi_llm_reindex(
            sio, sid, multi_llm_models, conversation_id, project_id, current_user
        )
        return
    context_added = False
    final_user_message = user_message
    if rag_client and sources.project:
        try:
            proj_rows = list(await rag_client.project_rag_list_documents(project_id) or [])
            proj_id_name = build_rag_id_to_filename(proj_rows)
            proj_hits = await rag_client.project_rag_search(
                user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
            )
            proj_hits = filter_rag_hits_by_score(proj_hits, min_sim)
            if proj_hits:
                parts, _m = format_rag_fragments(
                    proj_hits, proj_id_name, max_chars=12000, store_label="project (multi-llm)"
                )
                if parts:
                    final_user_message = f"""Документы проекта (RAG):
{chr(10).join(parts)}
Вопрос: {user_message}"""
                    context_added = True
                    logger.info(f"[multi-llm project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_multi_llm_reindex(
                sio, sid, multi_llm_models, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("multi-llm project RAG error")
    # KB — только документы выбранного агента; широкий поиск по всей KB убран
    # (тумблер библиотеки без агента ищет только memory-rag).
    if rag_client and sources.agent_kb:
        prefix = "База Знаний (документы агента)"
        try:
            kb_id_name = build_rag_id_to_filename(list(await rag_client.kb_list_documents() or []))
            hits = await kb_search_agent_documents(
                rag_client,
                user_message,
                agent_kb_doc_ids or [],
                k=get_rag_chat_top_k(),
                strategy=rag_strategy,
            )
            hits = filter_rag_hits_by_score(list(hits or []), min_sim)
            if hits:
                parts, _m = format_rag_fragments(
                    hits, kb_id_name, max_chars=10000, store_label="kb (multi-llm)", include_chunk_meta=False
                )
                if parts:
                    final_user_message = f"""{prefix}:
{''.join(parts)}

{final_user_message}"""
                    context_added = True
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_multi_llm_reindex(
                sio, sid, multi_llm_models, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("multi-llm kb_search error")
    if sources.memory and rag_client:
        try:
            mem_id_name = build_rag_id_to_filename(list(await rag_client.memory_rag_list_documents() or []))
            hits = await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
            hits = filter_rag_hits_by_score(list(hits or []), min_sim)
            prefix = "Документы из настроек (библиотека памяти)"
            if hits:
                parts, _m = format_rag_fragments(
                    hits, mem_id_name, max_chars=10000, store_label="memory (multi-llm)", include_chunk_meta=False
                )
                if parts:
                    final_user_message = f"""{prefix}:
{''.join(parts)}

{final_user_message}"""
                    context_added = True
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_multi_llm_reindex(
                sio, sid, multi_llm_models, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("multi-llm memory_rag_search error")
    if inline_context:
        inline_block = f"""[Прикреплённый документ]
{inline_context}"""
        if final_user_message != user_message:
            final_user_message = f"{inline_block}\n\n{final_user_message}"
        else:
            final_user_message = f"""{inline_block}

[Вопрос пользователя]
{user_message}"""
        context_added = True
        logger.info(
            f"[multi-llm inline_context] {len(inline_context)} символов, RAG-контекст {('совмещён' if final_user_message != inline_block else 'не применялся')}"
        )
    inline_imgs = list(inline_images) if inline_images else None
    rag_override = runtime_rag_system_prompt() or None

    feedback_block = await build_user_feedback_system_block(
        (current_user or {}).get("user_id"),
        conversation_id=conversation_id,
    )
    user_cpm = await get_user_prompt_manager((current_user or {}).get("user_id"))
    if user_cpm is None:
        user_cpm = context_prompt_manager

    def _system_prompt_for_model(model_path: Optional[str]) -> Optional[str]:
        prompt = None
        agent_sp = (agent_profile.get("system_prompt") or "") if isinstance(agent_profile, dict) else ""
        if user_cpm:
            prompt = user_cpm.resolve_chat_system_prompt(
                model_path,
                agent_system_prompt=agent_sp,
                project_instructions=project_instructions,
            )
        elif project_instructions and project_instructions.strip():
            prompt = project_instructions.strip()
        elif agent_sp and agent_sp.strip():
            prompt = agent_sp.strip()
        prompt = merge_feedback_into_system_prompt(prompt, feedback_block)
        if context_added:
            prompt = merge_strict_rag_system_prompt(prompt, rag_override=rag_override)
        return prompt

    canned = await maybe_rag_no_evidence_message(
        rag_client,
        block_when_no_evidence=rag_block,
        context_added=context_added,
        project_id=project_id,
        use_kb_rag=use_kb_rag,
        use_memory_library_rag=sources.memory,
        use_agent_scoped_kb=sources.agent_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
    )
    if canned:
        if multi_llm_models:
            await sio.emit(
                "multi_llm_start",
                {"model": multi_llm_models[0], "models": multi_llm_models, "total_models": len(multi_llm_models)},
                room=sid,
            )
        for i, model_name in enumerate(multi_llm_models):
            await sio.emit(
                "multi_llm_complete",
                {"model": model_name, "response": canned, "error": False, "index": i, "total": len(multi_llm_models)},
                room=sid,
            )
        # Сохраняем canned-ответ в историю — иначе после F5 он исчезает
        try:
            if conversation_id and multi_llm_models:
                slots = [
                    {"model": m, "content": canned, "error": False}
                    for m in multi_llm_models
                ]
                combined = "\n\n".join(
                    f"{s['model']}:\n{s['content']}" for s in slots
                )
                assistant_meta = {"multi_llm_responses": slots}
                if project_id:
                    from backend.database.memory_service import save_dialog_entry_to_project

                    await save_dialog_entry_to_project(
                        "assistant",
                        combined,
                        project_id,
                        conversation_id,
                        metadata=assistant_meta,
                        user_id=(current_user or {}).get("user_id"),
                    )
                else:
                    await save_dialog_entry(
                        "assistant",
                        combined,
                        assistant_meta,
                        None,
                        conversation_id,
                        user_id=(current_user or {}).get("user_id"),
                    )
        except Exception:
            logger.exception("Ошибка сохранения canned multi-LLM ответа")
        return
    n_models = len(multi_llm_models)
    tool_ids = resolve_chat_tool_ids(data.get("tool_ids") or data.get("mcp_tool_ids"))
    mcp_enabled = bool(tool_ids and current_user and (not inline_imgs))
    _ap = agent_profile if isinstance(agent_profile, dict) else {}
    mcp_temperature = float(
        data.get("temperature") if data.get("temperature") is not None else (_ap.get("temperature") or 0.7)
    )
    mcp_max_tokens = int(
        data.get("max_tokens") if data.get("max_tokens") is not None else (_ap.get("max_tokens") or 1024)
    )

    async def _gen_one(model_name: str):
        idx = multi_llm_models.index(model_name)
        eff_system_prompt = _system_prompt_for_model(model_name)

        async def _emit_complete(res: dict) -> dict:
            await sio.emit(
                "multi_llm_complete",
                {
                    "model": res.get("model", model_name),
                    "response": res.get("response", "") or "",
                    "error": bool(res.get("error", False)),
                    "index": idx,
                    "total": n_models,
                    "mcp_mode": res.get("mcp_mode"),
                    "mcp_tool_calls": res.get("mcp_tool_calls"),
                },
                room=sid,
            )
            return res

        try:
            await sio.emit(
                "multi_llm_start",
                {"model": model_name, "models": multi_llm_models, "total_models": n_models, "mcp_enabled": mcp_enabled},
                room=sid,
            )
            if mcp_enabled:
                try:
                    from backend.mcp.chat_integration import run_mcp_for_chat

                    async def _mcp_event_cb(payload):
                        event = dict(payload)
                        event["model"] = model_name
                        await sio.emit("chat_mcp_event", event, room=sid)

                    mcp_result = await run_mcp_for_chat(
                        tool_ids=tool_ids,
                        user_message=final_user_message,
                        history=[],
                        system_prompt=eff_system_prompt,
                        model_path=model_name,
                        user=current_user,
                        chat_id=conversation_id,
                        message_id=data.get("message_id"),
                        temperature=mcp_temperature,
                        max_tokens=mcp_max_tokens,
                        enable_thinking=enable_thinking,
                        emit_event=_mcp_event_cb,
                    )
                    if mcp_result is not None:
                        resp = mcp_result.content or ""
                        if streaming and resp:
                            await sio.emit(
                                "multi_llm_chunk", {"model": model_name, "chunk": resp, "accumulated": resp}, room=sid
                            )
                        if context_added and resp.strip():
                            resp = await maybe_replace_ungrounded(
                                final_user_message[:20000], resp, RAG_STRICT_NOT_FOUND_MESSAGE
                            )
                        logger.info(
                            "Multi-LLM MCP: model=%s mode=%s tools=%s",
                            model_name,
                            mcp_result.mode,
                            mcp_result.tool_calls_executed,
                        )
                        return await _emit_complete(
                            {
                                "model": model_name,
                                "response": resp,
                                "error": False,
                                "mcp_mode": mcp_result.mode,
                                "mcp_tool_calls": mcp_result.tool_calls_executed,
                            }
                        )
                except Exception:
                    logger.exception("Multi-LLM MCP error model=")
            model_path = model_name

            def _model_stream_cb(chunk, acc):
                if stop_generation_flags.get(sid, False):
                    return False
                asyncio.run_coroutine_threadsafe(
                    sio.emit("multi_llm_chunk", {"model": model_name, "chunk": chunk, "accumulated": acc}, room=sid),
                    loop,
                )
                return True

            with concurrent.futures.ThreadPoolExecutor() as ex:
                _runner = _make_ctx_runner(
                    lambda: ask_agent(
                        final_user_message,
                        [],
                        mcp_max_tokens,
                        streaming,
                        _model_stream_cb if streaming else None,
                        model_path,
                        None,
                        images=inline_imgs,
                        system_prompt=eff_system_prompt,
                        temperature=mcp_temperature,
                        enable_thinking=enable_thinking,
                    )
                )
                resp = await asyncio.get_event_loop().run_in_executor(ex, _runner)
            if context_added and isinstance(resp, str) and resp.strip():
                resp = await maybe_replace_ungrounded(final_user_message[:20000], resp, RAG_STRICT_NOT_FOUND_MESSAGE)
            return await _emit_complete(
                {"model": model_name, "response": resp if isinstance(resp, str) else "", "error": False}
            )
        except Exception as e:
            logger.exception("Ошибка операции")
            return await _emit_complete({"model": model_name, "response": f"Ошибка: {e}", "error": True})

    results: list = await asyncio.gather(*[_gen_one(m) for m in multi_llm_models], return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, dict):
            continue
        await sio.emit(
            "multi_llm_complete",
            {
                "model": multi_llm_models[i] if i < len(multi_llm_models) else "unknown",
                "response": str(result),
                "error": True,
                "index": i,
                "total": n_models,
            },
            room=sid,
        )

    # Сохраняем агрегированный multi-LLM ответ в историю, чтобы он не исчезал после перезагрузки.
    try:
        slots: list[dict] = []
        for i, model_name in enumerate(multi_llm_models):
            row = results[i] if i < len(results) and isinstance(results[i], dict) else None
            content = str((row or {}).get("response") or "")
            has_error = bool((row or {}).get("error", row is None))
            slot: dict = {
                "model": str((row or {}).get("model") or model_name),
                "content": content,
                "error": has_error,
            }
            alts = (row or {}).get("alternative_responses")
            if isinstance(alts, list) and alts:
                slot["alternative_responses"] = [str(v) for v in alts]
            current_idx = (row or {}).get("current_response_index")
            if isinstance(current_idx, int):
                slot["current_response_index"] = current_idx
            slots.append(slot)

        if conversation_id and slots:
            combined = "\n\n".join(
                (
                    f"{slot['model']}:\n{slot['content']}".strip()
                    if slot.get("content")
                    else f"{slot['model']}:\n[пустой ответ]"
                )
                for slot in slots
            )
            assistant_meta = {"multi_llm_responses": slots}
            if project_id:
                from backend.database.memory_service import save_dialog_entry_to_project

                await save_dialog_entry_to_project(
                    "assistant",
                    combined,
                    project_id,
                    conversation_id,
                    metadata=assistant_meta,
                    user_id=(current_user or {}).get("user_id"),
                )
            else:
                await save_dialog_entry(
                    "assistant",
                    combined,
                    assistant_meta,
                    None,
                    conversation_id,
                    user_id=(current_user or {}).get("user_id"),
                )
    except RuntimeError as e:
        logger.warning("Не удалось сохранить multi-LLM ответ: %s", e)
    except Exception:
        logger.exception("Ошибка сохранения агрегированного multi-LLM ответа")


async def _handle_agent_mode(
    sio,
    sid,
    data,
    user_message,
    streaming,
    conversation_id,
    history,
    use_kb_rag,
    use_memory_library_rag,
    orchestrator,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    agent_profile=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    current_user=None,
    enable_thinking=False,
    inline_context: str = "",
):
    await sio.emit(
        "chat_thinking",
        {"status": "processing", "message": "Обрабатываю запрос через агентную архитектуру..."},
        room=sid,
    )
    agentic_rag_enabled = bool(runtime_agentic_rag_enabled())
    sources = resolve_active_rag_sources(
        project_id=project_id,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        use_memory_library_rag=use_memory_library_rag,
        use_kb_rag=use_kb_rag,
    )
    if await rag_reindex_blocks_active_sources(sources, rag_client, project_id=project_id):
        await _notify_reindex_wait(sio, sid)
        await _abort_chat_reindex(
            sio, sid, conversation_id, project_id, current_user
        )
        return
    ap = agent_profile or {}
    eff_model_path = ap.get("model_path") or get_current_model_path()
    reasoning_trace_accumulated = ""

    async def agent_stream_cb(chunk, acc, stream_role="content"):
        nonlocal reasoning_trace_accumulated
        if stop_generation_flags.get(sid, False):
            return False
        if stream_role == "reasoning":
            if isinstance(acc, str) and acc:
                reasoning_trace_accumulated = acc
            elif isinstance(chunk, str) and chunk:
                reasoning_trace_accumulated += chunk
            await sio.emit(
                "chat_thinking",
                {"chunk": chunk, "accumulated": acc, "thinking": chunk, "stream_role": "reasoning"},
                room=sid,
            )
        else:
            await sio.emit("chat_chunk", {"chunk": chunk, "accumulated": acc}, room=sid)
        return True

    context = {
        "history": history,
        "user_message": user_message,
        "selected_model": eff_model_path,
        "socket_id": sid,
        "streaming": streaming,
        "sio": sio,
        "stream_callback": agent_stream_cb if streaming else None,
        "_main_event_loop": asyncio.get_running_loop(),
        "project_instructions": project_instructions or "",
        "agent_system_prompt": (agent_profile.get("system_prompt") or "") if isinstance(agent_profile, dict) else "",
        "project_id": project_id,
        "rag_strategy": rag_strategy,
        "agentic_rag_enabled": agentic_rag_enabled,
        "agentic_max_iterations": int(runtime_agentic_max_iterations()),
        "enable_thinking": enable_thinking,
        "tool_ids": resolve_chat_tool_ids(data.get("tool_ids") or data.get("mcp_tool_ids")),
        "current_user": current_user,
        "conversation_id": conversation_id,
        "message_id": data.get("message_id"),
        "use_agent_scoped_kb": sources.agent_kb,
        "agent_kb_doc_ids": agent_kb_doc_ids or [],
        # Прокидываем тумблер «Библиотека», чтобы agentic-tool не подмешивал
        # memory-RAG, когда пользователь его не включал.
        "use_memory_library_rag": sources.memory,
        "active_rag_sources": sources.as_dict(),
    }
    _get_set_tool_context()(context)
    effective_message = user_message
    if project_instructions and project_instructions.strip():
        effective_message = f"[Инструкции проекта: {project_instructions.strip()}]\n\n{user_message}"
    _agent_sp_text = (agent_profile.get("system_prompt") or "").strip() if isinstance(agent_profile, dict) else ""
    if _agent_sp_text and _agent_sp_text != "Системные инструкции не заданы.":
        effective_message = f"[Инструкции агента: {_agent_sp_text}]\n\n{effective_message}"
    feedback_block = await build_user_feedback_system_block(
        (current_user or {}).get("user_id"),
        conversation_id=conversation_id,
    )
    if feedback_block:
        # В agent mode system prompt оркестратора собирается отдельно —
        # предпочтения пользователя добавляем в начало user-сообщения.
        effective_message = f"{feedback_block}\n\n{effective_message}"
        context["user_feedback_block"] = feedback_block
    if not agentic_rag_enabled and rag_client and sources.project:
        try:
            proj_hits = (
                await rag_client.project_rag_search(
                    user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
                )
                or []
            )
            if proj_hits:
                proj_map: dict = {}
                with logged_suppress(logger):
                    proj_map = build_rag_id_to_filename(
                        list(await rag_client.project_rag_list_documents(project_id) or [])
                    )
                parts, _m = format_rag_fragments(
                    proj_hits, proj_map, max_chars=8000, store_label="project (agent)"
                )
                if parts:
                    effective_message = f"""Документы проекта (RAG):
{''.join(parts)}

{effective_message}"""
                    logger.info(f"[agent project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_chat_reindex(
                sio, sid, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("Agent project RAG error")
    if not agentic_rag_enabled and rag_client and sources.agent_kb:
        prefix = "База Знаний (документы агента)"
        try:
            hits = (
                await kb_search_agent_documents(
                    rag_client,
                    user_message,
                    agent_kb_doc_ids or [],
                    k=get_rag_chat_top_k(),
                    strategy=rag_strategy,
                )
                or []
            )
            if hits:
                kb_map: dict = {}
                with logged_suppress(logger):
                    kb_map = build_rag_id_to_filename(list(await rag_client.kb_list_documents() or []))
                parts, _m = format_rag_fragments(
                    hits, kb_map, max_chars=8000, store_label="kb (agent)", include_chunk_meta=False
                )
                if parts:
                    effective_message = f"""{prefix}:
{''.join(parts)}

{effective_message}"""
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_chat_reindex(
                sio, sid, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("Agent kb_search error")
    if not agentic_rag_enabled and sources.memory and rag_client:
        prefix = "Документы из настроек (библиотека памяти)"
        try:
            hits = await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy) or []
            if hits:
                mem_map: dict = {}
                with logged_suppress(logger):
                    mem_map = build_rag_id_to_filename(list(await rag_client.memory_rag_list_documents() or []))
                parts, _m = format_rag_fragments(
                    hits, mem_map, max_chars=8000, store_label="memory (agent)", include_chunk_meta=False
                )
                if parts:
                    effective_message = f"""{prefix}:
{''.join(parts)}

{effective_message}"""
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_chat_reindex(
                sio, sid, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("Agent memory_rag_search error")
    if inline_context:
        inline_block = f"""[Прикреплённый документ]
{inline_context}"""
        if effective_message != user_message:
            effective_message = f"{inline_block}\n\n{effective_message}"
        else:
            effective_message = f"""{inline_block}

[Вопрос пользователя]
{user_message}"""
        logger.info(f"[agent inline_context] {len(inline_context)} символов")
    _terminal_chat_inference_banner(
        sid=sid,
        conversation_id=conversation_id,
        user_preview=user_message,
        mode_label="Оркестратор агентов (agent architecture)",
        model_path_for_call=eff_model_path,
        extra_line="Базовая модель на сервере - та, что ниже; оркестратор может дергать LLM несколько раз.",
        enable_thinking=enable_thinking,
    )
    try:
        response = await orchestrator.process_message(effective_message, history=history, context=context)
        if stop_generation_flags.get(sid, False):
            stop_generation_flags[sid] = False
            await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
            return
        if response is None:
            await sio.emit("chat_error", {"error": "Не удалось получить ответ от агента"}, room=sid)
            return
        await sio.emit(
            "chat_complete",
            {"response": response, "timestamp": datetime.now().isoformat(), "was_streaming": streaming},
            room=sid,
        )
    except Exception as e:
        logger.exception("Ошибка оркестратора")
        await sio.emit("chat_error", {"error": str(e)}, room=sid)
        stop_generation_flags[sid] = False
        return
    try:
        assistant_meta = (
            {"reasoning_content": reasoning_trace_accumulated.strip()} if reasoning_trace_accumulated.strip() else None
        )
        regen = _regen_save_kwargs(data)
        await save_assistant_response(
            response,
            assistant_meta,
            conversation_id=conversation_id,
            user_id=(current_user or {}).get("user_id"),
            project_id=project_id,
            **regen,
        )
    except Exception:
        logger.exception("Не удалось сохранить ответ агента")


async def _handle_direct(
    sio,
    sid,
    data,
    user_message,
    streaming,
    conversation_id,
    history,
    use_kb_rag,
    use_memory_library_rag,
    agent_profile,
    sync_stream_cb,
    loop,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    current_user=None,
    enable_thinking=False,
    inline_context: str = "",
    inline_images: list = None,
):
    min_sim, rag_block = rag_guard_env()
    sources = resolve_active_rag_sources(
        project_id=project_id,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        use_memory_library_rag=use_memory_library_rag,
        use_kb_rag=use_kb_rag,
    )
    if await rag_reindex_blocks_active_sources(sources, rag_client, project_id=project_id):
        await _notify_reindex_wait(sio, sid)
        await _abort_chat_reindex(
            sio, sid, conversation_id, project_id, current_user
        )
        return
    context_added = False
    final_message = user_message
    images = list(inline_images) if inline_images else None
    proj_hits_for_trace = []
    proj_id_name: dict = {}
    if rag_client and sources.project:
        with logged_suppress(logger):
            proj_rows = list(await rag_client.project_rag_list_documents(project_id) or [])
            proj_id_name = build_rag_id_to_filename(proj_rows)
    if rag_client and sources.project:
        try:
            proj_hits = await rag_client.project_rag_search(
                user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
            )
            proj_hits = filter_rag_hits_by_score(proj_hits, min_sim)
            if proj_hits:
                if _is_structure_query(user_message):
                    seen = {(d, i) for _, _, d, i in proj_hits}
                    for doc_id in {d for _, _, d, _ in proj_hits if d is not None}:
                        with logged_suppress(logger):
                            for c, sc, did, idx in await rag_client.get_document_start_chunks(doc_id, max_chunks=2):
                                if (did, idx) not in seen:
                                    proj_hits = [(c, sc, did, idx)] + proj_hits
                                    seen.add((did, idx))
                parts, _m = format_rag_fragments(
                    proj_hits, proj_id_name, max_chars=12000, store_label="project (direct)"
                )
                proj_context = "\n".join(parts)
                final_message = f"""Документы проекта (RAG):
{proj_context}
Вопрос: {user_message}
Ответь на основе этих документов. Перечисляй только то, что явно есть в фрагментах."""
                proj_hits_for_trace = proj_hits
                context_added = True
                logger.info(f"[direct project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except RagReindexInProgress:
            await _notify_reindex_wait(sio, sid)
            await _abort_chat_reindex(
                sio, sid, conversation_id, project_id, current_user
            )
            return
        except Exception:
            logger.exception("Direct project RAG error")
    # «Библиотека» не вызывает global /search — только KB + memory ниже.
    document_search_trace = None
    kb_hits, mem_hits = ([], [])
    kb_id_name: dict = {}
    mem_id_name: dict = {}
    if proj_hits_for_trace and rag_client:
        trace_proj_map = proj_id_name
        if not trace_proj_map:
            try:
                trace_proj_map = build_rag_id_to_filename(
                    list(await rag_client.project_rag_list_documents(project_id) or [])
                )
            except Exception:
                logger.exception("Ошибка операции")
                trace_proj_map = {}
        hits_out, files_used = ([], set())
        for content, score, doc_id, chunk_idx in proj_hits_for_trace:
            if doc_id is None:
                continue
            try:
                fn = trace_proj_map.get(int(doc_id))
            except (TypeError, ValueError):
                fn = None
            if not fn:
                fn = f"doc_{doc_id}"
            files_used.add(fn)
            hits_out.append(
                {
                    "file": fn,
                    "anchor": f"chunk@{chunk_idx}({fn})",
                    "relevance": round(float(score), 4),
                    "content": (content or "")[:12000],
                    "chunkIndex": chunk_idx,
                    "documentId": doc_id,
                    "store": "project",
                }
            )
        if hits_out:
            document_search_trace = {
                "query": user_message,
                "strategy": rag_strategy,
                "sourceFiles": sorted(files_used),
                "hits": hits_out,
            }
    if rag_client and (sources.agent_kb or sources.memory):
        kb_rows: list = []
        mem_rows: list = []
        kb_hits: list = []
        mem_hits: list = []
        if sources.agent_kb:
            try:
                kb_rows = list(await rag_client.kb_list_documents() or [])
            except Exception:
                logger.exception("Ошибка операции")
                kb_rows = []
        if sources.memory:
            try:
                mem_rows = list(await rag_client.memory_rag_list_documents() or [])
            except Exception:
                logger.exception("Ошибка операции")
                mem_rows = []
        if sources.agent_kb:
            try:
                kb_hits = list(
                    await kb_search_agent_documents(
                        rag_client,
                        user_message,
                        agent_kb_doc_ids or [],
                        k=get_rag_chat_top_k(),
                        strategy=rag_strategy,
                    )
                    or []
                )
            except RagReindexInProgress:
                await _notify_reindex_wait(sio, sid)
                await _abort_chat_reindex(
                    sio, sid, conversation_id, project_id, current_user
                )
                return
            except Exception:
                logger.exception("KB search error")
            kb_hits = filter_rag_hits_by_score(kb_hits, min_sim)
        if sources.memory:
            try:
                mem_hits = list(
                    await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
                    or []
                )
            except RagReindexInProgress:
                await _notify_reindex_wait(sio, sid)
                await _abort_chat_reindex(
                    sio, sid, conversation_id, project_id, current_user
                )
                return
            except Exception:
                logger.exception("memory_rag search error")
            mem_hits = filter_rag_hits_by_score(mem_hits, min_sim)
        kb_id_name = build_rag_id_to_filename(kb_rows)
        mem_id_name = build_rag_id_to_filename(mem_rows)
        hits_out = document_search_trace["hits"] if document_search_trace else []
        files_used = set(document_search_trace["sourceFiles"]) if document_search_trace else set()
        for content, score, doc_id, chunk_idx in kb_hits:
            if doc_id is None:
                continue
            try:
                fn = kb_id_name.get(int(doc_id))
            except (TypeError, ValueError):
                fn = None
            if not fn:
                fn = f"doc_{doc_id}"
            files_used.add(fn)
            hits_out.append(
                {
                    "file": fn,
                    "anchor": f"chunk@{chunk_idx}({fn})",
                    "relevance": round(float(score), 4),
                    "content": (content or "")[:12000],
                    "chunkIndex": chunk_idx,
                    "documentId": doc_id,
                    "store": "kb",
                }
            )
        for content, score, doc_id, chunk_idx in mem_hits:
            if doc_id is None:
                continue
            try:
                fn = mem_id_name.get(int(doc_id))
            except (TypeError, ValueError):
                fn = None
            if not fn:
                fn = f"doc_{doc_id}"
            files_used.add(fn)
            hits_out.append(
                {
                    "file": fn,
                    "anchor": f"chunk@{chunk_idx}({fn})",
                    "relevance": round(float(score), 4),
                    "content": (content or "")[:12000],
                    "chunkIndex": chunk_idx,
                    "documentId": doc_id,
                    "store": "memory",
                }
            )
        document_search_trace = {
            "query": user_message,
            "strategy": rag_strategy,
            "sourceFiles": sorted(files_used),
            "hits": hits_out,
        }
    for hits_list, prefix, idnm, store_lbl in [
        (kb_hits, "База Знаний (постоянные документы)", kb_id_name, "kb (direct)"),
        (mem_hits, "Документы из настроек (библиотека памяти)", mem_id_name, "memory (direct)"),
    ]:
        if hits_list:
            parts, _m = format_rag_fragments(
                hits_list, idnm, max_chars=10000, store_label=store_lbl, include_chunk_meta=False
            )
            final_message = f"""{prefix}:
{''.join(parts)}

{final_message}"""
            context_added = True
    if inline_context:
        inline_block = f"""[Прикреплённый документ]
{inline_context}"""
        if final_message != user_message:
            final_message = f"{inline_block}\n\n{final_message}"
        else:
            final_message = f"""{inline_block}

[Вопрос пользователя]
{user_message}"""
        context_added = True
        logger.info(
            f"[direct inline_context] {len(inline_context)} символов, RAG-контекст {('совмещён' if final_message != inline_block else 'не применялся')}"
        )
    eff_model_path = agent_profile["model_path"] or get_current_model_path()
    base_system_prompt = agent_profile["system_prompt"] or ""
    user_cpm = await get_user_prompt_manager((current_user or {}).get("user_id"))
    if user_cpm is None:
        user_cpm = context_prompt_manager
    if user_cpm:
        eff_system_prompt = user_cpm.resolve_chat_system_prompt(
            eff_model_path,
            agent_system_prompt=base_system_prompt,
            project_instructions=project_instructions,
        )
        if project_instructions and project_instructions.strip():
            logger.debug(f"[direct] project_instructions применены к system_prompt (project={project_id})")
    elif project_instructions and project_instructions.strip():
        if base_system_prompt:
            eff_system_prompt = f"{project_instructions.strip()}\n\n{base_system_prompt}"
        else:
            eff_system_prompt = project_instructions.strip()
        logger.debug(f"[direct] project_instructions применены к system_prompt (project={project_id})")
    else:
        eff_system_prompt = base_system_prompt or None
    feedback_block = await build_user_feedback_system_block(
        (current_user or {}).get("user_id"),
        conversation_id=conversation_id,
    )
    eff_system_prompt = merge_feedback_into_system_prompt(eff_system_prompt, feedback_block)
    if context_added:
        eff_system_prompt = merge_strict_rag_system_prompt(
            eff_system_prompt, rag_override=runtime_rag_system_prompt() or None
        )
    canned = await maybe_rag_no_evidence_message(
        rag_client,
        block_when_no_evidence=rag_block,
        context_added=context_added,
        project_id=project_id,
        use_kb_rag=use_kb_rag,
        use_memory_library_rag=sources.memory,
        use_agent_scoped_kb=sources.agent_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
    )
    _terminal_chat_inference_banner(
        sid=sid,
        conversation_id=conversation_id,
        user_preview=final_message,
        mode_label="Прямой чат с LLM (одна модель)"
        + (" - параметры из выбранного агента" if agent_profile["model_path"] else ""),
        model_path_for_call=eff_model_path,
        extra_line="RAG/KB уже учтены в final_message при необходимости."
        + (" [RAG: ответ без LLM — нет релевантных фрагментов]" if canned else ""),
        enable_thinking=enable_thinking,
    )
    tool_ids = resolve_chat_tool_ids(data.get("tool_ids") or data.get("mcp_tool_ids"))
    mcp_result = None
    mcp_tool_events: list = []
    if not canned and tool_ids and current_user:
        try:
            from backend.mcp.chat_integration import run_mcp_for_chat

            async def _mcp_event_cb(payload):
                mcp_tool_events.append(dict(payload))
                await sio.emit("chat_mcp_event", payload, room=sid)

            mcp_result = await run_mcp_for_chat(
                tool_ids=tool_ids,
                user_message=final_message,
                history=history,
                system_prompt=eff_system_prompt,
                model_path=eff_model_path,
                user=current_user,
                chat_id=conversation_id,
                message_id=data.get("message_id"),
                temperature=agent_profile.get("temperature") or 0.7,
                max_tokens=max(agent_profile.get("max_tokens") or 1024, 4096),
                enable_thinking=enable_thinking,
                emit_event=_mcp_event_cb,
            )
        except Exception:
            logger.exception("MCP agent loop error")
    reasoning_trace_accumulated = ""

    def _direct_stream_cb(chunk, acc, stream_role="content"):
        nonlocal reasoning_trace_accumulated
        if stream_role == "reasoning":
            if isinstance(acc, str) and acc:
                reasoning_trace_accumulated = acc
            elif isinstance(chunk, str) and chunk:
                reasoning_trace_accumulated += chunk
        return sync_stream_cb(chunk, acc, stream_role)

    def _run_ask(stream, cb):
        return ask_agent(
            final_message,
            history=history,
            max_tokens=agent_profile["max_tokens"],
            streaming=stream,
            stream_callback=cb,
            model_path=eff_model_path,
            custom_prompt_id=None,
            images=images,
            system_prompt=eff_system_prompt,
            temperature=agent_profile["temperature"],
            enable_thinking=enable_thinking,
        )

    if canned:
        response = canned
        if streaming:
            await sio.emit("chat_chunk", {"chunk": canned, "accumulated": canned}, room=sid)
    elif mcp_result is not None:
        response = mcp_result.content
        if streaming and response:
            await sio.emit("chat_chunk", {"chunk": response, "accumulated": response}, room=sid)
        logger.info(
            "MCP agent loop: mode=%s tools=%s iterations=%s",
            mcp_result.mode,
            mcp_result.tool_calls_executed,
            mcp_result.iterations,
        )
    elif streaming:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            response = await asyncio.get_event_loop().run_in_executor(
                ex, _make_ctx_runner(lambda: _run_ask(True, _direct_stream_cb))
            )
        if response is None or stop_generation_flags.get(sid, False):
            stop_generation_flags[sid] = False
            await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
            return
    else:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            response = await asyncio.get_event_loop().run_in_executor(
                ex, _make_ctx_runner(lambda: _run_ask(False, None))
            )
    if context_added and (not canned) and response:
        response = await maybe_replace_ungrounded(final_message[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE)
    if stop_generation_flags.get(sid, False):
        stop_generation_flags[sid] = False
        await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
        return
    stop_generation_flags[sid] = False
    # Сначала отдаём ответ в UI: зависание Mongo на regenerate не должно
    # блокировать стрим и кнопку «Стоп».
    payload = {
        "response": response,
        "timestamp": datetime.now().isoformat(),
        "was_streaming": streaming,
    }
    if document_search_trace:
        payload["document_search"] = document_search_trace
    if mcp_tool_events:
        payload["mcp_tool_calls"] = mcp_tool_events
    await sio.emit("chat_complete", payload, room=sid)
    rag_metrics = await _compute_and_emit_rag_metrics(
        sio,
        sid,
        query=user_message,
        document_search_trace=document_search_trace,
        context_text=final_message,
        answer=response if isinstance(response, str) else "",
        context_added=context_added,
    )
    try:
        meta = {"document_search": document_search_trace} if document_search_trace else None
        if rag_metrics:
            meta = dict(meta or {})
            meta["rag_metrics"] = rag_metrics
        if reasoning_trace_accumulated.strip():
            meta = dict(meta or {})
            meta["reasoning_content"] = reasoning_trace_accumulated.strip()
        if mcp_tool_events:
            meta = dict(meta or {})
            meta["mcp_tool_calls"] = mcp_tool_events
        if mcp_result and getattr(mcp_result, "attachments", None):
            meta = dict(meta or {})
            meta["mcp_attachments"] = mcp_result.attachments
        regen = _regen_save_kwargs(data)
        await save_assistant_response(
            response,
            meta,
            conversation_id=conversation_id,
            user_id=(current_user or {}).get("user_id"),
            project_id=project_id,
            **regen,
        )
    except Exception as e:
        logger.warning(f"Не удалось сохранить ответ: {e}")
