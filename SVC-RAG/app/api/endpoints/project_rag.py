# API эндпоинты для RAG-файлов проектов
from typing import Any, Dict, List, Optional

import asyncio
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from pydantic import BaseModel

from app.api.rag_common import (
    RagSearchEvalBody,
    RagSearchFiltersBody,
    eval_search_kwargs_from_body,
    filters_body_to_domain,
)
from app.dependencies import get_project_rag_service
from app.services.project_rag_service import ProjectRagService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

class ProjectRagIndexResponse(BaseModel):
    ok: bool
    document_id: Optional[int] = None
    filename: Optional[str] = None
    chunks_count: Optional[int] = None
    project_id: Optional[str] = None
    error: Optional[str] = None

class ProjectRagDocumentItem(BaseModel):
    id: int
    filename: str
    project_id: str
    created_at: Optional[str] = None
    size: Optional[int] = None
    file_type: Optional[str] = None

class ProjectRagSearchRequest(RagSearchEvalBody):
    query: str
    k: int = 8
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None
    strategy: Optional[str] = None
    vector_query: Optional[str] = None
    filters: Optional[RagSearchFiltersBody] = None
    debug_trace: bool = False

class ProjectRagSearchHit(BaseModel):
    content: str
    score: float
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None

class ProjectRagSearchResponse(BaseModel):
    hits: List[ProjectRagSearchHit]
    trace: Optional[Dict[str, Any]] = None

@router.post("/projects/{project_id}/documents", response_model=ProjectRagIndexResponse)
async def project_rag_upload(
    project_id: str,
    file: UploadFile = File(...),
    minio_object: Optional[str] = Form(None),
    minio_bucket: Optional[str] = Form(None),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    chunking_strategy: Optional[str] = Form(None),
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Загрузить документ в RAG-хранилище проекта."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нужно имя файла")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пустой")

    result = await svc.index_document(
        data,
        file.filename,
        project_id=project_id,
        minio_object=minio_object,
        minio_bucket=minio_bucket,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=422, detail=result.get("error", "Ошибка индексации")
        )
    return ProjectRagIndexResponse(
        ok=True,
        document_id=result.get("document_id"),
        filename=result.get("filename"),
        chunks_count=result.get("chunks_count"),
        project_id=project_id,
    )

@router.get(
    "/projects/{project_id}/documents", response_model=List[ProjectRagDocumentItem]
)
async def project_rag_list(
    project_id: str,
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Список документов RAG конкретного проекта."""
    docs = await svc.list_documents(project_id)
    return [
        ProjectRagDocumentItem(
            id=d["id"],
            filename=d["filename"],
            project_id=d["project_id"],
            created_at=d.get("created_at"),
            size=d.get("size"),
            file_type=d.get("file_type"),
        )
        for d in docs
    ]

@router.delete("/projects/{project_id}/documents/{document_id}")
async def project_rag_delete_document(
    project_id: str,
    document_id: int,
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Удалить один документ из RAG-хранилища проекта."""
    out = await svc.delete_document(document_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail="Документ не найден")
    return out

@router.delete("/projects/{project_id}")
async def project_rag_delete_project(
    project_id: str,
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Удалить все RAG-документы проекта (вызывается при удалении проекта)."""
    out = await svc.delete_by_project(project_id)
    return out

@router.post("/projects/{project_id}/search", response_model=ProjectRagSearchResponse)
async def project_rag_search(
    project_id: str,
    body: ProjectRagSearchRequest,
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Семантический поиск по RAG-документам проекта."""
    if _project_reindex_lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Идёт переиндексация проектов — поиск временно недоступен",
        )
    payload = await svc.search(
        query=body.query,
        project_id=project_id,
        k=body.k,
        document_id=body.document_id,
        use_reranking=body.use_reranking,
        strategy=body.strategy,
        vector_query=body.vector_query,
        filters=filters_body_to_domain(body.filters),
        return_trace=True,
        **eval_search_kwargs_from_body(body),
    )
    results, trace = payload
    return ProjectRagSearchResponse(
        hits=[
            ProjectRagSearchHit(
                content=c, score=s, document_id=doc_id, chunk_index=chunk_idx
            )
            for c, s, doc_id, chunk_idx in results
        ],
        trace=trace.to_dict() if body.debug_trace else None,
    )

class ProjectRagReindexRequest(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    chunking_strategy: Optional[str] = None

_project_reindex_lock = asyncio.Lock()

async def _project_reindex_all_bg(
    svc: ProjectRagService,
    chunk_size: Optional[int],
    chunk_overlap: Optional[int],
    chunking_strategy: Optional[str],
) -> None:
    from app.services.project_rag_service import (
        bump_project_reindex_generation,
        current_project_reindex_generation,
    )

    gen = bump_project_reindex_generation()
    async with _project_reindex_lock:
        if gen != current_project_reindex_generation():
            logger.info("[REINDEX project ALL] пропуск: поколение устарело до старта")
            return
        try:
            res = await svc.reindex_all_projects(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chunking_strategy=chunking_strategy,
                generation=gen,
            )
            logger.info(
                "[REINDEX project ALL] фоновая перечанкировка завершена: %s", res
            )
        except Exception:
            logger.exception("[REINDEX project ALL] фоновая перечанкировка упала")

@router.post("/reindex")
async def project_rag_reindex_all(
    body: ProjectRagReindexRequest,
    background: BackgroundTasks,
    svc: ProjectRagService = Depends(get_project_rag_service),
):
    """Перечанкировать ВСЕ проекты В ФОНЕ. Отвечает сразу."""
    background.add_task(
        _project_reindex_all_bg,
        svc,
        body.chunk_size,
        body.chunk_overlap,
        body.chunking_strategy,
    )
    return {"ok": True, "status": "started"}


@router.get("/reindex/status")
async def project_rag_reindex_status():
    return {"reindexing": _project_reindex_lock.locked()}