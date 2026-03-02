# Поиск по индексированным документам
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_rag_service
from app.services.rag_service import RagService

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    k: int = 10
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None
    strategy: Optional[str] = None  # "flat" | "hierarchical"


class SearchHit(BaseModel):
    content: str
    score: float
    document_id: Optional[int] = None
    chunk_index: Optional[int] = None


class SearchResponse(BaseModel):
    hits: List[SearchHit]


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    rag: RagService = Depends(get_rag_service),
):
    """Поиск по RAG: эмбеддинг запроса, векторный (и при необходимости гибридный + реранк) поиск."""
    results = await rag.search(
        query=body.query,
        k=body.k,
        document_id=body.document_id,
        use_reranking=body.use_reranking,
        strategy=body.strategy,
    )
    return SearchResponse(
        hits=[
            SearchHit(content=c, score=s, document_id=doc_id, chunk_index=chunk_idx)
            for c, s, doc_id, chunk_idx in results
        ]
    )
