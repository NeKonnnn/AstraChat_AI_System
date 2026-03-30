"""
routes/rag.py - настройки RAG, База Знаний (KB), библиотека памяти (memory-rag)
"""

import logging
import os

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

import backend.app_state as state
from backend.app_state import rag_client, minio_client, settings, save_app_settings
from backend.rag_query.semantic_cache import bump_rag_semantic_cache
from backend.schemas import RAGSettings

router = APIRouter(tags=["rag"])
logger = logging.getLogger(__name__)

_VALID_STRATEGIES = {"auto", "hierarchical", "hybrid", "standard", "graph"}


def _is_upstream_httpx_timeout(exc: BaseException) -> bool:
    seen = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, httpx.TimeoutException):
            return True
        cur = cur.__cause__
    return False


def _rag_settings_response_dict() -> dict:
    """Текущее состояние настроек RAG для JSON (после GET/PUT/reset)."""
    return {
        "strategy": state.current_rag_strategy,
        "applied_method": state.current_rag_strategy,
        "method_description": {
            "auto": "Автоматический выбор стратегии.",
            "hierarchical": "Иерархический поиск по суммаризациям.",
            "hybrid": "Гибридный поиск: вектор + BM25.",
            "standard": "Стандартный векторный поиск.",
            "graph": "Графовый RAG: расширение по связям между чанками.",
        }.get(state.current_rag_strategy, ""),
        "agentic_rag_enabled": bool(getattr(state, "agentic_rag_enabled", True)),
        "agentic_max_iterations": int(getattr(state, "agentic_max_iterations", 2)),
        "rag_query_fix_typos": bool(getattr(state, "rag_query_fix_typos", False)),
        "rag_multi_query_enabled": bool(getattr(state, "rag_multi_query_enabled", False)),
        "rag_hyde_enabled": bool(getattr(state, "rag_hyde_enabled", False)),
        "rag_chat_top_k": state.get_rag_chat_top_k(),
    }


# -- RAG settings
@router.get("/api/rag/settings")
async def get_rag_settings():
    return _rag_settings_response_dict()


