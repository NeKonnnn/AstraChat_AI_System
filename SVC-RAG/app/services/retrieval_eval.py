"""Метрики retrieval: время, gold (precision/recall/hit rate), LLM-as-a-Judge."""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

from app.services.llm_rag_judge import judge_chunk_relevance
from app.services.rag_search_helpers import log_rag_retrieval_report

HitRow = Tuple[str, float, Optional[int], Optional[int]]


def _first_relevant_rank(
    hits: List[HitRow],
    *,
    gold_docs: Optional[set] = None,
    gold_chunks: Optional[set] = None,
) -> Optional[int]:
    """1-базовая позиция первого релевантного чанка (по gold), либо None."""
    for i, (_, _, d, c) in enumerate(hits):
        if gold_chunks and d is not None and c is not None and (d, c) in gold_chunks:
            return i + 1
        if gold_docs and d is not None and d in gold_docs:
            return i + 1
    return None


def reciprocal_rank(
    hits: List[HitRow],
    *,
    gold_document_ids: Optional[List[int]] = None,
    gold_chunks: Optional[List[Tuple[int, int]]] = None,
) -> float:
    """RR = 1/rank первого релевантного документа/чанка (0, если не найден).

    Агрегат MRR по набору вопросов = среднее reciprocal_rank (см. mrr()).
    """
    gd = set(gold_document_ids) if gold_document_ids else None
    gc = set(gold_chunks) if gold_chunks else None
    rank = _first_relevant_rank(hits, gold_docs=gd, gold_chunks=gc)
    return (1.0 / rank) if rank else 0.0


def mrr(reciprocal_ranks: List[float]) -> float:
    """MRR = среднее reciprocal rank по всем вопросам."""
    if not reciprocal_ranks:
        return 0.0
    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def compute_retrieval_metrics(
    hits: List[HitRow],
    k: int,
    *,
    gold_document_ids: Optional[List[int]] = None,
    gold_chunks: Optional[List[Tuple[int, int]]] = None,
) -> dict:
    """Числовые retrieval-метрики одного вопроса (для online/offline пайплайнов).

    Возвращает reciprocal_rank, hit_rate@k, precision@k, recall@k, first_relevant_rank.
    Приоритет разметки: gold_chunks > gold_document_ids.
    """
    k_eff = max(k, 1)
    top = hits[:k]
    out: dict = {
        "k": k,
        "retrieved": len(hits),
        "reciprocal_rank": None,
        "hit_rate_at_k": None,
        "precision_at_k": None,
        "recall_at_k": None,
        "first_relevant_rank": None,
        "basis": None,
    }
    if gold_chunks:
        gset = set(gold_chunks)
        rset = {(d, c) for _, _, d, c in top if d is not None and c is not None}
        tp = len(rset & gset)
        out["basis"] = "gold_chunks"
        out["hit_rate_at_k"] = 1.0 if tp > 0 else 0.0
        out["precision_at_k"] = tp / k_eff
        out["recall_at_k"] = (tp / len(gset)) if gset else 0.0
        out["first_relevant_rank"] = _first_relevant_rank(hits, gold_chunks=gset)
        out["reciprocal_rank"] = reciprocal_rank(hits, gold_chunks=gold_chunks)
    elif gold_document_ids:
        gset = set(gold_document_ids)
        found = {d for _, _, d, _ in top if d is not None} & gset
        tp_hits = sum(1 for _, _, d, _ in top if d is not None and d in gset)
        out["basis"] = "gold_document_ids"
        out["hit_rate_at_k"] = 1.0 if found else 0.0
        out["precision_at_k"] = tp_hits / k_eff
        out["recall_at_k"] = len(found) / len(gset) if gset else 0.0
        out["first_relevant_rank"] = _first_relevant_rank(hits, gold_docs=gset)
        out["reciprocal_rank"] = reciprocal_rank(hits, gold_document_ids=gold_document_ids)
    return out


def _gold_chunk_metrics(
    hits: List[HitRow],
    k: int,
    gold_chunks: List[Tuple[int, int]],
) -> List[str]:
    if not gold_chunks:
        return []
    gset = set(gold_chunks)
    k_eff = max(k, 1)
    top = hits[:k]
    rset = {(d, c) for _, _, d, c in top if d is not None and c is not None}
    tp = len(rset & gset)
    hit = 1.0 if tp > 0 else 0.0
    prec = tp / k_eff
    denom = len(gset)
    rec = (tp / denom) if denom else 0.0
    rr = reciprocal_rank(hits, gold_chunks=gold_chunks)
    return [
        "эталон: чанки (document_id, chunk_index)",
        f"hit_rate@k (gold, чанки)={hit:.4f} (есть ли пересечение с эталоном)",
        f"precision@k (gold, чанки)={prec:.4f} = |релев_в_top-k|/k, релев = чанк из эталона",
        f"recall@k (gold, чанки)={rec:.4f} = |пересечение|/|эталон|, |эталон|={denom}",
        f"reciprocal_rank (gold, чанки)={rr:.4f} = 1/позиция первого релевантного чанка",
    ]


