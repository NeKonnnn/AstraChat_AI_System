"""
routes/chat.py - REST /api/chat, WebSocket /ws/chat, WebSocket /ws/voice, WebSocket /ws/dictation
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

import backend.app_state as state
from backend.app_state import (
    ask_agent,
    get_agent_orchestrator,
    get_conversation_repository,
    get_current_model_path,
    get_model_comparison_models,
    get_rag_chat_top_k,
    get_recent_dialog_history,
    minio_client,
    rag_client,
    recognize_speech_from_file,
    save_dialog_entry,
    speak_text,
)
from backend.auth.jwt_handler import get_current_user
from backend.mcp.resolvers import resolve_chat_tool_ids
from backend.database.mongodb.models import Conversation, Message as DbMessage
from backend.llm_providers import get_registry
from backend.rag_query.post_generation import maybe_replace_ungrounded
from backend.rag_query.prompts import RAG_STRICT_NOT_FOUND_MESSAGE, merge_strict_rag_system_prompt
from backend.realtime.helpers import _is_structure_query, _terminal_chat_inference_banner
from backend.realtime.rag_evidence import (
    build_rag_id_to_filename,
    filter_rag_hits_by_score,
    format_rag_fragments,
    maybe_rag_no_evidence_message,
    rag_guard_env,
)
from backend.schemas import ChatMessage, ContextBreakdownRequest, MessageFeedbackRequest
from backend.services.context_breakdown import build_context_overhead
from backend.settings.cef_logger.cef_logger import log_cef_event
from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress
from backend.settings.service_toggles import is_service_enabled  # FEATURE-FLAG

logger = get_logger(__name__)

router = APIRouter(tags=["chat"])


class ConnectionManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)


manager = ConnectionManager()


@router.post("/api/chat/context-breakdown")
async def chat_context_breakdown(
    body: ContextBreakdownRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Оценка сегментов контекста (системные промпты, RAG, MCP) для UI-счётчика."""
    try:
        payload = await build_context_overhead(
            model_path=body.model_path,
            project_instructions=body.project_instructions,
            agent_id=body.agent_id,
            use_kb_rag=body.use_kb_rag,
            tool_ids=body.tool_ids,
            user=current_user,
        )
        payload["success"] = True
        return payload
    except Exception as e:
        logger.exception("context-breakdown error")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/chat")
