"""
routes/project_rag.py - RAG файлов проектов (MinIO/PVC + SVC-RAG) и оркестрационное удаление проекта
"""

import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app_state import minio_client, rag_client, get_rag_chunk_index_params, settings
from backend.auth.jwt_handler import get_current_user
from backend.rag_query.semantic_cache import bump_rag_semantic_cache
from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress
from backend.settings.service_toggles import is_service_enabled, require_service
from backend.storage.rag_pvc import (
    RAG_PVC_BUCKET_MARKER,
    RAG_PVC_DIR_ENV,
    delete_rag_pvc_file,
    is_rag_pvc_bucket,
    save_rag_bytes_to_pvc,
    use_rag_pvc,
)

logger = get_logger(__name__)

router = APIRouter(tags=["project-rag"])


def _rag_upload_username(current_user: dict) -> str:
    return current_user.get("username") or current_user.get("user_id") or "anonymous"


def _delete_rag_source_file(object_name: Optional[str], bucket: Optional[str]) -> None:
    if not object_name or not bucket:
        return
    if is_rag_pvc_bucket(bucket):
        delete_rag_pvc_file(object_name, bucket)
        return
    if minio_client:
        try:
            minio_client.delete_file(object_name, bucket_name=bucket)
        except Exception:
            logger.exception("MinIO delete project-rag object=%s bucket=%s", object_name, bucket)


@router.post("/api/project-rag/projects/{project_id}/documents")
async def project_rag_upload(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Загрузить файл в RAG-хранилище проекта: MinIO или PVC + индексация SVC-RAG."""
    require_service("rag")  # FEATURE-FLAG
    if not use_rag_pvc():
        require_service("minio")  # FEATURE-FLAG
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    username = _rag_upload_username(current_user)
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пустой")
        fn = file.filename or "unknown"
        ext = os.path.splitext(fn)[1] or ".bin"
        file_object_name = None
        project_bucket = None
        if use_rag_pvc():
            file_object_name = save_rag_bytes_to_pvc(
                content,
                fn,
                scope="project",
                username=username,
                prefix=f"proj_{project_id}_",
                content_type=file.content_type or "application/octet-stream",
            )
            if not file_object_name:
                raise HTTPException(
                    status_code=500,
                    detail=f"Не удалось сохранить файл в PVC — проверьте {RAG_PVC_DIR_ENV} и mount /ragdb",
                )
            project_bucket = RAG_PVC_BUCKET_MARKER
        else:
            project_bucket = settings.minio.project_rag_bucket_name
            if minio_client:
                try:
                    minio_client.ensure_bucket(project_bucket)
                    file_object_name = minio_client.generate_object_name(prefix=f"proj_{project_id}_", extension=ext)
                    minio_client.upload_file(
                        content,
                        file_object_name,
                        content_type=file.content_type or "application/octet-stream",
                        bucket_name=project_bucket,
                    )
                except Exception as e:
                    logger.exception("MinIO загрузка project-rag")
                    raise HTTPException(status_code=500, detail=f"MinIO: {e}") from e
        try:
            # Project RAG: UI-стратегия чанкования применяется
            chunk_params = get_rag_chunk_index_params()
            result = await rag_client.project_rag_upload_document(
                file_bytes=content,
                filename=fn,
                project_id=project_id,
                minio_object=file_object_name,
                minio_bucket=project_bucket if file_object_name else None,
                **chunk_params,
            )
        except Exception as e:
            if file_object_name and project_bucket:
                with logged_suppress(logger):
                    _delete_rag_source_file(file_object_name, project_bucket)
            logger.exception("SVC-RAG project-rag индексация")
            raise HTTPException(status_code=422, detail=str(e)) from e
        bump_rag_semantic_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки project-rag")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/project-rag/projects/{project_id}/documents")
async def project_rag_list(project_id: str):
    """Список файлов RAG конкретного проекта"""
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        docs = await rag_client.project_rag_list_documents(project_id)
        return {"documents": docs}
    except Exception as e:
        logger.exception("Ошибка списка project-rag")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/project-rag/projects/{project_id}/documents/{document_id}")
async def project_rag_delete_document(project_id: str, document_id: int):
    """Удалить один файл из RAG проекта (PVC/MinIO + Postgres)"""
    require_service("rag")
    if not rag_client:
        raise HTTPException(status_code=503, detail="RAG service недоступен")
    try:
        out = await rag_client.project_rag_delete_document(project_id, document_id)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail="Документ не найден")
        _delete_rag_source_file(out.get("minio_object"), out.get("minio_bucket"))
        bump_rag_semantic_cache()
        return {"ok": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка удаления project-rag документа")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/project-rag/projects/{project_id}/search")
async def project_rag_search(project_id: str, body: dict):
    """Семантический поиск по RAG-файлам проекта"""
    require_service("rag")
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
        logger.exception("Ошибка поиска project-rag")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """
    Оркестрационное удаление проекта:
    1. Удаляет все RAG-документы из SVC-RAG (Postgres) и PVC/MinIO
    2. Удаляет все диалоги проекта из MongoDB
    Сам проект хранится во фронтенд-localStorage — там он тоже должен быть удалён
    """
    errors = []
    if rag_client and is_service_enabled("rag"):
        try:
            rag_out = await rag_client.project_rag_delete_project(project_id)
            minio_keys = rag_out.get("minio_keys", [])
            if minio_keys:
                for key_info in minio_keys:
                    _delete_rag_source_file(key_info.get("minio_object"), key_info.get("minio_bucket"))
            logger.info(f"project_id={project_id}: удалено RAG-документов: {rag_out.get('deleted_count', 0)}")
            bump_rag_semantic_cache()
        except Exception as e:
            logger.exception("Ошибка удаления RAG проекта")
            errors.append(f"RAG: {e}")
    else:
        errors.append("RAG service недоступен")
    try:
        from backend.database.memory_service import delete_project_memory

        deleted_convs = await delete_project_memory(project_id)
        logger.info(f"project_id={project_id}: удалено диалогов: {deleted_convs}")
    except Exception as e:
        logger.exception("Ошибка удаления MongoDB диалогов проекта")
        errors.append(f"MongoDB: {e}")
    return {"ok": len(errors) == 0, "project_id": project_id, "errors": errors}
