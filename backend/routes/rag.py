"""
routes/rag.py - настройки RAG, База Знаний (KB), библиотека памяти (memory-rag)
"""

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

import backend.app_state as state
from backend.app_state import minio_client, rag_client, rag_models_client, save_app_settings, settings
from backend.rag_query.semantic_cache import bump_rag_semantic_cache
from backend.schemas import RAGSettings, RagModelSelectRequest
from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress
from backend.settings.service_toggles import require_service

logger = get_logger(__name__)

router = APIRouter(tags=["rag"])
_VALID_STRATEGIES = {"auto", "hierarchical", "hybrid", "standard", "lexical", "raw_cosine", "graph"}
_VALID_CHUNKING_STRATEGIES = {"hierarchical", "fixed", "markdown", "separators", "semantic"}


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
            "standard": "Векторный поиск по semantic similarity.",
            "lexical": "Лексический поиск BM25 (без семантического расширения).",
            "raw_cosine": "Сырой cosine-поиск (без постобработки).",
            "graph": "Графовый RAG: расширение по связям между чанками.",
        }.get(state.current_rag_strategy, ""),
        "agentic_rag_enabled": bool(getattr(state, "agentic_rag_enabled", True)),
        "agentic_max_iterations": int(getattr(state, "agentic_max_iterations", 2)),
        "rag_query_fix_typos": bool(getattr(state, "rag_query_fix_typos", False)),
        "rag_multi_query_enabled": bool(getattr(state, "rag_multi_query_enabled", False)),
        "rag_hyde_enabled": bool(getattr(state, "rag_hyde_enabled", False)),
        "rag_chat_top_k": state.get_rag_chat_top_k(),
        "rag_chunking_strategy": str(getattr(state, "rag_chunking_strategy", "hierarchical")),
        "rag_chunk_overlap": int(getattr(state, "rag_chunk_overlap", 200)),
        "rag_similarity_threshold": float(getattr(state, "rag_similarity_threshold", 0.0)),
        "rag_reranking_enabled": bool(getattr(state, "rag_reranking_enabled", False)),
        "rag_rerank_top_n": int(getattr(state, "rag_rerank_top_n", 5)),
        "rag_system_prompt": str(
            getattr(
                state,
                "rag_system_prompt",
                'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.',
            )
        ),
        "rag_embedding_model_path": str(getattr(state, "rag_embedding_model_path", "") or ""),
        "rag_reranker_model_path": str(getattr(state, "rag_reranker_model_path", "") or ""),
    }


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
        state.rag_chat_top_k = 8
        state.rag_chunking_strategy = "hierarchical"
        state.rag_chunk_overlap = 200
        state.rag_similarity_threshold = 0.0
        state.rag_reranking_enabled = False
        state.rag_rerank_top_n = 5
        state.rag_embedding_model_path = ""
        state.rag_reranker_model_path = ""
        state.rag_system_prompt = (
            'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.'
        )
        save_app_settings(
            {
                "rag_strategy": "auto",
                "agentic_rag_enabled": True,
                "agentic_max_iterations": 2,
                "rag_query_fix_typos": False,
                "rag_multi_query_enabled": False,
                "rag_hyde_enabled": False,
                "rag_chat_top_k": 8,
                "rag_chunking_strategy": "hierarchical",
                "rag_chunk_overlap": 200,
                "rag_similarity_threshold": 0.0,
                "rag_reranking_enabled": False,
                "rag_rerank_top_n": 5,
                "rag_embedding_model_path": "",
                "rag_reranker_model_path": "",
                "rag_system_prompt": 'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.',
            }
        )
        bump_rag_semantic_cache()
        return {"message": "Настройки RAG сброшены", "success": True, **_rag_settings_response_dict()}
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/api/rag/settings")
async def update_rag_settings(settings_data: RAGSettings):
    strat = settings_data.strategy
    if strat is not None and strat == "reranking":
        strat = "hybrid"
    if strat is not None and strat == "lexical":
        strat = "lexical"
    if strat is not None and strat not in _VALID_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Недопустимая стратегия. Допустимые: {_VALID_STRATEGIES}")
    chunking = settings_data.rag_chunking_strategy
    if chunking is not None:
        chunking = str(chunking).strip().lower()
        if chunking not in _VALID_CHUNKING_STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимая стратегия чанкования. Допустимые: {_VALID_CHUNKING_STRATEGIES}",
            )
    if (
        settings_data.strategy is None
        and settings_data.agentic_rag_enabled is None
        and (settings_data.agentic_max_iterations is None)
        and (settings_data.rag_query_fix_typos is None)
        and (settings_data.rag_multi_query_enabled is None)
        and (settings_data.rag_hyde_enabled is None)
        and (settings_data.rag_chat_top_k is None)
        and (settings_data.rag_chunking_strategy is None)
        and (settings_data.rag_chunk_overlap is None)
        and (settings_data.rag_similarity_threshold is None)
        and (settings_data.rag_reranking_enabled is None)
        and (settings_data.rag_rerank_top_n is None)
        and (settings_data.rag_system_prompt is None)
        and (settings_data.rag_embedding_model_path is None)
        and (settings_data.rag_reranker_model_path is None)
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
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_chat_top_k: ожидается целое число 1–64") from e
        if chunking is not None:
            state.rag_chunking_strategy = chunking
            updates["rag_chunking_strategy"] = chunking
        if settings_data.rag_chunk_overlap is not None:
            try:
                overlap = int(settings_data.rag_chunk_overlap)
                state.rag_chunk_overlap = max(0, min(overlap, 2000))
                updates["rag_chunk_overlap"] = state.rag_chunk_overlap
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_chunk_overlap: ожидается целое число 0–2000") from e
        if settings_data.rag_similarity_threshold is not None:
            try:
                threshold = float(settings_data.rag_similarity_threshold)
                state.rag_similarity_threshold = max(0.0, min(threshold, 1.0))
                updates["rag_similarity_threshold"] = state.rag_similarity_threshold
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_similarity_threshold: ожидается число 0..1") from e
        if settings_data.rag_reranking_enabled is not None:
            state.rag_reranking_enabled = bool(settings_data.rag_reranking_enabled)
            updates["rag_reranking_enabled"] = state.rag_reranking_enabled
        if settings_data.rag_rerank_top_n is not None:
            try:
                top_n = int(settings_data.rag_rerank_top_n)
                state.rag_rerank_top_n = max(1, min(top_n, 64))
                updates["rag_rerank_top_n"] = state.rag_rerank_top_n
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail="rag_rerank_top_n: ожидается целое число 1–64") from e
        if settings_data.rag_system_prompt is not None:
            prompt = str(settings_data.rag_system_prompt or "").strip()
            state.rag_system_prompt = (
                prompt
                if prompt
                else 'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.'
            )
            updates["rag_system_prompt"] = state.rag_system_prompt
        if settings_data.rag_embedding_model_path is not None:
            state.rag_embedding_model_path = str(settings_data.rag_embedding_model_path or "").strip()
            updates["rag_embedding_model_path"] = state.rag_embedding_model_path
        if settings_data.rag_reranker_model_path is not None:
            state.rag_reranker_model_path = str(settings_data.rag_reranker_model_path or "").strip()
            updates["rag_reranker_model_path"] = state.rag_reranker_model_path
        if updates:
            save_app_settings(updates)
            if "rag_chat_top_k" in updates or "rag_rerank_top_n" in updates:
                bump_rag_semantic_cache()
        return {"message": "Настройки RAG обновлены", "success": True, **_rag_settings_response_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/rag/models")
async def list_rag_models(type: str | None = None):
    """Список моделей эмбеддингов и cross-encoder из SVC-RAG-MODELS."""
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    try:
        data = await rag_models_client.list_models(type)
        saved_emb = str(getattr(state, "rag_embedding_model_path", "") or "")
        saved_rer = str(getattr(state, "rag_reranker_model_path", "") or "")
        if saved_emb or saved_rer:
            current = dict(data.get("current") or {})
            if saved_emb:
                current["embedding"] = {
                    "path": saved_emb,
                    "name": saved_emb.split("/")[-1],
                    "display_name": saved_emb.split("/")[-1],
                    "source": saved_emb.split("/")[0] if "/" in saved_emb else "local",
                    "kind": "embedding",
                }
            if saved_rer:
                current["reranker"] = {
                    "path": saved_rer,
                    "name": saved_rer.split("/")[-1],
                    "display_name": saved_rer.split("/")[-1],
                    "source": saved_rer.split("/")[0] if "/" in saved_rer else "local",
                    "kind": "reranker",
                }
            data["current"] = current
        return data
    except Exception as e:
        logger.exception("list_rag_models error")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/api/rag/models/current")
async def get_rag_models_current():
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    try:
        data = await rag_models_client.get_current()
        saved_emb = str(getattr(state, "rag_embedding_model_path", "") or "")
        saved_rer = str(getattr(state, "rag_reranker_model_path", "") or "")
        if saved_emb or saved_rer:
            current = dict(data.get("current") or {})
            if saved_emb:
                current["embedding"] = {
                    "path": saved_emb,
                    "name": saved_emb.split("/")[-1],
                    "display_name": saved_emb.split("/")[-1],
                    "source": saved_emb.split("/")[0] if "/" in saved_emb else "local",
                    "kind": "embedding",
                }
            if saved_rer:
                current["reranker"] = {
                    "path": saved_rer,
                    "name": saved_rer.split("/")[-1],
                    "display_name": saved_rer.split("/")[-1],
                    "source": saved_rer.split("/")[0] if "/" in saved_rer else "local",
                    "kind": "reranker",
                }
            data["current"] = current
        return data
    except Exception as e:
        logger.exception("get_rag_models_current error")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/api/rag/models/select")
async def select_rag_model(body: RagModelSelectRequest):
    """Выбор и загрузка модели эмбеддингов или cross-encoder."""
    require_service("rag_models")
    if not rag_models_client:
        raise HTTPException(status_code=503, detail="RAG-models service недоступен")
    model_type = str(body.model_type or "").strip().lower()
    if model_type not in ("embedding", "reranker"):
        raise HTTPException(status_code=400, detail="model_type должен быть embedding или reranker")
    model_path = str(body.model_path or "").strip()
    if not model_path:
        raise HTTPException(status_code=400, detail="model_path обязателен")
    try:
        result = await rag_models_client.select_model(model_type, model_path)
        updates: dict = {}
        if model_type == "embedding":
            state.rag_embedding_model_path = model_path
            updates["rag_embedding_model_path"] = model_path
        else:
            state.rag_reranker_model_path = model_path
            updates["rag_reranker_model_path"] = model_path
        if updates:
            save_app_settings(updates)
        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("select_rag_model error")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/api/kb/documents")
async def kb_upload_document(file: Annotated[UploadFile, File(...)]):
    require_service("rag")
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
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/kb/documents")
async def kb_list_documents():
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.kb_list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/kb/documents/{document_id}")
async def kb_delete_document(document_id: int):
    require_service("rag")  # FEATURE-FLAG
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.kb_delete_document(document_id)
        bump_rag_semantic_cache()
        return out
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/memory-rag/documents")
async def memory_rag_upload(file: Annotated[UploadFile, File(...)]):
    require_service("minio")  # FEATURE-FLAG
    require_service("rag")  # FEATURE-FLAG
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
                    content,
                    file_object_name,
                    content_type=file.content_type or "application/octet-stream",
                    bucket_name=memory_bucket,
                )
            except Exception as e:
                logger.exception("MinIO memory-rag upload")
                raise HTTPException(status_code=500, detail=f"MinIO: {e}") from e
        try:
            result = await rag_client.memory_rag_index_document(
                file_bytes=content,
                filename=fn,
                minio_object=file_object_name,
                minio_bucket=memory_bucket if file_object_name else None,
            )
        except Exception as e:
            logger.exception("Ошибка операции")
            if minio_client and file_object_name:
                with logged_suppress(logger):
                    minio_client.delete_file(file_object_name, bucket_name=memory_bucket)
            if _is_upstream_httpx_timeout(e):
                raise HTTPException(
                    status_code=504,
                    detail="Таймаут ответа SVC-RAG при индексации (большой файл или медленный embed). Увеличьте SVC_RAG_INDEX_READ_TIMEOUT (секунды) для backend, по умолчанию 900.",
                ) from e
            raise HTTPException(status_code=502, detail=str(e)) from e
        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/memory-rag/documents")
async def memory_rag_list():
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.memory_rag_list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/memory-rag/documents/{document_id}")
async def memory_rag_delete(document_id: int):
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.memory_rag_delete_document(document_id)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail="Документ не найден")
        mo, mb = (out.get("minio_object"), out.get("minio_bucket"))
        if minio_client and mo and mb:
            try:
                minio_client.delete_file(mo, bucket_name=mb)
            except Exception:
                logger.exception("MinIO delete memory-rag")
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка операции")
        raise HTTPException(status_code=500, detail=str(e)) from e