async def chat_with_ai(
    request: Request, message: ChatMessage, current_user: Annotated[dict, Depends(get_current_user)]
):
    if not ask_agent:
        raise HTTPException(status_code=503, detail="AI agent не доступен")
    if not save_dialog_entry:
        raise HTTPException(status_code=503, detail="Memory service не доступен")
    from backend.settings.cef_logger.cef_audit_context import cef_audit_reset, cef_audit_set

    _audit_tok = cef_audit_set(request=request, user=current_user, socket_remote=None)
    try:
        history = (
            await get_recent_dialog_history(max_entries=state.memory_max_messages) if get_recent_dialog_history else []
        )
        from backend.services.user_feedback_context import (
            build_user_feedback_system_block,
            merge_feedback_into_system_prompt,
        )

        feedback_block = await build_user_feedback_system_block(
            current_user.get("user_id"),
            conversation_id=message.conversation_id,
        )
        orchestrator = get_agent_orchestrator()
        use_agent_mode = orchestrator and orchestrator.get_mode() == "agent"
        if use_agent_mode:
            agent_message = message.message
            if feedback_block:
                agent_message = f"{feedback_block}\n\n{message.message}"
            _terminal_chat_inference_banner(
                sid="HTTP-POST-/api/chat",
                conversation_id=None,
                user_preview=message.message,
                mode_label="REST /api/chat — оркестратор агентов",
            )
            response = await orchestrator.process_message(
                agent_message,
                context={
                    "history": history,
                    "user_message": message.message,
                    "selected_model": message.model or get_current_model_path(),
                    "tool_ids": resolve_chat_tool_ids(message.tool_ids or message.mcp_tool_ids),
                    "current_user": current_user,
                    "conversation_id": message.conversation_id,
                    "message_id": message.message_id,
                    "user_feedback_block": feedback_block,
                },
            )
        else:
            logger.info("ПРЯМОЙ РЕЖИМ: Переключение на прямое общение с LLM")
            logger.info(
                f"Запрос пользователя: '{message.message[:100]}{('...' if len(message.message) > 100 else '')}'"
            )
            response = None
            tool_ids = resolve_chat_tool_ids(message.tool_ids or message.mcp_tool_ids)
            current_model_path = message.model or get_current_model_path()
            rest_system_prompt = merge_feedback_into_system_prompt(None, feedback_block)
            if tool_ids:
                try:
                    from backend.mcp.chat_integration import run_mcp_for_chat

                    mcp_result = await run_mcp_for_chat(
                        tool_ids=tool_ids,
                        user_message=message.message,
                        history=history,
                        system_prompt=rest_system_prompt,
                        model_path=current_model_path,
                        user=current_user,
                        chat_id=message.conversation_id,
                        message_id=message.message_id,
                    )
                    if mcp_result is not None:
                        response = mcp_result.content
                        logger.info(
                            "REST MCP agent loop: mode=%s tools=%s", mcp_result.mode, mcp_result.tool_calls_executed
                        )
                except Exception:
                    logger.exception("REST MCP agent loop error")
            if rag_client and response is None and is_service_enabled("rag"):  # FEATURE-FLAG
                try:
                    min_sim, rag_block = rag_guard_env()
                    hits = await rag_client.search(
                        message.message, k=get_rag_chat_top_k(), strategy=state.current_rag_strategy
                    )
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
                                with logged_suppress(logger):
                                    for c, sc, did, idx in await rag_client.get_document_start_chunks(
                                        doc_id, max_chunks=2
                                    ):
                                        if (did, idx) not in seen:
                                            hits = [(c, sc, did, idx)] + hits
                                            seen.add((did, idx))
                        id_map = build_rag_id_to_filename(list(await rag_client.list_documents() or []))
                        parts, _ = format_rag_fragments(
                            hits, id_map, max_chars=12000, store_label="global/rest-api-chat"
                        )
                        doc_context = "\n".join(parts)
                        prompt = (
                            f"CONTEXT (фрагменты из документов):\n{doc_context}\n"
                            f"Вопрос пользователя: {message.message}\nОтвет:"
                        )
                        current_model_path = message.model or get_current_model_path()
                        _terminal_chat_inference_banner(
                            sid="HTTP-POST-/api/chat",
                            conversation_id=None,
                            user_preview=prompt,
                            mode_label="REST /api/chat — ответ с RAG",
                            model_path_for_call=current_model_path,
                        )
                        response = ask_agent(
                            prompt,
                            history=[],
                            streaming=False,
                            model_path=current_model_path,
                            system_prompt=merge_strict_rag_system_prompt(
                                None, rag_override=getattr(state, "rag_system_prompt", None)
                            ),
                        )
                        response = await maybe_replace_ungrounded(
                            prompt[:20000], response, RAG_STRICT_NOT_FOUND_MESSAGE
                        )
                except Exception:
                    logger.exception("ПРЯМОЙ РЕЖИМ: ошибка при получении контекста документов через SVC-RAG")
            if not response:
                logger.info("ПРЯМОЙ РЕЖИМ: Используем обычный AI agent без контекста документов")
                current_model_path = message.model or get_current_model_path()
                _terminal_chat_inference_banner(
                    sid="HTTP-POST-/api/chat",
                    conversation_id=None,
                    user_preview=message.message,
                    mode_label="REST /api/chat — прямой LLM (без RAG)",
                    model_path_for_call=current_model_path,
                )
                response = ask_agent(message.message, history=history, streaming=False, model_path=current_model_path)
            else:
                logger.info(f"ПРЯМОЙ РЕЖИМ: ответ готов, длина: {len(response)} символов")
        await save_dialog_entry("user", message.message, user_id=current_user["user_id"])
        await save_dialog_entry("assistant", response, user_id=current_user["user_id"])
        return {"response": response, "timestamp": datetime.now().isoformat(), "success": True}
    except Exception as e:
        logger.exception("Ошибка операции")
        logger.error(f"/api/chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        with logged_suppress(logger):
            cef_audit_reset(_audit_tok)


@router.get("/api/conversations")
async def get_conversations(current_user: Annotated[dict, Depends(get_current_user)], limit: int = 200):
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
                "metadata": conv.metadata or {},
                "messages": [
                    {
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                        "metadata": msg.metadata or {},
                    }
                    for msg in conv.messages or []
                ],
            }
        )
    return {"conversations": result, "count": len(result)}


