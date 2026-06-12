"""
routes/chat.py - REST /api/chat, WebSocket /ws/chat, WebSocket /ws/voice
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
import backend.app_state as state
from backend.app_state import (
    ask_agent, save_dialog_entry, get_recent_dialog_history,
    clear_dialog_history, rag_client, get_agent_orchestrator,
    minio_client, speak_text, recognize_speech_from_file,
    get_current_model_path,
    get_rag_chat_top_k,
    reload_model_by_path,
    get_conversation_repository,
    get_model_comparison_models,
)
from backend.llm_providers import get_registry
from backend.schemas import ChatMessage
from backend.auth.jwt_handler import get_current_user
from backend.realtime.helpers import _is_structure_query, _terminal_chat_inference_banner
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
from backend.settings.cef_logger.cef_logger import log_cef_event
from backend.database.mongodb.models import Conversation
router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)
# -- WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)
manager = ConnectionManager()
# -- REST /api/chat
@router.post("/api/chat")
async def chat_with_ai(
    request: Request,
    message: ChatMessage,
    current_user: dict = Depends(get_current_user),
):
    if not ask_agent:
        raise HTTPException(status_code=503, detail="AI agent не доступен")
    if not save_dialog_entry:
        raise HTTPException(status_code=503, detail="Memory service не доступен")
    from backend.settings.cef_logger.cef_audit_context import cef_audit_reset, cef_audit_set

    _audit_tok = cef_audit_set(request=request, user=current_user, socket_remote=None)
    try:
        from backend.services.comfyui_image_generation import ComfyImageGenError
        from backend.services.image_generation_service import (
            handle_chat_image_generation,
            is_image_generation_chat_request,
        )

        if is_image_generation_chat_request(message.message):
            await save_dialog_entry("user", message.message, user_id=current_user["user_id"])
            try:
                img_result = await handle_chat_image_generation(
                    message.message,
                    preset_id=message.image_gen_preset_id,
                )
                response = img_result.get("response") or ""
                meta = img_result.get("metadata") or {}
                await save_dialog_entry(
                    "assistant",
                    response,
                    meta,
                    user_id=current_user["user_id"],
                )
                return {
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "inline_attachments": img_result.get("inline_attachments") or [],
                    "image_generation": True,
                }
            except ComfyImageGenError as img_exc:
                err_text = f"Не удалось сгенерировать изображение: {img_exc}"
                await save_dialog_entry("assistant", err_text, user_id=current_user["user_id"])
                raise HTTPException(status_code=502, detail=err_text) from img_exc

        history = await get_recent_dialog_history(max_entries=state.memory_max_messages) if get_recent_dialog_history else []
        orchestrator = get_agent_orchestrator()
        use_agent_mode = orchestrator and orchestrator.get_mode() == "agent"
        if use_agent_mode:
            _terminal_chat_inference_banner(
                sid="HTTP-POST-/api/chat", conversation_id=None,
                user_preview=message.message, mode_label="REST /api/chat — оркестратор агентов",
            )
            response = await orchestrator.process_message(
                message.message,
                context={
                    "history": history,
                    "user_message": message.message,
                    "selected_model": message.model or get_current_model_path(),
                    "tool_ids": message.tool_ids or message.mcp_tool_ids or [],
                    "current_user": current_user,
                    "conversation_id": message.conversation_id,
                    "message_id": message.message_id,
                },
            )
        else:
            logger.info("ПРЯМОЙ РЕЖИМ: Переключение на прямое общение с LLM")
            logger.info(f"Запрос пользователя: '{message.message[:100]}{'...' if len(message.message) > 100 else ''}'")
            response = None
            tool_ids = message.tool_ids or message.mcp_tool_ids or []
            current_model_path = message.model or get_current_model_path()
            if tool_ids:
                try:
                    from backend.mcp.chat_integration import run_mcp_for_chat

                    mcp_result = await run_mcp_for_chat(
                        tool_ids=tool_ids,
                        user_message=message.message,
                        history=history,
                        system_prompt=None,
                        model_path=current_model_path,
                        user=current_user,
                        chat_id=message.conversation_id,
                        message_id=message.message_id,
                    )
                    if mcp_result is not None:
                        response = mcp_result.content
                        logger.info(
                            "REST MCP agent loop: mode=%s tools=%s",
                            mcp_result.mode,
                            mcp_result.tool_calls_executed,
                        )
                except Exception as mcp_exc:
                    logger.error("REST MCP agent loop error: %s", mcp_exc, exc_info=True)
            if rag_client and response is None:
                try:
                    min_sim, rag_block = rag_guard_env()
                    hits = await rag_client.search(message.message, k=get_rag_chat_top_k(), strategy=state.current_rag_strategy)
                    hits = filter_rag_hits_by_score(hits, min_sim)
                    canned = await maybe_rag_no_evidence_message(
                        rag_client,
                        block_when_no_evidence=rag_block,
                        context_added=bool(hits),
                        global_attempted=True,
                        project_id=None,
                        use_kb_rag=False,
                        use_memory_library_rag=False,
                        use_agent_scoped_kb=False,
                        agent_kb_doc_ids=None,
                        implicit_global_corpus=True,
                    )
                    if canned:
                        response = canned
                    elif hits:
                        if _is_structure_query(message.message):
                            seen = {(d, i) for _, _, d, i in hits}
                            for doc_id in {d for _, _, d, _ in hits if d}:
                                try:
                                    for c, sc, did, idx in await rag_client.get_document_start_chunks(doc_id, max_chunks=2):
                                        if (did, idx) not in seen:
                                            hits = [(c, sc, did, idx)] + hits
                                            seen.add((did, idx))
                                except Exception:
                                    pass
                        id_map = build_rag_id_to_filename(list(await rag_client.list_documents() or []))
                        parts, _ = format_rag_fragments(
                            hits,
                            id_map,
                            max_chars=12000,
                            store_label="global/rest-api-chat",
                        )
                        doc_context = "\n".join(parts)
                        prompt = f"""CONTEXT (фрагменты из документов):
                        {doc_context}
                        Вопрос пользователя: {message.message}
                        Ответ:"""
                        current_model_path = message.model or get_current_model_path()
                        _terminal_chat_inference_banner(
                            sid="HTTP-POST-/api/chat", conversation_id=None,
                            user_preview=prompt, mode_label="REST /api/chat — ответ с RAG",
                            model_path_for_call=current_model_path,
                        )
                        response = ask_agent(
                            prompt,
                            history=[],
                            streaming=False,
                            model_path=current_model_path,
                            system_prompt=merge_strict_rag_system_prompt(None),
                        )
                        response = await maybe_replace_ungrounded(
                            prompt[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE
                        )
                except Exception as e:
                    logger.error(f"ПРЯМОЙ РЕЖИМ: ошибка при получении контекста документов через SVC-RAG: {e}")
            if not response:
                logger.info("ПРЯМОЙ РЕЖИМ: Используем обычный AI agent без контекста документов")
                current_model_path = message.model or get_current_model_path()
                _terminal_chat_inference_banner(
                    sid="HTTP-POST-/api/chat", conversation_id=None,
                    user_preview=message.message, mode_label="REST /api/chat — прямой LLM (без RAG)",
                    model_path_for_call=current_model_path,
                )
                response = ask_agent(message.message, history=history, streaming=False, model_path=current_model_path)
            else:
                logger.info(f"ПРЯМОЙ РЕЖИМ: ответ готов, длина: {len(response)} символов")
        await save_dialog_entry("user", message.message, user_id=current_user["user_id"])
        await save_dialog_entry("assistant", response, user_id=current_user["user_id"])
        return {"response": response, "timestamp": datetime.now().isoformat(), "success": True}
    except Exception as e:
        logger.error(f"/api/chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cef_audit_reset(_audit_tok)
        except Exception:
            pass
@router.get("/api/conversations")
async def get_conversations(limit: int = 200, current_user: dict = Depends(get_current_user)):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    user_id = current_user["user_id"]
    conversations = await repo.get_user_conversations(user_id=user_id, limit=limit)
    result = []
    for conv in conversations:
        result.append(
            {
                "conversation_id": conv.conversation_id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "project_id": conv.project_id,
                "messages": [
                    {
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                        "metadata": msg.metadata or {},
                    }
                    for msg in (conv.messages or [])
                ],
            }
        )
    return {"conversations": result, "count": len(result)}
@router.delete("/api/conversations")
async def delete_all_conversations(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    from backend.services.image_generation_service import persist_image_creations_from_conversation

    user_id = current_user["user_id"]
    conversations = await repo.get_user_conversations(user_id, limit=10000)
    for conv in conversations:
        try:
            await persist_image_creations_from_conversation(conv)
        except Exception:
            pass
    deleted = await repo.delete_user_conversations(user_id)
    log_cef_event(
        "CNV005",
        request=request,
        current_user=current_user,
        status_code=200,
        extra={"cs2": "all", "cs2Label": "ConversationId"},
    )
    return {"success": True, "deleted": deleted}
@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
    from backend.services.image_generation_service import persist_image_creations_from_conversation

    try:
        await persist_image_creations_from_conversation(conv)
    except Exception:
        pass
    await repo.delete_conversation(conversation_id)
    log_cef_event(
        "CNV004",
        request=request,
        current_user=current_user,
        status_code=200,
        extra={"cs2": conversation_id, "cs2Label": "ConversationId"},
    )
    return {"success": True, "conversation_id": conversation_id}
@router.put("/api/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    body = await request.json()
    title = body.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Поле 'title' обязательно")
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
    await repo.update_conversation(conversation_id, {"title": title})
    log_cef_event(
        "CNV001",
        request=request,
        current_user=current_user,
        status_code=200,
        extra={"cs2": conversation_id, "cs2Label": "ConversationId"},
    )
    return {"success": True, "conversation_id": conversation_id, "title": title}
@router.post("/api/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
    metadata = dict(conv.metadata or {})
    metadata["archived"] = True
    await repo.update_conversation(conversation_id, {"metadata": metadata})
    log_cef_event(
        "CNV002",
        request=request,
        current_user=current_user,
        status_code=200,
        extra={"cs2": conversation_id, "cs2Label": "ConversationId"},
    )
    return {"success": True, "conversation_id": conversation_id, "archived": True}
@router.post("/api/conversations/{conversation_id}/duplicate")
async def duplicate_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
    new_id = str(uuid.uuid4())
    clone = Conversation(
        conversation_id=new_id,
        user_id=current_user["user_id"],
        title=(conv.title or "Диалог") + " (copy)",
        messages=conv.messages,
        metadata=conv.metadata or {},
        project_id=conv.project_id,
    )
    created_id = await repo.create_conversation(clone)
    if not created_id:
        raise HTTPException(status_code=500, detail="Не удалось создать копию диалога")
    log_cef_event(
        "CNV003",
        request=request,
        current_user=current_user,
        status_code=201,
        extra={"cs2": new_id, "cs2Label": "ConversationId"},
    )
    return {"success": True, "conversation_id": new_id}
@router.put("/api/messages/{conversation_id}/{message_id}")
async def update_message(conversation_id: str, message_id: str, request: dict):
    try:
        from backend.app_state import get_conversation_repository
        repo = get_conversation_repository()
        if repo is None:
            raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="Поле 'content' обязательно")
        success = await repo.update_message(conversation_id, message_id, content, request.get("old_content"))
        if success:
            return {"message": "Сообщение обновлено", "success": True, "timestamp": datetime.now().isoformat()}
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# -- WebSocket /ws/chat
@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    if not ask_agent or not save_dialog_entry:
        await websocket.close(code=1008, reason="AI services not available")
        return
    await manager.connect(websocket)
    try:
        while True:
            data = json.loads(await websocket.receive_text())
            user_message = data.get("message", "")
            streaming = data.get("streaming", True)
            history = await get_recent_dialog_history(max_entries=state.memory_max_messages) if get_recent_dialog_history else []
            await save_dialog_entry("user", user_message)
            orchestrator = get_agent_orchestrator()
            use_multi_llm = bool(data.get("model_comparison_enabled", False))
            use_agent = orchestrator and orchestrator.get_mode() == "agent"
            def stream_cb(chunk, acc):
                try:
                    asyncio.create_task(websocket.send_text(json.dumps({"type": "chunk", "chunk": chunk, "accumulated": acc})))
                    return True
                except Exception:
                    return False
            try:
                if use_multi_llm:
                    models = get_model_comparison_models()
                    if not models:
                        await websocket.send_text(json.dumps({"type": "error", "error": "Модели не выбраны"}))
                        continue
                    doc_context = None
                    if rag_client:
                        try:
                            hits = await rag_client.search(user_message, k=get_rag_chat_top_k(), strategy=state.current_rag_strategy)
                            if hits:
                                id_map = build_rag_id_to_filename(list(await rag_client.list_documents() or []))
                                parts, _ = format_rag_fragments(
                                    hits,
                                    id_map,
                                    max_chars=12000,
                                    store_label="global/ws-chat",
                                )
                                doc_context = "\n".join(parts)
                        except Exception as e:
                            logger.error(f"WebSocket: Ошибка при получении контекста документов через SVC-RAG: {e}")
                    final_user_message = user_message
                    if doc_context:
                        final_user_message = f"""Контекст из загруженных документов:
                        {doc_context}
                        Вопрос пользователя: {user_message}
                        Пожалуйста, ответьте на вопрос пользователя, используя информацию из предоставленных документов. Если в документах нет информации для ответа, честно скажите об этом."""
                    async def _gen_one(model_name):
                        """Одна генерация multi-LLM через ProviderRegistry (без глобальных локов)."""
                        await websocket.send_text(json.dumps({
                            "type": "multi_llm_start", "model": model_name,
                            "total_models": len(models), "models": models,
                        }))
                        try:
                            registry = await get_registry()
                            provider, model_id = registry.resolve(model_name)
                            if not model_id:
                                return {"model": model_name, "response": f"Некорректный путь модели {model_name!r}", "error": True}
                            if not await provider.ensure_model_loaded(model_id):
                                return {
                                    "model": model_name,
                                    "response": (
                                        f"Модель {model_id!r} недоступна на провайдере "
                                        f"{provider.id!r}. Проверьте состояние сервера."
                                    ),
                                    "error": True,
                                }
                            from backend.llm_client import get_llm_service
                            service = await get_llm_service()
                            messages = service.prepare_messages(
                                prompt=final_user_message, history=None, system_prompt=None,
                            )
                            if streaming:
                                def _cb(chunk: str, acc: str) -> bool:
                                    try:
                                        asyncio.create_task(websocket.send_text(json.dumps({
                                            "type": "multi_llm_chunk", "model": model_name,
                                            "chunk": chunk, "accumulated": acc,
                                        })))
                                    except Exception as e:
                                        logger.error(f"WebSocket: ошибка отправки чанка {model_name}: {e}")
                                    return True
                                resp = await provider.stream_chat(
                                    messages=messages, model=model_id, callback=_cb,
                                    temperature=0.7, max_tokens=1024,
                                )
                            else:
                                resp = await provider.chat(
                                    messages=messages, model=model_id,
                                    temperature=0.7, max_tokens=1024,
                                )
                            return {"model": model_name, "response": resp}
                        except Exception as e:
                            logger.exception("multi-llm /ws/chat: ошибка для модели %s", model_name)
                            return {"model": model_name, "response": f"Ошибка: {e}", "error": True}
                    results = await asyncio.gather(*[_gen_one(m) for m in models], return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            await websocket.send_text(json.dumps({
                                "type": "multi_llm_complete", "model": "unknown",
                                "response": str(r), "error": True,
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "multi_llm_complete", "model": r.get("model", "unknown"),
                                "response": r.get("response", ""), "error": r.get("error", False),
                            }))
                    logger.info("WebSocket: Все ответы от моделей сгенерированы")
                    continue
                # --- ЛОГИКА АГЕНТНОЙ АРХИТЕКТУРЫ (Начало) ---
                if use_agent:
                    # Обычная генерация
                        response = ask_agent(
                            user_message,
                            history=history,
                            streaming=False,
                            model_path=get_current_model_path()
                        )
                        logger.info(f"WebSocket: получен ответ от AI agent, длина: {len(response)} символов")
                await save_dialog_entry("assistant", response)
                await websocket.send_text(json.dumps({"type": "complete", "response": response, "timestamp": datetime.now().isoformat()}))
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/chat отключен")
        try:
            manager.disconnect(websocket)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"WebSocket /ws/chat error: {e}")
        manager.disconnect(websocket)
# -- WebSocket /ws/voice
@router.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    await manager.connect(websocket)
    if not ask_agent or not save_dialog_entry:
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": "AI сервисы недоступны."}))
        except Exception:
            pass
    try:
        while True:
            raw = await websocket.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            if "text" in raw:
                try:
                    cmd = json.loads(raw["text"])
                    t = cmd.get("type", "")
                    if t == "start_listening":
                        await websocket.send_text(json.dumps({"type": "listening_started", "message": "Готов"}))
                    elif t == "stop_processing":
                        state.voice_chat_stop_flag = True
                        await websocket.send_text(json.dumps({"type": "processing_stopped"}))
                    elif t == "reset_processing":
                        state.voice_chat_stop_flag = False
                        await websocket.send_text(json.dumps({"type": "processing_reset"}))
                except json.JSONDecodeError:
                    pass
            elif "bytes" in raw:
                try:
                    await _process_audio(websocket, raw["bytes"])
                except Exception as e:
                    try:
                        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"W**ebSocket /ws/voice error: {e}", exc_info=True)
    finally:
        try:
            manager.disconnect(websocket)
        except Exception:
            pass
async def _process_audio(websocket: WebSocket, data: bytes):
    import tempfile
    if state.voice_chat_stop_flag:
        return
    if len(data) < 100:
        await websocket.send_text(json.dumps({"type": "error", "error": "Некорректные аудио данные"}))
        return
    # определяем формат
    if data[:4] == b"RIFF" and b"WAVE" in data[:12]:
        ext, ct = ".wav", "audio/wav"
    elif data[:4] == b"\x1a\x45\xdf\xa3":
        ext, ct = ".webm", "audio/webm"
    elif data[:4] == b"OggS":
        ext, ct = ".ogg", "audio/ogg"
    else:
        ext, ct = ".webm", "audio/webm"
    temp_dir = tempfile.gettempdir()
    audio_file = os.path.join(temp_dir, f"voice{datetime.now().timestamp()}{ext}")
    try:
        if minio_client:
            _vb = getattr(minio_client, "bucket_name", "") or "default"
            try:
                obj = minio_client.generate_object_name(prefix="voice_", extension=ext)
                minio_client.upload_file(data, obj, content_type=ct)
                audio_file = minio_client.get_file_path(obj)
                log_cef_event(
                    "FS003",
                    request=websocket,
                    status_code=200,
                    extra={"file": obj, "bucket": f"minio://{_vb}/{obj}"},
                )
            except Exception as _me:
                try:
                    log_cef_event(
                        "FS004",
                        request=websocket,
                        status_code=500,
                        extra={"file": "voice_upload", "bucket": f"minio://{_vb}", "reason": str(_me)[:300]},
                    )
                except Exception:
                    pass
                with open(audio_file, "wb") as f:
                    f.write(data)
        else:
            with open(audio_file, "wb") as f:
                f.write(data)
        if not recognize_speech_from_file:
            await websocket.send_text(json.dumps({"type": "error", "error": "STT недоступен"}))
            return
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, lambda: recognize_speech_from_file(audio_file))
        if not (text and text.strip()):
            await websocket.send_text(json.dumps({"type": "speech_error", "error": "Речь не распознана"}))
            return
        await websocket.send_text(json.dumps({"type": "speech_recognized", "text": text}))
        history = await get_recent_dialog_history(max_entries=state.memory_max_messages) if get_recent_dialog_history else []
        voice_prompt = (
            "Ты — голосовой AI-ассистент AstraChat. Отвечай кратко, без markdown и emoji."
        )
        ai_resp = await loop.run_in_executor(
            None,
            lambda: ask_agent(text, history=history, streaming=False,
                               model_path=get_current_model_path(), system_prompt=voice_prompt),
        )
        await save_dialog_entry("user", text)
        await save_dialog_entry("assistant", ai_resp)
        await websocket.send_text(json.dumps({"type": "ai_response", "text": ai_resp}))
        speech_file = os.path.join(temp_dir, f"speech_{datetime.now().timestamp()}.wav")
        try:
            ok = await loop.run_in_executor(
                None,
                lambda: speak_text(ai_resp, speaker="baya", voice_id="ru", save_to_file=speech_file),
            )
            if ok and os.path.exists(speech_file) and os.path.getsize(speech_file) > 44:
                with open(speech_file, "rb") as f:
                    await websocket.send_bytes(f.read())
                try:
                    os.remove(speech_file)
                except Exception:
                    pass
            else:
                await websocket.send_text(json.dumps({"type": "tts_error", "error": "Ошибка TTS"}))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "tts_error", "error": str(e)}))
    finally:
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception:
            pass