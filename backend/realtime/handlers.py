"""
socket_handlers.py - все @sio.event обработчики Socket.IO

Регистрируется в main.py:
    from backend.socket_handlers import register_handlers
    register_handlers(sio)
"""

import asyncio
import concurrent.futures
import logging
import os
from datetime import datetime

import backend.app_state as state
from backend.auth.jwt_handler import decode_token
from backend.app_state import (
    ask_agent, save_dialog_entry, get_recent_dialog_history,
    rag_client, get_agent_orchestrator,
    reload_model_by_path,
    stop_generation_flags, stop_transcription_flags,
    get_current_model_path,
    get_rag_chat_top_k,
)
from backend.llm_providers import get_registry
from backend.realtime.helpers import (
    _is_structure_query,
    _terminal_chat_inference_banner,
    _resolve_agent_chat_params,
    kb_search_agent_documents,
)
from backend.realtime.rag_evidence import (
    build_rag_id_to_filename,
    filter_rag_hits_by_score,
    format_rag_fragments,
    maybe_rag_no_evidence_message,
    rag_document_label,
    rag_guard_env,
)
from backend.rag_query.post_generation import maybe_replace_ungrounded
from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE, merge_strict_rag_system_prompt

logger = logging.getLogger(__name__)
_VALID_RAG_STRATEGIES = {"auto", "hierarchical", "hybrid", "standard", "graph"}


async def _get_conversation_project_id(conversation_id: str) -> "Optional[str]":
    """Возвращает project_id диалога из MongoDB, или None если диалог не привязан к проекту."""
    if not conversation_id:
        return None
    try:
        from backend.database.init_db import get_conversation_repository
        repo = get_conversation_repository()
        conv = await repo.get_conversation(conversation_id)
        return conv.project_id if conv else None
    except Exception as e:
        logger.debug(f"_get_conversation_project_id({conversation_id}): {e}")
        return None


