"""
routes/project_rag.py - RAG файлов проектов (MinIO + SVC-RAG) и оркестрационное удаление проекта
"""

import logging
import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app_state import rag_client, minio_client, settings
from backend.rag_query.semantic_cache import bump_rag_semantic_cache

router = APIRouter(tags=["project-rag"])
logger = logging.getLogger(__name__)


# -- документы проекта RAG

@router.post("/api/project-rag/projects/{project_id}/documents")
async def project_rag_upload(project_id: str, file: UploadFile = File(...)):
    """Загрузить файл в RAG-хранилище проекта: MinIO (bucket project-rag) + индексация"""
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        fn = file.filename or "unknown"
        ext = os.path.splitext(fn)[1] or ".bin"
        project_bucket = settings.minio.project_rag_bucket_name
        file_object_name = None
        if minio_client:
            try:
                minio_client.ensure_bucket(project_bucket)
                file_object_name = minio_client.generate_object_name(
                    prefix=f"proj_{project_id}_", extension=ext
                )
                minio_client.upload_file(
                    content,
                    file_object_name,
                    content_type=file.content_type or "application/octet-stream",
                    bucket_name=project_bucket,
                )
            except Exception as e:
                logger.error(f"MinIO загрузка project-rag: {e}")
                raise HTTPException(status_code=500, detail=f"MinIO: {e}")
        try:
            result = await rag_client.project_rag_upload_document(
                file_bytes=content,
                filename=fn,
                project_id=project_id,
                minio_object=file_object_name,
                minio_bucket=project_bucket if file_object_name else None,
            )
        except Exception as e:
            if minio_client and file_object_name:
                try:
                    minio_client.delete_file(file_object_name, bucket_name=project_bucket)
                except Exception:
                    pass
            logger.error(f"SVC-RAG project-rag индексация: {e}")
            raise HTTPException(status_code=422, detail=str(e))
        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка загрузки project-rag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/project-rag/projects/{project_id}/documents")
async def project_rag_list(project_id: str):
    """Список файлов RAG конкретного проекта"""
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.project_rag_list_documents(project_id)
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Ошибка списка project-rag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/project-rag/projects/{project_id}/documents/{document_id}")
async def project_rag_delete_document(project_id: str, document_id: int):
    """Удалить один файл из RAG проекта (MinIO + Postgres)"""
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.project_rag_delete_document(project_id, document_id)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail="Документ не найден")
        mo, mb = out.get("minio_object"), out.get("minio_bucket")
        if minio_client and mo and mb:
            try:
                minio_client.delete_file(mo, bucket_name=mb)
            except Exception as ex:
                logger.warning(f"Не удалось удалить объект MinIO project-rag: {ex}")
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления project-rag документа: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/project-rag/projects/{project_id}/search")
async def project_rag_search(project_id: str, body: dict):
    """Семантический поиск по RAG-файлам проекта"""
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        results = await rag_client.project_rag_search(
            query=body.get("query", ""),
            project_id=project_id,
            k=body.get("k", 8),
            document_id=body.get("document_id"),
            use_reranking=body.get("use_reranking"),
            strategy=body.get("strategy"),
        )
        return {
            "hits": [
                {"content": c, "score": s, "document_id": doc_id, "chunk_index": chunk_idx}
                for c, s, doc_id, chunk_idx in results
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка поиска project-rag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -- оркестрационное удаление проекта

@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """
    Оркестрационное удаление проекта:
    1. Удаляет все RAG-документы из SVC-RAG (Postgres) и MinIO
    2. Удаляет все диалоги проекта из MongoDB
    Сам проект хранится во фронтенд-localStorage — там он тоже должен быть удалён
    """
    errors = []

    if rag_client:
        try:
            rag_out = await rag_client.project_rag_delete_project(project_id)
            minio_keys = rag_out.get("minio_keys", [])
            if minio_client and minio_keys:
                for key_info in minio_keys:
                    mo = key_info.get("minio_object")
                    mb = key_info.get("minio_bucket")
                    if mo and mb:
                        try:
                            minio_client.delete_file(mo, bucket_name=mb)
                        except Exception as ex:
                            logger.warning(f"MinIO project-rag ключ не удалён ({mo}): {ex}")
            logger.info(
                f"project_id={project_id}: удалено RAG-документов: {rag_out.get('deleted_count', 0)}"
            )
            bump_rag_semantic_cache()
        except Exception as e:
            logger.error(f"Ошибка удаления RAG проекта {project_id}: {e}")
            errors.append(f"RAG: {e}")
    else:
        errors.append("RAG service недоступен")

    try:
        from backend.database.memory_service import delete_project_memory
        deleted_convs = await delete_project_memory(project_id)
        logger.info(f"project_id={project_id}: удалено диалогов: {deleted_convs}")
    except Exception as e:
        logger.error(f"Ошибка удаления MongoDB диалогов проекта {project_id}: {e}")
        errors.append(f"MongoDB: {e}")

    return {
        "ok": len(errors) == 0,
        "project_id": project_id,
        "errors": errors,
    }
