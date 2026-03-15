# API эндпоинты для постоянной Базы Знаний (Knowledge Base)
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

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


class KbSearchRequest(BaseModel):
    query: str
    k: int = 8
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None


class KbSearchHit(BaseModel):
    content: str
    score: float
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None


class KbSearchResponse(BaseModel):
    hits: List[KbSearchHit]


@router.post("/documents", response_model=KbIndexResponse)
async def kb_index_document(
    file: UploadFile = File(...),
    kb: KbService = Depends(get_kb_service),
):
    """Загрузить документ в постоянную Базу Знаний (PDF, DOCX, XLSX, TXT)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нужно имя файла")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пустой")

    result = await kb.index_document(data, file.filename)
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
    results = await kb.search(
        query=body.query,
        k=body.k,
        document_id=body.document_id,
        use_reranking=body.use_reranking,
    )
    return KbSearchResponse(
        hits=[
            KbSearchHit(content=c, score=s, document_id=doc_id, chunk_index=chunk_idx)
            for c, s, doc_id, chunk_idx in results
        ]
    )