def register_handlers(sio):
    """Регистрирует все Socket.IO обработчики на переданный sio-сервер"""
    sid_tokens: dict[str, str] = {}

    @sio.event
    async def connect(sid, environ, auth):
        token = None
        if isinstance(auth, dict):
            token = auth.get("token")
        if not token:
            logger.warning(f"Socket.IO auth failed: token missing sid={sid}")
            return False
        try:
            decode_token(token)
        except Exception as e:
            logger.warning(f"Socket.IO auth failed: sid={sid} error={e}")
            return False

        sid_tokens[sid] = token
        logger.info(f"Socket.IO client connected: {sid}")
        stop_generation_flags[sid] = False
        await sio.emit("connected", {"data": "Connected to astrachat"}, room=sid)

    @sio.event
    async def disconnect(sid):
        logger.info(f"Socket.IO client disconnected: {sid}")
        stop_generation_flags.pop(sid, None)
        sid_tokens.pop(sid, None)

    @sio.event
    async def ping(sid, data):
        try:
            await sio.emit(
                "pong",
                {"timestamp": data.get("timestamp", 0), "server_time": datetime.now().isoformat()},
                room=sid,
            )
        except Exception as e:
            logger.error(f"Ошибка обработки ping: {e}")

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

    # -- chat_message
    @sio.event
    async def chat_message(sid, data):
        if not ask_agent or not save_dialog_entry:
            await sio.emit("chat_error", {"error": "AI services not available"}, room=sid)
            return

        token = sid_tokens.get(sid)
        if not token:
            await sio.emit("chat_error", {"error": "Не авторизован. Выполните вход снова."}, room=sid)
            return
        try:
            user_data = decode_token(token)
        except Exception:
            await sio.emit(
                "chat_error",
                {"error": "Сессия завершена: выполнен вход в другом окне. Обновите страницу и войдите снова."},
                room=sid,
            )
            return

        def session_still_valid() -> bool:
            current_token = sid_tokens.get(sid)
            if not current_token:
                return False
            try:
                decode_token(current_token)
                return True
            except Exception:
                return False

        try:
            current_user_id = user_data.get("user_id")
            user_message = data.get("message", "")
            streaming = data.get("streaming", True)
            stop_generation_flags[sid] = False
            user_message_id = data.get("message_id", None)
            conversation_id = data.get("conversation_id", None)
            use_kb_rag = bool(data.get("use_kb_rag", False))
            use_memory_library_rag = bool(data.get("use_memory_library_rag", False))
            requested_rag_strategy = str(data.get("rag_strategy") or "").strip().lower()
            effective_rag_strategy = (
                requested_rag_strategy
                if requested_rag_strategy in _VALID_RAG_STRATEGIES
                else state.current_rag_strategy
            )
            agent_profile = await _resolve_agent_chat_params(data.get("agent_id"))
            agent_kb_enabled = bool(agent_profile.get("file_search_enabled"))
            agent_kb_doc_ids = agent_profile.get("kb_document_ids") or []
            use_agent_scoped_kb = (
                agent_kb_enabled
                and isinstance(agent_kb_doc_ids, list)
                and len(agent_kb_doc_ids) > 0
            )

            orchestrator_early = get_agent_orchestrator()
            use_multi_llm_early = orchestrator_early and orchestrator_early.get_mode() == "multi-llm"
            multi_slot_regen = str(data.get("multi_llm_slot_regenerate") or "").strip()
            skip_user_save = bool(data.get("regenerate")) and use_multi_llm_early and bool(multi_slot_regen)

            if conversation_id:
                import backend.database.memory_service as mem_mod
                mem_mod.current_conversation_id = conversation_id

            # Получаем project_id из payload (фронтенд знает это немедленно),
            # если не пришёл — fallback на поиск в MongoDB
            project_id = data.get("project_id") or None
            if project_id:
                logger.debug(f"[chat_message] project_id из payload: {project_id}")
            else:
                project_id = await _get_conversation_project_id(conversation_id)
                if project_id:
                    logger.debug(f"[chat_message] project_id из MongoDB: {project_id}")

            project_memory = data.get("project_memory") or "default"       # 'default' | 'project-only'
            project_instructions = data.get("project_instructions") or ""  # строка инструкций проекта

            # История: project-only — только диалоги внутри проекта, иначе — текущий диалог
            if project_id and project_memory == "project-only":
                from backend.database.memory_service import get_project_memory_history
                history = await get_project_memory_history(
                    project_id, max_entries=state.memory_max_messages
                )
                logger.debug(f"[chat_message] project-only история: {len(history)} сообщений из проекта {project_id}")
            else:
                history = await get_recent_dialog_history(
                    max_entries=state.memory_max_messages, conversation_id=conversation_id
                )

            # Сохраняем сообщение пользователя (с привязкой к проекту, если нужно).
            # Перегенерация одного столбца multi-LLM — без дубля user в истории.
            if not skip_user_save:
                try:
                    if project_id:
                        from backend.database.memory_service import save_dialog_entry_to_project
                        await save_dialog_entry_to_project(
                            "user", user_message, project_id, conversation_id, user_message_id, current_user_id
                        )
                    else:
                        await save_dialog_entry("user", user_message, None, user_message_id, conversation_id, current_user_id)
                except RuntimeError as e:
                    if "MongoDB" in str(e):
                        await sio.emit("chat_error", {"error": "MongoDB недоступен."}, room=sid)
                        return
                    raise

            orchestrator = get_agent_orchestrator()
            use_agent_mode = orchestrator and orchestrator.get_mode() == "agent"
            use_multi_llm_mode = orchestrator and orchestrator.get_mode() == "multi-llm"
            chat_mode = "multi-llm" if use_multi_llm_mode else ("agent" if use_agent_mode else "direct")
            logger.info(
                "[RAG] chat_message mode=%s effective_strategy=%s payload_rag_strategy=%r "
                "settings_rag_strategy=%s agentic_rag_enabled=%s "
                "use_kb_rag=%s use_memory_library_rag=%s use_agent_scoped_kb=%s project_id=%s",
                chat_mode,
                effective_rag_strategy,
                requested_rag_strategy or "",
                getattr(state, "current_rag_strategy", "auto"),
                getattr(state, "agentic_rag_enabled", True),
                use_kb_rag,
                use_memory_library_rag,
                use_agent_scoped_kb,
                project_id,
            )

            # -- stream helpers
            async def async_stream_cb(chunk, acc):
                try:
                    await sio.emit("chat_chunk", {"chunk": chunk, "accumulated": acc}, room=sid)
                except Exception:
                    pass

            loop = asyncio.get_event_loop()

            def sync_stream_cb(chunk, acc):
                if stop_generation_flags.get(sid, False) or not session_still_valid():
                    return False
                asyncio.run_coroutine_threadsafe(async_stream_cb(chunk, acc), loop)
                return True

            # -- MULTI-LLM mode
            if use_multi_llm_mode:
                slot = str(data.get("multi_llm_slot_regenerate") or "").strip()
                models_subset = [slot] if (bool(data.get("regenerate")) and slot) else None
                await _handle_multi_llm(
                    sio, sid, data, user_message, streaming, conversation_id,
                    use_kb_rag, use_memory_library_rag, loop,
                    use_agent_scoped_kb, agent_kb_doc_ids,
                    project_id=project_id,
                    project_instructions=project_instructions,
                    rag_strategy=effective_rag_strategy,
                    models_subset=models_subset,
                    session_still_valid=session_still_valid,
                )
                return

            # -- AGENT mode
            if use_agent_mode:
                await _handle_agent_mode(
                    sio, sid, data, user_message, streaming, conversation_id,
                    history, use_kb_rag, use_memory_library_rag, orchestrator,
                    use_agent_scoped_kb, agent_kb_doc_ids,
                    agent_profile=agent_profile,
                    project_id=project_id,
                    project_instructions=project_instructions,
                    rag_strategy=effective_rag_strategy,
                    session_still_valid=session_still_valid,
                    user_id=current_user_id,
                )
                return

            # -- DIRECT mode
            await _handle_direct(
                sio, sid, data, user_message, streaming, conversation_id,
                history, use_kb_rag, use_memory_library_rag,
                agent_profile, sync_stream_cb, loop,
                use_agent_scoped_kb, agent_kb_doc_ids,
                project_id=project_id,
                project_instructions=project_instructions,
                rag_strategy=effective_rag_strategy,
                session_still_valid=session_still_valid,
                user_id=current_user_id,
            )

        except Exception as e:
            logger.error(f"Socket.IO chat error: {e}", exc_info=True)
            try:
                await sio.emit("chat_error", {"error": str(e)}, room=sid)
            except Exception:
                pass
        finally:
            stop_generation_flags[sid] = False