@router.delete("/api/conversations")
async def delete_all_conversations(request: Request, current_user: Annotated[dict, Depends(get_current_user)]):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    deleted = await repo.delete_user_conversations(current_user["user_id"])
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
    conversation_id: str, request: Request, current_user: Annotated[dict, Depends(get_current_user)]
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
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
    conversation_id: str, request: Request, current_user: Annotated[dict, Depends(get_current_user)]
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
    conversation_id: str, request: Request, current_user: Annotated[dict, Depends(get_current_user)]
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
    conversation_id: str, request: Request, current_user: Annotated[dict, Depends(get_current_user)]
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


def _new_branch_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _resolve_multi_llm_slot_content(slot: Dict[str, Any]) -> str:
    alts = slot.get("alternative_responses") or slot.get("alternativeResponses")
    if isinstance(alts, list) and alts:
        idx = slot.get("current_response_index", slot.get("currentResponseIndex", 0))
        if not isinstance(idx, int) or idx < 0 or idx >= len(alts):
            idx = 0
        return str(alts[idx])
    return str(slot.get("content") or "")


def _clone_message_for_branch(
    msg: DbMessage,
    *,
    is_branch_point: bool,
    multi_llm_slot_index: Optional[int] = None,
) -> DbMessage:
    meta = dict(msg.metadata or {})
    content = msg.content
    if is_branch_point and msg.role == "assistant":
        if multi_llm_slot_index is not None:
            slots = meta.get("multi_llm_responses") or meta.get("multiLLMResponses") or []
            if isinstance(slots, list) and 0 <= multi_llm_slot_index < len(slots):
                slot = slots[multi_llm_slot_index]
                if isinstance(slot, dict):
                    content = _resolve_multi_llm_slot_content(slot)
                    meta = {
                        k: v
                        for k, v in meta.items()
                        if k not in ("multi_llm_responses", "multiLLMResponses")
                    }
                    model = slot.get("model")
                    if model:
                        meta["model"] = model
        else:
            alts = meta.get("alternative_responses") or meta.get("alternativeResponses")
            if isinstance(alts, list) and alts:
                idx = meta.get("current_response_index", meta.get("currentResponseIndex", 0))
                if not isinstance(idx, int) or idx < 0 or idx >= len(alts):
                    idx = 0
                content = str(alts[idx])
                for key in (
                    "alternative_responses",
                    "alternativeResponses",
                    "current_response_index",
                    "currentResponseIndex",
                ):
                    meta.pop(key, None)
    return DbMessage(
        message_id=_new_branch_message_id(),
        role=msg.role,
        content=content,
        timestamp=msg.timestamp or datetime.utcnow(),
        metadata=meta,
    )


def _serialize_conversation_for_client(conv: Conversation) -> dict:
    return {
        "conversation_id": conv.conversation_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "project_id": conv.project_id,
        "metadata": conv.metadata or {},
        "messages": [
            {
                "message_id": item.message_id,
                "role": item.role,
                "content": item.content,
                "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                "metadata": item.metadata or {},
            }
            for item in conv.messages or []
        ],
    }