def _gold_doc_metrics(
    hits: List[HitRow],
    k: int,
    gold_docs: List[int],
) -> List[str]:
    if not gold_docs:
        return []
    gset = set(gold_docs)
    k_eff = max(k, 1)
    top = hits[:k]
    retrieved_docs = {d for _, _, d, _ in top if d is not None}
    found = retrieved_docs & gset
    tp_hits = sum(1 for _, _, d, _ in top if d is not None and d in gset)
    hit = 1.0 if found else 0.0
    prec = tp_hits / k_eff
    rec = len(found) / len(gset) if gset else 0.0
    rr = reciprocal_rank(hits, gold_document_ids=gold_docs)
    return [
        "эталон: document_id",
        f"hit_rate@k (gold, документы)={hit:.4f} (хотя бы один эталонный doc в top-k)",
        f"precision@k (gold, документы)={prec:.4f} = (хитов, чей doc в эталоне)/k",
        f"recall@k (gold, документы)={rec:.4f} = (эталонных doc, попавших в top-k)/|эталон|",
        f"reciprocal_rank (gold, документы)={rr:.4f} = 1/позиция первого эталонного doc",
    ]


async def build_eval_metric_lines(
    query: str,
    hits: List[HitRow],
    k_requested: int,
    *,
    gold_document_ids: Optional[List[int]] = None,
    gold_chunks: Optional[List[Tuple[int, int]]] = None,
    llm_judge: bool = False,
) -> List[str]:
    """Строки для блока логов «Метрики оценки»."""
    lines: List[str] = []
    k_eff = max(k_requested, 1)

    if gold_chunks:
        lines.extend(_gold_chunk_metrics(hits, k_requested, gold_chunks))
    elif gold_document_ids:
        lines.extend(_gold_doc_metrics(hits, k_requested, gold_document_ids))

    if llm_judge:
        passages = [h[0] or "" for h in hits[:k_requested]]
        flags, err = await judge_chunk_relevance(query, passages)
        n = len(passages)
        if err and err.startswith("LLM-judge отключён"):
            lines.append(f"LLM-judge: пропуск — {err}")
        elif err:
            lines.append(f"LLM-judge: ошибка — {err}")
        else:
            rel = sum(1 for i in range(n) if i < len(flags) and flags[i])
            prec_j = rel / k_eff if k_eff else 0.0
            hit_j = 1.0 if rel > 0 else 0.0
            lines.append("LLM-as-a-Judge: бинарная релевантность каждого чанка в top-k")
            lines.append(f"hit_rate@k (LLM)={hit_j:.4f}")
            lines.append(f"precision@k (LLM)={prec_j:.4f} = (чанков, помеченных релевантными)/k")
            if gold_chunks:
                top = hits[:k_requested]
                pair_to_flag: dict[tuple[int, int], bool] = {}
                for i, (_, _, d, c) in enumerate(top):
                    if d is not None and c is not None and i < len(flags):
                        pair_to_flag[(d, c)] = flags[i]
                gset = set(gold_chunks)
                llm_on_gold = sum(1 for p in gset if pair_to_flag.get(p, False))
                rec_llm_g = llm_on_gold / len(gset) if gset else 0.0
                lines.append(
                    f"recall@k (LLM∧эталон_чанки)={rec_llm_g:.4f} = "
                    f"(эталонных пар в top-k, помеченных LLM релевантными)/|эталон|"
                )
            else:
                lines.append(
                    "recall@k (LLM): без эталона (gold) не определён — знаменатель неизвестен; "
                    "передайте eval_gold_chunks для recall@k (LLM∧эталон) или eval_gold_document_ids для recall@k (gold)"
                )
            lines.append(f"LLM-judge: релевантных_чанков={rel} из {n}")

    return lines


async def log_retrieval_with_eval(
    *,
    store: str,
    strategy_resolved: str,
    pipeline: str,
    extra_lines: Optional[List[str]],
    final_hits: List[HitRow],
    k_requested: int,
    query_for_eval: str,
    search_started_perf: float,
    gold_document_ids: Optional[List[int]] = None,
    gold_chunks: Optional[List[Tuple[int, int]]] = None,
    llm_judge: bool = False,
) -> None:
    elapsed = time.perf_counter() - search_started_perf
    eval_lines = await build_eval_metric_lines(
        query_for_eval,
        final_hits,
        k_requested,
        gold_document_ids=gold_document_ids,
        gold_chunks=gold_chunks,
        llm_judge=llm_judge,
    )
    log_rag_retrieval_report(
        store=store,
        strategy_resolved=strategy_resolved,
        pipeline=pipeline,
        extra_lines=extra_lines,
        final_hits=final_hits,
        k_requested=k_requested,
        search_seconds=elapsed,
        eval_lines=eval_lines if eval_lines else None,
    )