# -- внутренние обработчики режимов

async def _handle_multi_llm(
    sio, sid, data, user_message, streaming, conversation_id,
    use_kb_rag, use_memory_library_rag, loop,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    models_subset=None,
    session_still_valid=lambda: True,
):
    orchestrator = get_agent_orchestrator()
    multi_llm_models = orchestrator.get_multi_llm_models()
    if not multi_llm_models:
        await sio.emit("chat_error", {"error": "Модели не выбраны"}, room=sid)
        return
    if models_subset is not None:
        allowed = set(multi_llm_models)
        multi_llm_models = [m for m in models_subset if m in allowed]
        if not multi_llm_models:
            await sio.emit(
                "chat_error",
                {"error": "Указанная модель не входит в список multi-LLM"},
                room=sid,
            )
            return

    _terminal_chat_inference_banner(
        sid=sid, conversation_id=conversation_id, user_preview=user_message,
        mode_label=f"MULTI-LLM - модели: {', '.join(multi_llm_models)}",
        extra_line="Ниже для каждой модели - отдельный блок перед вызовом LLM.",
    )

    min_sim, rag_block = rag_guard_env()
    context_added = False
    global_attempted = False
    final_user_message = user_message

    # RAG из документов проекта (приоритет — специфичен для текущего проекта)
    if rag_client and project_id:
        try:
            proj_rows = list(await rag_client.project_rag_list_documents(project_id) or [])
            proj_id_name = build_rag_id_to_filename(proj_rows)
            proj_hits = await rag_client.project_rag_search(
                user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
            )
            proj_hits = filter_rag_hits_by_score(proj_hits, min_sim)
            if proj_hits:
                parts, _ = format_rag_fragments(
                    proj_hits,
                    proj_id_name,
                    max_chars=12000,
                    store_label=f"project({project_id})/multi-llm",
                )
                final_user_message = (
                    f"Документы проекта (RAG):\n{chr(10).join(parts)}\n"
                    f"Вопрос: {user_message}"
                )
                context_added = True
                logger.info(f"[multi-llm project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except Exception as e:
            logger.error(f"multi-llm project RAG error: {e}")

    # Глобальный RAG контекст (если нет контекста из проекта)
    if rag_client and final_user_message == user_message:
        global_attempted = True
        try:
            glob_rows = list(await rag_client.list_documents() or [])
            glob_id_name = build_rag_id_to_filename(glob_rows)
            hits = await rag_client.search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
            hits = filter_rag_hits_by_score(hits, min_sim)
            if hits:
                parts, _ = format_rag_fragments(
                    hits,
                    glob_id_name,
                    max_chars=12000,
                    store_label="global/multi-llm",
                )
                final_user_message = f"Контекст: {chr(10).join(parts)}\nВопрос: {user_message}"
                context_added = True
        except Exception as e:
            logger.error(f"multi-llm RAG error: {e}")

    # KB (глобальная БЗ или только документы выбранного агента) / memory_rag
    if rag_client and (use_kb_rag or use_agent_scoped_kb):
        prefix = "База Знаний (постоянные документы)"
        try:
            kb_id_name = build_rag_id_to_filename(
                list(await rag_client.kb_list_documents() or [])
            )
            if use_agent_scoped_kb:
                hits = await kb_search_agent_documents(
                    rag_client, user_message, agent_kb_doc_ids or [], k=get_rag_chat_top_k()
                )
            else:
                hits = await rag_client.kb_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
            hits = filter_rag_hits_by_score(list(hits or []), min_sim)
            if hits:
                parts, _ = format_rag_fragments(
                    hits,
                    kb_id_name,
                    max_chars=10000,
                    store_label="kb/multi-llm",
                    include_chunk_meta=False,
                    truncate_marker="\n...\n",
                )
                final_user_message = f"{prefix}:\n{''.join(parts)}\n\n{final_user_message}"
                context_added = True
        except Exception as e:
            logger.error(f"multi-llm kb_search: {e}")

    if use_memory_library_rag and rag_client:
        try:
            mem_id_name = build_rag_id_to_filename(
                list(await rag_client.memory_rag_list_documents() or [])
            )
            hits = await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
            hits = filter_rag_hits_by_score(list(hits or []), min_sim)
            prefix = "Документы из настроек (библиотека памяти)"
            if hits:
                parts, _ = format_rag_fragments(
                    hits,
                    mem_id_name,
                    max_chars=10000,
                    store_label="memory/multi-llm",
                    include_chunk_meta=False,
                    truncate_marker="\n...\n",
                )
                final_user_message = f"{prefix}:\n{''.join(parts)}\n\n{final_user_message}"
                context_added = True
        except Exception as e:
            logger.error(f"multi-llm memory_rag_search: {e}")

    eff_system_prompt = project_instructions.strip() if project_instructions else None
    if context_added:
        eff_system_prompt = merge_strict_rag_system_prompt(eff_system_prompt)

    canned = await maybe_rag_no_evidence_message(
        rag_client,
        block_when_no_evidence=rag_block,
        context_added=context_added,
        global_attempted=global_attempted,
        project_id=project_id,
        use_kb_rag=use_kb_rag,
        use_memory_library_rag=use_memory_library_rag,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        implicit_global_corpus=False,
    )
    if canned:
        # Иначе фронт не получит total_models (ожидается в multi_llm_start) и зависнет индикатор загрузки
        if multi_llm_models:
            await sio.emit(
                "multi_llm_start",
                {
                    "model": multi_llm_models[0],
                    "models": multi_llm_models,
                    "total_models": len(multi_llm_models),
                },
                room=sid,
            )
        for i, model_name in enumerate(multi_llm_models):
            await sio.emit(
                "multi_llm_complete",
                {
                    "model": model_name,
                    "response": canned,
                    "error": False,
                    "index": i,
                    "total": len(multi_llm_models),
                },
                room=sid,
            )
        return

    n_models = len(multi_llm_models)

    async def _gen_one(model_name: str):
        idx = multi_llm_models.index(model_name)

        async def _emit_complete(res: dict) -> dict:
            # Сразу после готовности этой модели — иначе фронт ждёт gather по всем и «вечно генерирует»
            await sio.emit(
                "multi_llm_complete",
                {
                    "model": res.get("model", model_name),
                    "response": res.get("response", "") or "",
                    "error": bool(res.get("error", False)),
                    "index": idx,
                    "total": n_models,
                },
                room=sid,
            )
            return res

        try:
            await sio.emit(
                "multi_llm_start",
                {
                    "model": model_name,
                    "models": multi_llm_models,
                    "total_models": n_models,
                },
                room=sid,
            )

            # Разрешаем модель через ProviderRegistry. Путь может быть:
            #   - новый формат: <provider_id>/<model_id>
            #   - legacy: llm-svc://host/model, llm-svc://model, models/<name>
            registry = await get_registry()
            provider, model_id = registry.resolve(model_name)
            if not model_id:
                return await _emit_complete(
                    {"model": model_name, "response": f"Некорректный путь модели: {model_name!r}", "error": True}
                )

            # Гарантируем, что модель доступна. Для llm-svc это может вызвать
            # POST /v1/models/load, сериализованный внутренним _switch_lock
            # провайдера (параллельные gather-слоты не мешают друг другу).
            # Для vLLM/Ollama/OpenAI это no-op проверка наличия модели.
            ok = await provider.ensure_model_loaded(model_id)
            if not ok:
                return await _emit_complete(
                    {
                        "model": model_name,
                        "response": (
                            f"Модель {model_id!r} недоступна на провайдере "
                            f"{provider.id!r} (kind={provider.kind}). "
                            f"Проверьте, что модель запущена на стороне сервера."
                        ),
                        "error": True,
                    }
                )

            # Собираем сообщения через LLMService.prepare_messages (там учтены
            # системный промпт и история; история здесь пустая — по дизайну
            # multi-LLM без контекста предыдущих ответов).
            from backend.llm_client import get_llm_service
            service = await get_llm_service()
            messages = service.prepare_messages(
                prompt=final_user_message,
                history=None,
                system_prompt=eff_system_prompt,
            )

            # stream-callback: emit в socket без блокировки текущей корутины
            # (create_task ставит emit в очередь loop'а; loop обслуживает её
            # между чанками stream_chat).
            def _model_stream_cb(chunk: str, acc: str) -> bool:
                if stop_generation_flags.get(sid, False) or not session_still_valid():
                    return False
                loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(
                        sio.emit(
                            "multi_llm_chunk",
                            {"model": model_name, "chunk": chunk, "accumulated": acc},
                            room=sid,
                        ),
                        loop=loop,
                    )
                )
                return True

            if streaming:
                resp = await provider.stream_chat(
                    messages=messages,
                    model=model_id,
                    callback=_model_stream_cb,
                    temperature=0.7,
                    max_tokens=1024,
                )
            else:
                resp = await provider.chat(
                    messages=messages,
                    model=model_id,
                    temperature=0.7,
                    max_tokens=1024,
                )

            if context_added and isinstance(resp, str) and resp.strip():
                resp = await maybe_replace_ungrounded(
                    final_user_message[:20000], resp, RAG_STRICT_NOT_FOUND_MESSAGE
                )
            return await _emit_complete(
                {
                    "model": model_name,
                    "response": resp if isinstance(resp, str) else "",
                    "error": False,
                }
            )
        except Exception as e:
            logger.exception("multi-llm: ошибка для модели %s", model_name)
            return await _emit_complete(
                {"model": model_name, "response": f"Ошибка: {e}", "error": True}
            )

    # Параллельные запросы: провайдеры сами сериализуют load-операции внутри
    # себя (LlmSvcProvider._switch_lock). Никаких глобальных локов.
    results: list = await asyncio.gather(*[_gen_one(m) for m in multi_llm_models], return_exceptions=True)

    # Успешные пути уже вызвали multi_llm_complete внутри _gen_one; здесь только сбой gather
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


