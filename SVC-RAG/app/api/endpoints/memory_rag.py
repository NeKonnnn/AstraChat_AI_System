# Библиотека документов памяти (настройки)
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.dependencies import get_memory_rag_service
from app.services.memory_rag_service import MemoryRagService

logger = logging.getLogger(__name__)
router = APIRouter()


class MemoryRagIndexResponse(BaseModel):
    ok: bool
    document_id: Optional[int] = None
    filename: Optional[str] = None
    chunks_count: Optional[int] = None
    error: Optional[str] = None


class MemoryRagDocumentItem(BaseModel):
    id: int
    filename: str
    created_at: Optional[str] = None
    size: Optional[int] = None
    file_type: Optional[str] = None


class MemoryRagSearchRequest(BaseModel):
    query: str
    k: int = 8
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None


class MemoryRagSearchHit(BaseModel):
    content: str
    score: float
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None


class MemoryRagSearchResponse(BaseModel):
    hits: List[MemoryRagSearchHit]


@router.post("/documents", response_model=MemoryRagIndexResponse)
async def index_memory_rag_document(
    file: UploadFile = File(...),
    minio_object: Optional[str] = Form(None),
    minio_bucket: Optional[str] = Form(None),
    svc: MemoryRagService = Depends(get_memory_rag_service),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нужно имя файла")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Файл пустой")

    result = await svc.index_document(
        data,
        file.filename,
        minio_object=minio_object,
        minio_bucket=minio_bucket,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("error", "Ошибка индексации"))
    return MemoryRagIndexResponse(
        ok=True,
        document_id=result.get("document_id"),
        filename=result.get("filename"),
        chunks_count=result.get("chunks_count"),
    )


@router.get("/documents", response_model=List[MemoryRagDocumentItem])
async def list_memory_rag_documents(svc: MemoryRagService = Depends(get_memory_rag_service)):
    docs = await svc.list_documents()
    return [
        MemoryRagDocumentItem(
            id=d["id"],
            filename=d["filename"],
            created_at=d.get("created_at"),
            size=d.get("size"),
            file_type=d.get("file_type"),
        )
        for d in docs
    ]


@router.delete("/documents/{document_id}")
async def delete_memory_rag_document(
    document_id: int,
    svc: MemoryRagService = Depends(get_memory_rag_service),
):
    out = await svc.delete_document(document_id)
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail="Документ не найден")
    return out


@router.post("/search", response_model=MemoryRagSearchResponse)
async def memory_rag_search(
    body: MemoryRagSearchRequest,
    svc: MemoryRagService = Depends(get_memory_rag_service),
):
    results = await svc.search(
        query=body.query,
        k=body.k,
        document_id=body.document_id,
        use_reranking=body.use_reranking,
    )
    return MemoryRagSearchResponse(
        hits=[
            MemoryRagSearchHit(content=c, score=s, document_id=doc_id, chunk_index=chunk_idx)
            for c, s, doc_id, chunk_idx in results
        ]
    )
