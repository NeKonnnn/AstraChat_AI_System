# Поиск по индексированным документам
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.rag_common import RagSearchEvalBody, RagSearchFiltersBody, eval_search_kwargs_from_body, filters_body_to_domain
from app.dependencies import get_rag_service
from app.services.rag_service import RagService

router = APIRouter()


class SearchRequest(RagSearchEvalBody):
    query: str
    k: int = 10
    document_id: Optional[int] = None
    use_reranking: Optional[bool] = None
    strategy: Optional[str] = None  # "auto" | "reranking" | "hierarchical" | "hybrid" | "standard" | "raw_cosine" | "graph" | "flat"
    vector_query: Optional[str] = None
    filters: Optional[RagSearchFiltersBody] = None


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
        vector_query=body.vector_query,
        filters=filters_body_to_domain(body.filters),
        **eval_search_kwargs_from_body(body),
    )
    return SearchResponse(
        hits=[
            SearchHit(content=c, score=s, document_id=doc_id, chunk_index=chunk_idx)
            for c, s, doc_id, chunk_idx in results
        ]
    )