async def _handle_agent_mode(
    sio, sid, data, user_message, streaming, conversation_id,
    history, use_kb_rag, use_memory_library_rag, orchestrator,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    agent_profile=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    session_still_valid=lambda: True,
    user_id: str = "default_user",
):
    await sio.emit("chat_thinking", {"status": "processing", "message": "Обрабатываю запрос через агентную архитектуру..."}, room=sid)
    agentic_rag_enabled = bool(getattr(state, "agentic_rag_enabled", True))

    ap = agent_profile or {}
    eff_model_path = ap.get("model_path") or get_current_model_path()

    async def agent_stream_cb(chunk, acc):
        if stop_generation_flags.get(sid, False) or not session_still_valid():
            return False
        await sio.emit("chat_chunk", {"chunk": chunk, "accumulated": acc}, room=sid)
        return True

    try:
        from backend.tools.prompt_tools import set_tool_context
    except ModuleNotFoundError:
        from tools.prompt_tools import set_tool_context

    context = {
        "history": history, "user_message": user_message,
        "selected_model": eff_model_path, "socket_id": sid, "streaming": streaming,
        "sio": sio, "stream_callback": agent_stream_cb if streaming else None,
        "_main_event_loop": asyncio.get_running_loop(),
        "project_instructions": project_instructions or "",
        "project_id": project_id,
        "rag_strategy": rag_strategy,
        "agentic_rag_enabled": agentic_rag_enabled,
        "agentic_max_iterations": int(getattr(state, "agentic_max_iterations", 2)),
    }
    set_tool_context(context)

    effective_message = user_message
    # Инструкции проекта добавляются как системный префикс к сообщению пользователя
    if project_instructions and project_instructions.strip():
        effective_message = f"[Инструкции проекта: {project_instructions.strip()}]\n\n{user_message}"

    # Legacy pre-retrieval (fallback, если Agentic RAG отключен)
    if (not agentic_rag_enabled) and rag_client and project_id:
        try:
            proj_hits = await rag_client.project_rag_search(
                user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
            ) or []
            if proj_hits:
                parts, tl = [], 0
                for i, (c, s, did, ch) in enumerate(proj_hits, 1):
                    frag = f"Документы проекта {i} (doc={did}): {c}\n"
                    if tl + len(frag) > 8000:
                        break
                    parts.append(frag)
                    tl += len(frag)
                effective_message = f"Документы проекта (RAG):\n{''.join(parts)}\n\n{effective_message}"
                logger.info(f"[agent project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except Exception as e:
            logger.error(f"Agent project RAG error: {e}")

    if (not agentic_rag_enabled) and rag_client and (use_kb_rag or use_agent_scoped_kb):
        prefix = "База Знаний (документы)"
        try:
            if use_agent_scoped_kb:
                hits = await kb_search_agent_documents(
                    rag_client, user_message, agent_kb_doc_ids or [], k=get_rag_chat_top_k()
                ) or []
            else:
                hits = await rag_client.kb_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy) or []
            if hits:
                parts, tl = [], 0
                for i, (c, s, did, ch) in enumerate(hits, 1):
                    frag = f"{prefix} {i} (doc={did}): {c}\n"
                    if tl + len(frag) > 8000:
                        break
                    parts.append(frag)
                    tl += len(frag)
                effective_message = f"{prefix}:\n{''.join(parts)}\n\n{effective_message}"
        except Exception as e:
            logger.error(f"Agent kb_search: {e}")

    if (not agentic_rag_enabled) and use_memory_library_rag and rag_client:
        prefix = "Документы из настроек (библиотека памяти)"
        try:
            hits = await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy) or []
            if hits:
                parts, tl = [], 0
                for i, (c, s, did, ch) in enumerate(hits, 1):
                    frag = f"{prefix} {i} (doc={did}): {c}\n"
                    if tl + len(frag) > 8000:
                        break
                    parts.append(frag)
                    tl += len(frag)
                effective_message = f"{prefix}:\n{''.join(parts)}\n\n{effective_message}"
        except Exception as e:
            logger.error(f"Agent memory_rag_search: {e}")

    _terminal_chat_inference_banner(
        sid=sid, conversation_id=conversation_id, user_preview=user_message,
        mode_label="Оркестратор агентов (agent architecture)",
        model_path_for_call=eff_model_path,
        extra_line="Базовая модель на сервере - та, что ниже; оркестратор может дергать LLM несколько раз.",
    )

    try:
        response = await orchestrator.process_message(effective_message, history=history, context=context)

        if stop_generation_flags.get(sid, False) or not session_still_valid():
            stop_generation_flags[sid] = False
            await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
            return

        if response is None:
            await sio.emit("chat_error", {"error": "Не удалось получить ответ от агента"}, room=sid)
            return

        await sio.emit("chat_complete", {
            "response": response, "timestamp": datetime.now().isoformat(), "was_streaming": streaming,
        }, room=sid)
    except Exception as e:
        logger.error(f"Ошибка оркестратора: {e}", exc_info=True)
        await sio.emit("chat_error", {"error": str(e)}, room=sid)
        stop_generation_flags[sid] = False
        return

    try:
        if project_id:
            from backend.database.memory_service import save_dialog_entry_to_project
            await save_dialog_entry_to_project("assistant", response, project_id, conversation_id, None, user_id)
        else:
            await save_dialog_entry("assistant", response, None, None, conversation_id, user_id)
    except Exception as e:
        logger.warning(f"Не удалось сохранить ответ агента: {e}")


