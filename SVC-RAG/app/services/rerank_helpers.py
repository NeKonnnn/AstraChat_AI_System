"""Корректное применение cross-encoder rerank (индексы top-k) и порог по скору."""

from __future__ import annotations


from typing import Any, List, Tuple
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rerank_vector_hits(
    query: str,
    hits: List[Tuple[Any, float]],
    rag_client: Any,
    top_k: int,
    vector_weight: float = 0.3,
) -> List[Tuple[Any, float]]:
    """
    hits: список (DocumentVector, prior_score) — prior может быть cosine или RRF.

    Best practice: после fusion порядок задаёт cross-encoder. Prior-score (RRF ~0.01)
    нельзя линейно смешивать с логитом реранкера — шкалы несопоставимы.
    Поэтому:
      1) берём порядок от reranker;
      2) prior используется только как микро-тайбрейк (1e-6 * rank_norm).
    ``vector_weight`` оставлен для совместимости вызовов, на порядок не влияет.
    """
    if not hits or not rag_client:
        return hits[:top_k] if top_k else hits
    contents = [dv.content for dv, _ in hits]
    logger.debug(
        "[rerank] вход: кандидатов=%s, top_k=%s (rank-primary, prior только tiebreak)",
        len(contents),
        top_k,
    )
    try:
        ranked = await rag_client.rerank(query, contents, top_k=min(len(contents), max(top_k * 2, top_k)))
    except Exception as e:
        logger.warning("rerank_helpers.rerank failed: %s", e)
        return hits[:top_k] if top_k else hits
    if not ranked:
        return hits[:top_k] if top_k else hits

    # Нормализуем prior по рангу исходного списка (не по абсолютному RRF/cosine).
    prior_rank = {i: r for r, (i, _) in enumerate(sorted(enumerate(hits), key=lambda x: float(x[1][1]), reverse=True))}
    n = max(len(hits), 1)
    out: List[Tuple[Any, float]] = []
    for rr_rank, (idx, rr_sc) in enumerate(ranked):
        if idx >= len(hits):
            continue
        dv, _orig = hits[idx]
        # Основной сигнал — позиция/скор реранкера; prior — микро-тайбрейк.
        pr = prior_rank.get(idx, n - 1)
        prior_norm = 1.0 - (pr / n)
        combined = float(rr_sc) + 1e-6 * prior_norm - 1e-9 * rr_rank
        out.append((dv, combined))
    logger.debug("[rerank] выход: отранжировано=%s (из %s)", len(out), len(hits))
    return out[:top_k] if top_k else out


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