@router.post("/api/conversations/{conversation_id}/branch")
async def branch_conversation(
    conversation_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    repo = get_conversation_repository()
    if repo is None:
        raise HTTPException(status_code=503, detail="MongoDB repository не доступен")
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Некорректное тело запроса") from exc
    message_id = str(body.get("message_id") or "").strip()
    if not message_id:
        raise HTTPException(status_code=400, detail="Поле 'message_id' обязательно")
    multi_llm_slot_index = body.get("multi_llm_slot_index")
    if multi_llm_slot_index is not None and not isinstance(multi_llm_slot_index, int):
        raise HTTPException(status_code=400, detail="Поле 'multi_llm_slot_index' должно быть числом")

    conv = await repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")

    source_messages = conv.messages or []
    branch_index = next(
        (idx for idx, item in enumerate(source_messages) if item.message_id == message_id),
        -1,
    )
    if branch_index < 0:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    branch_message = source_messages[branch_index]
    if branch_message.role != "assistant":
        raise HTTPException(status_code=400, detail="Ветку можно создать только от ответа ассистента")

    branched_messages = [
        _clone_message_for_branch(
            item,
            is_branch_point=(idx == branch_index),
            multi_llm_slot_index=multi_llm_slot_index if idx == branch_index else None,
        )
        for idx, item in enumerate(source_messages[: branch_index + 1])
    ]

    new_id = str(uuid.uuid4())
    base_title = (conv.title or "Чат").strip() or "Чат"
    branch_title = f"Ветка · {base_title[:40]}"
    now = datetime.utcnow()
    clone = Conversation(
        conversation_id=new_id,
        user_id=current_user["user_id"],
        title=branch_title,
        messages=branched_messages,
        metadata={
            **(conv.metadata or {}),
            "branched_from": conversation_id,
            "branch_message_id": message_id,
            "hidden_from_sidebar_until_user_message": True,
            "branch_seeded_message_count": len(branched_messages),
        },
        project_id=conv.project_id,
        created_at=now,
        updated_at=now,
    )
    created_id = await repo.create_conversation(clone)
    if not created_id:
        raise HTTPException(status_code=500, detail="Не удалось создать ветку диалога")

    log_cef_event(
        "CNV004",
        request=request,
        current_user=current_user,
        status_code=201,
        extra={"cs2": new_id, "cs2Label": "ConversationId", "cs3": conversation_id, "cs3Label": "SourceConversationId"},
    )
    return {
        "success": True,
        "conversation_id": new_id,
        "conversation": _serialize_conversation_for_client(clone),
    }


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
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/api/messages/{conversation_id}/{message_id}/feedback")
async def upsert_message_feedback(
    conversation_id: str,
    message_id: str,
    body: MessageFeedbackRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Сохранить или сбросить лайк/дизлайк ответа ассистента."""
    try:
        from backend.app_state import get_conversation_repository

        repo = get_conversation_repository()
        if repo is None:
            raise HTTPException(status_code=503, detail="MongoDB repository не доступен")

        conversation = await repo.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        if getattr(conversation, "user_id", None) and conversation.user_id != current_user.get("user_id"):
            raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")

        msg = next(
            (m for m in (conversation.messages or []) if getattr(m, "message_id", None) == message_id),
            None,
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        if getattr(msg, "role", None) != "assistant":
            raise HTTPException(status_code=400, detail="Оценку можно ставить только ответам ассистента")

        allowed_tags = {
            "did_not_follow_instructions",
            "dislike_style",
            "inaccurate",
            "too_verbose",
            "too_short",
            "irrelevant",
            "biased",
            "safety_or_legal",
            "other",
        }
        rating = body.rating
        if rating is None:
            feedback_payload = None
        else:
            raw_tags = [t for t in (body.tags or []) if t in allowed_tags]
            comment = (body.comment or "").strip()
            if len(comment) > 2000:
                comment = comment[:2000]
            if rating == "dislike" and not raw_tags and not comment:
                raise HTTPException(
                    status_code=400,
                    detail="Для дизлайка укажите причину (тег) или комментарий",
                )
            feedback_payload = {
                "rating": rating,
                "tags": raw_tags if rating == "dislike" else [],
                "comment": comment,
                "user_id": current_user.get("user_id"),
                "updated_at": datetime.now().isoformat(),
            }

        success = await repo.update_message_feedback(
            conversation_id,
            message_id,
            feedback_payload,
            multi_llm_slot_index=body.multi_llm_slot_index,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Не удалось сохранить отзыв")
        return {
            "success": True,
            "feedback": feedback_payload,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка сохранения feedback")
        raise HTTPException(status_code=500, detail=str(e)) from e


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
            history = (
                await get_recent_dialog_history(max_entries=state.memory_max_messages)
                if get_recent_dialog_history
                else []
            )
            await save_dialog_entry("user", user_message)
            orchestrator = get_agent_orchestrator()
            use_multi_llm = bool(data.get("model_comparison_enabled", False))
            use_agent = orchestrator and orchestrator.get_mode() == "agent"

            def stream_cb(chunk, acc):
                try:
                    asyncio.create_task(
                        websocket.send_text(json.dumps({"type": "chunk", "chunk": chunk, "accumulated": acc}))
                    )
                    return True
                except Exception:
                    logger.exception("Ошибка операции")
                    return False

            try:
                if use_multi_llm:
                    models = get_model_comparison_models()
                    if not models:
                        await websocket.send_text(json.dumps({"type": "error", "error": "Модели не выбраны"}))
                        continue
                    doc_context = None
                    if rag_client and is_service_enabled("rag"):  # FEATURE-FLAG
                        try:
                            hits = await rag_client.search(
                                user_message, k=get_rag_chat_top_k(), strategy=state.current_rag_strategy
                            )
                            if hits:
                                id_map = build_rag_id_to_filename(list(await rag_client.list_documents() or []))
                                parts, _ = format_rag_fragments(
                                    hits, id_map, max_chars=12000, store_label="global/ws-chat"
                                )
                                doc_context = "\n".join(parts)
                        except Exception:
                            logger.exception("WebSocket: Ошибка при получении контекста документов через SVC-RAG")
                    final_user_message = user_message
                    if doc_context:
                        final_user_message = (
                            f"Контекст из загруженных документов:\n{doc_context}\n"
                            f"Вопрос пользователя: {user_message}\n"
                            "Пожалуйста, ответьте на вопрос пользователя, используя информацию из предоставленных документов. "
                            "Если в документах нет информации для ответа, честно скажите об этом."
                        )

                    async def _gen_one(
                        model_name,
                        *,
                        _models=models,
                        _final_user_message=final_user_message,
                        _streaming=streaming,
                    ):
                        """Одна генерация multi-LLM через ProviderRegistry (без глобальных локов)."""
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "multi_llm_start",
                                    "model": model_name,
                                    "total_models": len(_models),
                                    "models": _models,
                                }
                            )
                        )
                        try:
                            registry = await get_registry()
                            provider, model_id = registry.resolve(model_name)
                            if not model_id:
                                return {
                                    "model": model_name,
                                    "response": f"Некорректный путь модели {model_name!r}",
                                    "error": True,
                                }
                            if not await provider.ensure_model_loaded(model_id):
                                return {
                                    "model": model_name,
                                    "response": f"Модель {model_id!r} недоступна на провайдере {provider.id!r}. Проверьте состояние сервера.",
                                    "error": True,
                                }
                            from backend.llm_client import get_llm_service

                            service = await get_llm_service()
                            messages = service.prepare_messages(
                                prompt=_final_user_message, history=None, system_prompt=None
                            )
                            if _streaming:

                                def _cb(chunk: str, acc: str) -> bool:
                                    try:
                                        asyncio.create_task(
                                            websocket.send_text(
                                                json.dumps(
                                                    {
                                                        "type": "multi_llm_chunk",
                                                        "model": model_name,
                                                        "chunk": chunk,
                                                        "accumulated": acc,
                                                    }
                                                )
                                            )
                                        )
                                    except Exception:
                                        logger.exception("WebSocket: ошибка отправки чанка")
                                    return True

                                resp = await provider.stream_chat(
                                    messages=messages, model=model_id, callback=_cb, temperature=0.7, max_tokens=1024
                                )
                            else:
                                resp = await provider.chat(
                                    messages=messages, model=model_id, temperature=0.7, max_tokens=1024
                                )
                            return {"model": model_name, "response": resp}
                        except Exception as e:
                            logger.exception("multi-llm /ws/chat: ошибка для модели %s", model_name)
                            return {"model": model_name, "response": f"Ошибка: {e}", "error": True}

                    results = await asyncio.gather(*[_gen_one(m) for m in models], return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception):
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "multi_llm_complete",
                                        "model": "unknown",
                                        "response": str(r),
                                        "error": True,
                                    }
                                )
                            )
                        else:
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "multi_llm_complete",
                                        "model": r.get("model", "unknown"),
                                        "response": r.get("response", ""),
                                        "error": r.get("error", False),
                                    }
                                )
                            )
                    logger.info("WebSocket: Все ответы от моделей сгенерированы")
                    continue
                if use_agent:
                    response = ask_agent(
                        user_message, history=history, streaming=False, model_path=get_current_model_path()
                    )
                    logger.info(f"WebSocket: получен ответ от AI agent, длина: {len(response)} символов")
                await save_dialog_entry("assistant", response)
                await websocket.send_text(
                    json.dumps({"type": "complete", "response": response, "timestamp": datetime.now().isoformat()})
                )
            except Exception as e:
                logger.exception("Ошибка операции")
                await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
    except WebSocketDisconnect:
        logger.info("WebSocket /ws/chat отключен")
        with logged_suppress(logger):
            manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket /ws/chat error")
        manager.disconnect(websocket)


@router.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket):
    await manager.connect(websocket)
    if not ask_agent or not save_dialog_entry:
        with logged_suppress(logger):
            await websocket.send_text(json.dumps({"type": "error", "error": "AI сервисы недоступны."}))
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
                    logger.exception("Ошибка операции")
                    with logged_suppress(logger):
                        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Ошибка операции")
        logger.error(f"W**ebSocket /ws/voice error: {e}", exc_info=True)
    finally:
        with logged_suppress(logger):
            manager.disconnect(websocket)


def _write_audio_bytes_to_file(data: bytes, *, upload_to_minio: bool = True) -> str:
    import tempfile

    if len(data) < 100:
        msg = "Некорректные аудио данные"
        raise ValueError(msg)
    if data[:4] == b"RIFF" and b"WAVE" in data[:12]:
        ext, ct = (".wav", "audio/wav")
    elif data[:4] == b"\x1aE\xdf\xa3":
        ext, ct = (".webm", "audio/webm")
    elif data[:4] == b"OggS":
        ext, ct = (".ogg", "audio/ogg")
    else:
        ext, ct = (".webm", "audio/webm")
    temp_dir = tempfile.gettempdir()
    audio_file = os.path.join(temp_dir, f"voice{datetime.now().timestamp()}{ext}")
    if minio_client and upload_to_minio:
        _vb = getattr(minio_client, "bucket_name", "") or "default"
        try:
            obj = minio_client.generate_object_name(prefix="voice_", extension=ext)
            minio_client.upload_file(data, obj, content_type=ct, cef_display_name="voice_upload")
            audio_file = minio_client.get_file_path(obj)
        except Exception:
            logger.exception("Ошибка загрузки аудио в MinIO")
            with open(audio_file, "wb") as f:
                f.write(data)
    else:
        with open(audio_file, "wb") as f:
            f.write(data)
    return audio_file


async def _process_dictation_audio(websocket: WebSocket, data: bytes):
    if not recognize_speech_from_file:
        await websocket.send_text(json.dumps({"type": "error", "error": "STT недоступен"}))
        return
    if len(data) < 100:
        await websocket.send_text(json.dumps({"type": "speech_error", "error": "Слишком короткий аудиофрагмент"}))
        return
    audio_file = None
    try:
        loop = asyncio.get_event_loop()
        audio_file = await loop.run_in_executor(None, lambda: _write_audio_bytes_to_file(data, upload_to_minio=False))
        text = await loop.run_in_executor(None, lambda: recognize_speech_from_file(audio_file))
        if not (text and text.strip()):
            await websocket.send_text(json.dumps({"type": "speech_error", "error": "Речь не распознана"}))
            return
        await websocket.send_text(json.dumps({"type": "speech_recognized", "text": text.strip()}))
    except ValueError as e:
        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
    except Exception as e:
        logger.exception("Ошибка операции")
        logger.warning(f"Dictation STT error: {e}")
        await websocket.send_text(json.dumps({"type": "speech_error", "error": "Ошибка распознавания"}))
    finally:
        if audio_file:
            with logged_suppress(logger):
                if os.path.exists(audio_file):
                    os.remove(audio_file)


@router.websocket("/ws/dictation")
async def websocket_dictation(websocket: WebSocket):
    await manager.connect(websocket)
    if not recognize_speech_from_file:
        with logged_suppress(logger):
            await websocket.send_text(json.dumps({"type": "error", "error": "STT недоступен"}))
    try:
        while True:
            raw = await websocket.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            if "text" in raw:
                try:
                    cmd = json.loads(raw["text"])
                    if cmd.get("type") == "start":
                        await websocket.send_text(json.dumps({"type": "ready", "message": "Готов к диктовке"}))
                except json.JSONDecodeError:
                    pass
            elif "bytes" in raw:
                try:
                    await _process_dictation_audio(websocket, raw["bytes"])
                except Exception as e:
                    logger.exception("Ошибка операции")
                    with logged_suppress(logger):
                        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Ошибка операции")
        logger.error(f"WebSocket /ws/dictation error: {e}", exc_info=True)
    finally:
        with logged_suppress(logger):
            manager.disconnect(websocket)


async def _process_audio(websocket: WebSocket, data: bytes):
    import tempfile

    if state.voice_chat_stop_flag:
        return
    if len(data) < 100:
        await websocket.send_text(json.dumps({"type": "error", "error": "Некорректные аудио данные"}))
        return
    if data[:4] == b"RIFF" and b"WAVE" in data[:12]:
        ext, ct = (".wav", "audio/wav")
    elif data[:4] == b"\x1aE\xdf\xa3":
        ext, ct = (".webm", "audio/webm")
    elif data[:4] == b"OggS":
        ext, ct = (".ogg", "audio/ogg")
    else:
        ext, ct = (".webm", "audio/webm")
    temp_dir = tempfile.gettempdir()
    audio_file = os.path.join(temp_dir, f"voice{datetime.now().timestamp()}{ext}")
    try:
        if minio_client:
            _vb = getattr(minio_client, "bucket_name", "") or "default"
            try:
                obj = minio_client.generate_object_name(prefix="voice_", extension=ext)
                minio_client.upload_file(data, obj, content_type=ct, cef_display_name="voice_upload")
                audio_file = minio_client.get_file_path(obj)
            except Exception:
                logger.exception("Ошибка загрузки аудио в MinIO")
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
        history = (
            await get_recent_dialog_history(max_entries=state.memory_max_messages) if get_recent_dialog_history else []
        )
        voice_prompt = "Ты — голосовой AI-ассистент AstraChat. Отвечай кратко, без markdown и emoji."
        ai_resp = await loop.run_in_executor(
            None,
            lambda: ask_agent(
                text, history=history, streaming=False, model_path=get_current_model_path(), system_prompt=voice_prompt
            ),
        )
        await save_dialog_entry("user", text)
        await save_dialog_entry("assistant", ai_resp)
        await websocket.send_text(json.dumps({"type": "ai_response", "text": ai_resp}))
        speech_file = os.path.join(temp_dir, f"speech_{datetime.now().timestamp()}.wav")
        try:
            ok = await loop.run_in_executor(
                None, lambda: speak_text(ai_resp, speaker="baya", voice_id="ru", save_to_file=speech_file)
            )
            if ok and os.path.exists(speech_file) and (os.path.getsize(speech_file) > 44):
                with open(speech_file, "rb") as f:
                    await websocket.send_bytes(f.read())
                with logged_suppress(logger):
                    os.remove(speech_file)
            else:
                await websocket.send_text(json.dumps({"type": "tts_error", "error": "Ошибка TTS"}))
        except Exception as e:
            logger.exception("Ошибка операции")
            await websocket.send_text(json.dumps({"type": "tts_error", "error": str(e)}))
    finally:
        with logged_suppress(logger):
            if os.path.exists(audio_file):
                os.remove(audio_file)