async def _handle_direct(
    sio, sid, data, user_message, streaming, conversation_id,
    history, use_kb_rag, use_memory_library_rag,
    agent_profile, sync_stream_cb, loop,
    use_agent_scoped_kb=False,
    agent_kb_doc_ids=None,
    project_id=None,
    project_instructions=None,
    rag_strategy="auto",
    session_still_valid=lambda: True,
    user_id: str = "default_user",
):
    min_sim, rag_block = rag_guard_env()
    context_added = False
    global_attempted = False
    final_message = user_message
    images = None
    proj_hits_for_trace = []  # сохраняем для document_search_trace
    global_hits_for_trace: list = []  # глобальная библиотека (не project/kb/memory) — для трейса в UI

    proj_id_name: dict = {}
    glob_id_name: dict = {}
    if rag_client and project_id:
        try:
            proj_rows = list(await rag_client.project_rag_list_documents(project_id) or [])
            proj_id_name = build_rag_id_to_filename(proj_rows)
        except Exception:
            pass

    # RAG из документов проекта (приоритет — специфичен для текущего проекта)
    if rag_client and project_id:
        try:
            proj_hits = await rag_client.project_rag_search(
                user_message, project_id=project_id, k=get_rag_chat_top_k(), strategy=rag_strategy
            )
            proj_hits = filter_rag_hits_by_score(proj_hits, min_sim)
            if proj_hits:
                if _is_structure_query(user_message):
                    seen = {(d, i) for _, _, d, i in proj_hits}
                    for doc_id in {d for _, _, d, _ in proj_hits if d is not None}:
                        try:
                            for c, sc, did, idx in await rag_client.get_document_start_chunks(doc_id, max_chunks=2):
                                if (did, idx) not in seen:
                                    proj_hits = [(c, sc, did, idx)] + proj_hits
                                    seen.add((did, idx))
                        except Exception:
                            pass
                parts, _ = format_rag_fragments(
                    proj_hits,
                    proj_id_name,
                    max_chars=12000,
                    store_label=f"project({project_id})/direct",
                )
                proj_context = "\n".join(parts)
                final_message = (
                    f"Документы проекта (RAG):\n{proj_context}\n"
                    f"Вопрос: {user_message}\n"
                    f"Ответь на основе этих документов. Перечисляй только то, что явно есть в фрагментах."
                )
                proj_hits_for_trace = proj_hits  # запомним для трейса
                context_added = True
                logger.info(f"[direct project_rag] {len(proj_hits)} фрагментов, project={project_id}")
        except Exception as e:
            logger.error(f"Direct project RAG error: {e}")

    # Глобальный RAG из загруженных документов (если нет контекста из проекта)
    if rag_client and final_message == user_message:
        global_attempted = True
        try:
            hits = await rag_client.search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy)
            try:
                glob_rows = list(await rag_client.list_documents() or [])
                glob_id_name = build_rag_id_to_filename(glob_rows)
            except Exception:
                pass
            hits = filter_rag_hits_by_score(hits, min_sim)
            if hits:
                if _is_structure_query(user_message):
                    seen = {(d, i) for _, _, d, i in hits}
                    for doc_id in {d for _, _, d, _ in hits if d is not None}:
                        try:
                            for c, sc, did, idx in await rag_client.get_document_start_chunks(doc_id, max_chunks=2):
                                if (did, idx) not in seen:
                                    hits = [(c, sc, did, idx)] + hits
                                    seen.add((did, idx))
                        except Exception:
                            pass
                global_hits_for_trace = list(hits)
                parts, _ = format_rag_fragments(
                    hits,
                    glob_id_name,
                    max_chars=12000,
                    store_label="global/direct",
                )
                doc_context = "\n".join(parts)
                final_message = (
                    f"Документы (RAG):\n{doc_context}\n"
                    f"Вопрос: {user_message}\n"
                    f"Ответь на основе этих документов. Перечисляй только то, что явно есть в фрагментах."
                )
                context_added = True
        except Exception as e:
            logger.error(f"Direct RAG error: {e}")

    # KB / memory / project-RAG trace
    document_search_trace = None
    kb_hits, mem_hits = [], []
    kb_id_name: dict = {}
    mem_id_name: dict = {}

    # Трейс project-RAG (всегда строим, если были хиты — вне зависимости от KB-флагов)
    if proj_hits_for_trace and rag_client:
        trace_proj_map = proj_id_name
        if not trace_proj_map:
            try:
                trace_proj_map = build_rag_id_to_filename(
                    list(await rag_client.project_rag_list_documents(project_id) or [])
                )
            except Exception:
                trace_proj_map = {}
        hits_out, files_used = [], set()
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
            hits_out.append({"file": fn, "anchor": f"chunk@{chunk_idx}({fn})",
                "relevance": round(float(score), 4), "content": (content or "")[:12000],
                "chunkIndex": chunk_idx, "documentId": doc_id, "store": "project"})
        if hits_out:
            document_search_trace = {
                "query": user_message,
                "strategy": rag_strategy,
                "sourceFiles": sorted(files_used),
                "hits": hits_out,
            }

    if rag_client and (use_kb_rag or use_agent_scoped_kb or use_memory_library_rag):
        kb_rows: list = []
        mem_rows: list = []
        kb_hits: list = []
        mem_hits: list = []
        if use_kb_rag or use_agent_scoped_kb:
            try:
                kb_rows = list(await rag_client.kb_list_documents() or [])
            except Exception:
                kb_rows = []
        if use_memory_library_rag:
            try:
                mem_rows = list(await rag_client.memory_rag_list_documents() or [])
            except Exception:
                mem_rows = []

        if use_kb_rag or use_agent_scoped_kb:
            try:
                if use_agent_scoped_kb:
                    kb_hits = list(
                        await kb_search_agent_documents(
                            rag_client, user_message, agent_kb_doc_ids or [], k=get_rag_chat_top_k()
                        )
                        or []
                    )
                else:
                    kb_hits = list(await rag_client.kb_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy) or [])
            except Exception as e:
                logger.error(f"KB search: {e}")
            kb_hits = filter_rag_hits_by_score(kb_hits, min_sim)
        if use_memory_library_rag:
            try:
                mem_hits = list(await rag_client.memory_rag_search(user_message, k=get_rag_chat_top_k(), strategy=rag_strategy) or [])
            except Exception as e:
                logger.error(f"memory_rag: {e}")
            mem_hits = filter_rag_hits_by_score(mem_hits, min_sim)

        kb_id_name = build_rag_id_to_filename(kb_rows)
        mem_id_name = build_rag_id_to_filename(mem_rows)

        # Если project-trace уже создан — дополняем его, иначе создаём новый
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
            hits_out.append({"file": fn, "anchor": f"chunk@{chunk_idx}({fn})",
                "relevance": round(float(score), 4), "content": (content or "")[:12000],
                "chunkIndex": chunk_idx, "documentId": doc_id, "store": "kb"})
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
            hits_out.append({"file": fn, "anchor": f"chunk@{chunk_idx}({fn})",
                "relevance": round(float(score), 4), "content": (content or "")[:12000],
                "chunkIndex": chunk_idx, "documentId": doc_id, "store": "memory"})
        document_search_trace = {
            "query": user_message,
            "strategy": rag_strategy,
            "sourceFiles": sorted(files_used),
            "hits": hits_out,
        }

    # Глобальный RAG (загрузки в /api/documents) — раньше не попадал в трейс → в UI не было PDF/файлов из глобального корпуса
    if global_hits_for_trace and rag_client:
        trace_glob_map = glob_id_name if glob_id_name else {}
        if not trace_glob_map:
            try:
                trace_glob_map = build_rag_id_to_filename(
                    list(await rag_client.list_documents() or [])
                )
            except Exception:
                trace_glob_map = {}
        hits_out = list(document_search_trace["hits"]) if document_search_trace else []
        files_used = set(document_search_trace["sourceFiles"]) if document_search_trace else set()
        for content, score, doc_id, chunk_idx in global_hits_for_trace:
            if doc_id is None:
                continue
            try:
                fn = trace_glob_map.get(int(doc_id))
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
                    "store": "global",
                }
            )
        if hits_out:
            document_search_trace = {
                "query": user_message,
                "strategy": rag_strategy,
                "sourceFiles": sorted(files_used),
                "hits": hits_out,
            }

    for hits_list, prefix, idnm, label in [
        (kb_hits, "База Знаний (постоянные документы)", kb_id_name, "kb/direct"),
        (mem_hits, "Документы из настроек (библиотека памяти)", mem_id_name, "memory/direct"),
    ]:
        if hits_list:
            parts, _ = format_rag_fragments(
                hits_list,
                idnm,
                max_chars=10000,
                store_label=label,
                include_chunk_meta=False,
                truncate_marker="\n...\n",
            )
            final_message = f"{prefix}:\n{''.join(parts)}\n\n{final_message}"
            context_added = True

    eff_model_path = agent_profile["model_path"] or get_current_model_path()

    # Формируем итоговый системный промпт: инструкции проекта + промпт агента
    base_system_prompt = agent_profile["system_prompt"] or ""
    if project_instructions and project_instructions.strip():
        if base_system_prompt:
            eff_system_prompt = f"{project_instructions.strip()}\n\n{base_system_prompt}"
        else:
            eff_system_prompt = project_instructions.strip()
        logger.debug(f"[direct] project_instructions применены к system_prompt (project={project_id})")
    else:
        eff_system_prompt = base_system_prompt or None

    if context_added:
        eff_system_prompt = merge_strict_rag_system_prompt(eff_system_prompt)

    canned = await maybe_rag_no_evidence_message(
        rag_client,
        block_when_no_evidence=rag_block,
        context_added=context_added,
        global_attempted=global_attempted,
        project_id=project_id,
        use_kb_rag=use_kb_rag,
        use_memory_library_rag=use_memory_library_rag,
        use_agent_scoped_kb=use_agent_scoped_kb,
        agent_kb_doc_ids=agent_kb_doc_ids,
        implicit_global_corpus=False,
    )

    _terminal_chat_inference_banner(
        sid=sid, conversation_id=conversation_id, user_preview=final_message,
        mode_label="Прямой чат с LLM (одна модель)"
        + (" - параметры из выбранного агента" if agent_profile["model_path"] else ""),
        model_path_for_call=eff_model_path,
        extra_line="RAG/KB уже учтены в final_message при необходимости."
        + (" [RAG: ответ без LLM — нет релевантных фрагментов]" if canned else ""),
    )

    def _run_ask(stream, cb):
        return ask_agent(
            final_message, history=history,
            max_tokens=agent_profile["max_tokens"], streaming=stream, stream_callback=cb,
            model_path=eff_model_path, custom_prompt_id=None, images=images,
            system_prompt=eff_system_prompt, temperature=agent_profile["temperature"],
        )

    if canned:
        response = canned
        if streaming:
            await sio.emit("chat_chunk", {"chunk": canned, "accumulated": canned}, room=sid)
    elif streaming:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            response = await asyncio.get_event_loop().run_in_executor(ex, lambda: _run_ask(True, sync_stream_cb))
        if response is None or stop_generation_flags.get(sid, False):
            stop_generation_flags[sid] = False
            await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
            return
    else:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            response = await asyncio.get_event_loop().run_in_executor(ex, lambda: _run_ask(False, None))

    if context_added and not canned and response:
        response = await maybe_replace_ungrounded(
            final_message[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE
        )

    if stop_generation_flags.get(sid, False) or not session_still_valid():
        stop_generation_flags[sid] = False
        await sio.emit("generation_stopped", {"message": "Генерация остановлена"}, room=sid)
        return

    try:
        meta = {"document_search": document_search_trace} if document_search_trace else None
        if project_id:
            from backend.database.memory_service import save_dialog_entry_to_project
            await save_dialog_entry_to_project("assistant", response, project_id, conversation_id, None, user_id)
        else:
            await save_dialog_entry("assistant", response, meta, None, conversation_id, user_id)
    except RuntimeError as e:
        logger.warning(f"Не удалось сохранить ответ: {e}")

    stop_generation_flags[sid] = False
    payload = {"response": response, "timestamp": datetime.now().isoformat(), "was_streaming": streaming}
    if document_search_trace:
        payload["document_search"] = document_search_trace
    await sio.emit("chat_complete", payload, room=sid)