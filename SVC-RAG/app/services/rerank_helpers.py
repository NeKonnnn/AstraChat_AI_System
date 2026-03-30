"""Корректное применение cross-encoder rerank (индексы top-k) и порог по скору."""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


async def rerank_vector_hits(
    query: str,
    hits: List[Tuple[Any, float]],
    rag_client: Any,
    top_k: int,
    vector_weight: float = 0.3,
) -> List[Tuple[Any, float]]:
    """
    hits: список (DocumentVector, similarity_score).
    rag_client.rerank возвращает пары (индекс_в_passages, rerank_score).
    """
    if not hits or not rag_client:
        return hits[:top_k] if top_k else hits
    contents = [dv.content for dv, _ in hits]
    try:
        ranked = await rag_client.rerank(query, contents, top_k=min(len(contents), max(top_k * 2, top_k)))
    except Exception as e:
        logger.warning("rerank_helpers.rerank failed: %s", e)
        return hits[:top_k] if top_k else hits
    out: List[Tuple[Any, float]] = []
    for idx, rr_sc in ranked:
        if idx < len(hits):
            dv, orig = hits[idx]
            rr = float(rr_sc)
            combined = (1.0 - vector_weight) * rr + vector_weight * float(orig)
            out.append((dv, combined))
    return out


def filter_by_min_score(
    rows: List[Tuple[Any, ...]],
    min_score: float,
    score_index: int = 1,
) -> List[Tuple[Any, ...]]:
    if min_score <= 0.0:
        return rows
    out = []
    for row in rows:
        try:
            if float(row[score_index]) >= min_score:
                out.append(row)
        except (TypeError, ValueError, IndexError):
            continue
    return out
