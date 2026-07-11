# API эндпоинты для постоянной Базы Знаний (Knowledge Base)
import logging
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
from app.dependencies import get_kb_service
from app.services.kb_service import KbService

logger = logging.getLogger(__name__)
router = APIRouter()


class KbIndexResponse(BaseModel):
    ok: bool
    document_id: Optional[int] = None
    filename: Optional[str] = None
    chunks_count: Optional[int] = None
    error: Optional[str] = None


class KbDocumentItem(BaseModel):
    id: int
    filename: str
    created_at: Optional[str] = None
    size: Optional[int] = None
    file_type: Optional[str] = None


class KbSearchRequest(RagSearchEvalBody):
    query: str
    k: int = 8
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None
    strategy: Optional[str] = None
    vector_query: Optional[str] = None
    filters: Optional[RagSearchFiltersBody] = None
    debug_trace: bool = False  # отладочные метрики по шагам пайплайна


class KbSearchHit(BaseModel):
    content: str
    score: float
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None


class KbSearchResponse(BaseModel):
    hits: List[KbSearchHit]
    trace: Optional[Dict[str, Any]] = None


@router.post("/documents", response_model=KbIndexResponse)
async def kb_index_document(
    file: UploadFile = File(...),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    chunking_strategy: Optional[str] = Form(None),
    kb: KbService = Depends(get_kb_service),
):
    """Загрузить документ в постоянную Базу Знаний (PDF, DOCX, XLSX, TXT)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нужно имя файла")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пустой")

    result = await kb.index_document(
        data,
        file.filename,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy or "universal",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("error", "Ошибка индексации"))
    return KbIndexResponse(
        ok=True,
        document_id=result.get("document_id"),
        filename=result.get("filename"),
        chunks_count=result.get("chunks_count"),
    )


@router.get("/documents", response_model=List[KbDocumentItem])
async def kb_list_documents(kb: KbService = Depends(get_kb_service)):
    """Список документов в Базе Знаний."""
    docs = await kb.list_documents()
    return [
        KbDocumentItem(
            id=d["id"],
            filename=d["filename"],
            created_at=d.get("created_at"),
            size=d.get("size"),
            file_type=d.get("file_type"),
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def kb_delete_document(
    document_id: int,
    kb: KbService = Depends(get_kb_service),
):
    """Удалить документ из Базы Знаний."""
    ok = await kb.delete_document(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Документ не найден в Базе Знаний")
    return {"ok": True, "document_id": document_id}


@router.post("/search", response_model=KbSearchResponse)
async def kb_search(
    body: KbSearchRequest,
    kb: KbService = Depends(get_kb_service),
):
    """Поиск по Базе Знаний."""
    payload = await kb.search(
        query=body.query,
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
    return KbSearchResponse(
        hits=[
            KbSearchHit(content=c, score=s, document_id=doc_id, chunk_index=chunk_idx)
            for c, s, doc_id, chunk_idx in results
        ],
        trace=trace.to_dict() if body.debug_trace else None,
    )


class KbReindexRequest(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    chunking_strategy: Optional[str] = None


_kb_reindex_lock = asyncio.Lock()


async def _kb_reindex_bg(
    kb: KbService,
    chunk_size: Optional[int],
    chunk_overlap: Optional[int],
    chunking_strategy: Optional[str],
) -> None:
    if _kb_reindex_lock.locked():
        logger.info(
            "[REINDEX kb] уже идёт — новый запуск дождётся завершения предыдущего"
        )
    async with _kb_reindex_lock:
        try:
            res = await kb.reindex_all(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                chunking_strategy=chunking_strategy,
            )
            logger.info("[REINDEX kb] фоновая перечанкировка завершена: %s", res)
        except Exception:
            logger.exception("[REINDEX kb] фоновая перечанкировка упала")

            
@router.post("/reindex")
async def kb_reindex(
    body: KbReindexRequest,
    background: BackgroundTasks,
    kb: KbService = Depends(get_kb_service),
):
    """Запустить перечанкировку всей БЗ В ФОНЕ. Отвечает сразу, не дожидаясь конца."""
    background.add_task(
        _kb_reindex_bg,
        kb,
        body.chunk_size,
        body.chunk_overlap,
        body.chunking_strategy,
    )
    return {"ok": True, "status": "started"}