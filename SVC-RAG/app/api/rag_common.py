"""Общие поля запросов RAG (фильтры, vector_query)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.database.search_filters import DocumentVectorSearchFilters


class RagSearchFiltersBody(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    filename_contains: Optional[str] = Field(None, max_length=512)


class RagEvalGoldChunkBody(BaseModel):
    """Эталонный чанк для offline-метрик recall@k / precision@k."""

    document_id: int
    chunk_index: int


class RagSearchEvalBody(BaseModel):
    """Опциональная оценка качества retrieval (логи + можно расширить ответ API позже)."""

    eval_gold_document_ids: Optional[List[int]] = None
    eval_gold_chunks: Optional[List[RagEvalGoldChunkBody]] = None
    eval_llm_judge: bool = False


def eval_search_kwargs_from_body(body: RagSearchEvalBody) -> Dict[str, Any]:
    """Параметры для RagService.search / kb / memory / project search."""
    chunks: Optional[List[Tuple[int, int]]] = None
    if body.eval_gold_chunks:
        chunks = [(c.document_id, c.chunk_index) for c in body.eval_gold_chunks]
    return {
        "eval_gold_document_ids": body.eval_gold_document_ids,
        "eval_gold_chunks": chunks,
        "eval_llm_judge": bool(body.eval_llm_judge),
    }


def filters_body_to_domain(body: Optional[RagSearchFiltersBody]) -> Optional[DocumentVectorSearchFilters]:
    if body is None:
        return None
    f = DocumentVectorSearchFilters(
        date_from=body.date_from,
        date_to=body.date_to,
        filename_contains=body.filename_contains,
    )
    return f if f.active() else None