@router.post("/api/rag/settings/reset")
async def reset_rag_settings():
    """Сброс всех настроек RAG из UI к значениям по умолчанию (как после чистой установки)."""
    try:
        state.current_rag_strategy = "auto"
        state.agentic_rag_enabled = True
        state.agentic_max_iterations = 2
        state.rag_query_fix_typos = False
        state.rag_multi_query_enabled = False
        state.rag_hyde_enabled = False
        state.rag_chat_top_k = 5
        save_app_settings(
            {
                "rag_strategy": "auto",
                "agentic_rag_enabled": True,
                "agentic_max_iterations": 2,
                "rag_query_fix_typos": False,
                "rag_multi_query_enabled": False,
                "rag_hyde_enabled": False,
                "rag_chat_top_k": 5,
            }
        )
        bump_rag_semantic_cache()
        return {"message": "Настройки RAG сброшены", "success": True, **_rag_settings_response_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/rag/settings")
async def update_rag_settings(settings_data: RAGSettings):
    strat = settings_data.strategy
    if strat is not None and strat == "reranking":
        strat = "hybrid"
    if strat is not None and strat not in _VALID_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимая стратегия. Допустимые: {_VALID_STRATEGIES}",
        )
    if (
        settings_data.strategy is None
        and settings_data.agentic_rag_enabled is None
        and settings_data.agentic_max_iterations is None
        and settings_data.rag_query_fix_typos is None
        and settings_data.rag_multi_query_enabled is None
        and settings_data.rag_hyde_enabled is None
        and settings_data.rag_chat_top_k is None
    ):
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    try:
        updates: dict = {}
        if strat is not None:
            state.current_rag_strategy = strat
            updates["rag_strategy"] = state.current_rag_strategy
        if settings_data.agentic_rag_enabled is not None:
            state.agentic_rag_enabled = bool(settings_data.agentic_rag_enabled)
            updates["agentic_rag_enabled"] = state.agentic_rag_enabled
        if settings_data.agentic_max_iterations is not None:
            ami = int(settings_data.agentic_max_iterations)
            state.agentic_max_iterations = max(1, min(ami, 5))
            updates["agentic_max_iterations"] = state.agentic_max_iterations
        if settings_data.rag_query_fix_typos is not None:
            state.rag_query_fix_typos = bool(settings_data.rag_query_fix_typos)
            updates["rag_query_fix_typos"] = state.rag_query_fix_typos
        if settings_data.rag_multi_query_enabled is not None:
            state.rag_multi_query_enabled = bool(settings_data.rag_multi_query_enabled)
            updates["rag_multi_query_enabled"] = state.rag_multi_query_enabled
        if settings_data.rag_hyde_enabled is not None:
            state.rag_hyde_enabled = bool(settings_data.rag_hyde_enabled)
            updates["rag_hyde_enabled"] = state.rag_hyde_enabled
        if settings_data.rag_chat_top_k is not None:
            try:
                rk = int(settings_data.rag_chat_top_k)
                state.rag_chat_top_k = max(1, min(rk, 64))
                updates["rag_chat_top_k"] = state.rag_chat_top_k
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="rag_chat_top_k: ожидается целое число 1–64")
        if updates:
            save_app_settings(updates)
            if "rag_chat_top_k" in updates:
                bump_rag_semantic_cache()
        return {"message": "Настройки RAG обновлены", "success": True, **_rag_settings_response_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -- Knowledge Base
@router.post("/api/kb/documents")
async def kb_upload_document(file: UploadFile = File(...)):
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        out = await rag_client.kb_upload_document(file_bytes=content, filename=file.filename or "unknown")
        bump_rag_semantic_cache()
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/kb/documents")
async def kb_list_documents():
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.kb_list_documents()
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/kb/documents/{document_id}")
async def kb_delete_document(document_id: int):
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.kb_delete_document(document_id)
        bump_rag_semantic_cache()
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -- Memory RAG
@router.post("/api/memory-rag/documents")
async def memory_rag_upload(file: UploadFile = File(...)):
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        fn = file.filename or "unknown"
        ext = os.path.splitext(fn)[1] or ".bin"
        memory_bucket = settings.minio.memory_rag_bucket_name
        file_object_name = None

        if minio_client:
            try:
                minio_client.ensure_bucket(memory_bucket)
                file_object_name = minio_client.generate_object_name(prefix="memrag_", extension=ext)
                minio_client.upload_file(
                    content, file_object_name,
                    content_type=file.content_type or "application/octet-stream",
                    bucket_name=memory_bucket,
                )
            except Exception as e:
                logger.error(f"MinIO memory-rag upload: {e}")
                raise HTTPException(status_code=500, detail=f"MinIO: {e}")

        try:
            result = await rag_client.memory_rag_index_document(
                file_bytes=content, filename=fn,
                minio_object=file_object_name,
                minio_bucket=memory_bucket if file_object_name else None,
            )
        except Exception as e:
            if minio_client and file_object_name:
                try:
                    minio_client.delete_file(file_object_name, bucket_name=memory_bucket)
                except Exception:
                    pass
            if _is_upstream_httpx_timeout(e):
                raise HTTPException(
                    status_code=504,
                    detail=(
                        "Таймаут ответа SVC-RAG при индексации (большой файл или медленный embed). "
                        "Увеличьте SVC_RAG_INDEX_READ_TIMEOUT (секунды) для backend, по умолчанию 900."
                    ),
                ) from e
            raise HTTPException(status_code=502, detail=str(e)) from e

        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory-rag/documents")
async def memory_rag_list():
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.memory_rag_list_documents()
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory-rag/documents/{document_id}")
async def memory_rag_delete(document_id: int):
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.memory_rag_delete_document(document_id)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail="Документ не найден")
        mo, mb = out.get("minio_object"), out.get("minio_bucket")
        if minio_client and mo and mb:
            try:
                minio_client.delete_file(mo, bucket_name=mb)
            except Exception as e:
                logger.warning(f"MinIO delete memory-rag: {e}")
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
