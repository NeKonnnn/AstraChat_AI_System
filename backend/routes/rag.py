"""
routes/rag.py - настройки RAG, База Знаний (KB), библиотека памяти (memory-rag)
"""

import logging
import os

from fastapi import APIRouter, File, HTTPException, UploadFile

import backend.app_state as state
from backend.app_state import rag_client, minio_client, settings, save_app_settings
from backend.schemas import RAGSettings

router = APIRouter(tags=["rag"])
logger = logging.getLogger(__name__)

_VALID_STRATEGIES = {"auto", "reranking", "hierarchical", "hybrid", "standard"}


# -- RAG settings
@router.get("/api/rag/settings")
async def get_rag_settings():
    s = state.current_rag_strategy
    descriptions = {
        "auto": "Автоматический выбор стратегии.",
        "reranking": "Переранжирование результатов поиска.",
        "hierarchical": "Иерархический поиск по суммаризациям.",
        "hybrid": "Гибридный поиск: вектор + BM25.",
        "standard": "Стандартный векторный поиск.",
    }
    return {"strategy": s, "applied_method": s, "method_description": descriptions.get(s, "")}


@router.put("/api/rag/settings")
async def update_rag_settings(settings_data: RAGSettings):
    if settings_data.strategy not in _VALID_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Недопустимая стратегия. Допустимые: {_VALID_STRATEGIES}")
    try:
        state.current_rag_strategy = settings_data.strategy
        save_app_settings({"rag_strategy": state.current_rag_strategy})
        return {"message": "Настройки RAG обновлены", "success": True, "strategy": state.current_rag_strategy}
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
        return await rag_client.kb_upload_document(file_bytes=content, filename=file.filename or "unknown")
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
        return await rag_client.kb_delete_document(document_id)
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
            raise HTTPException(status_code=422, detail=str(e))

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
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
