"""Общая логика поиска для KB / memory_rag / project_rag (не global RagService).

Факторы, которые обычно снижают качество RAG (для ориентира при чтении метрик):
- Слишком большой или слишком мелкий chunk / плохое перекрытие → потеря контекста или шум.
- Только вектор без BM25 (или наоборот) при несовпадении формулировки запроса и документа.
- Узкий top-k из pgvector при многих документах → «вытеснение» релевантных файлов.
- Высокий RAG_RERANK_MIN_SCORE / RAG_MIN_VECTOR_SIMILARITY на backend → пустой контекст.
- Слабый парсинг PDF/сканов → пустые или короткие чанки.
- Реранкер выключен при auto → порядок только по эмбеддингу.
"""

from __future__ import annotations

import logging
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from app.database.models import DocumentVector

logger = logging.getLogger(__name__)

TVec = TypeVar("TVec", bound=DocumentVector)


def effective_use_reranking(
    requested: Optional[bool],
    cfg_rerank_enabled: bool,
    strategy: str,
) -> bool:
    """standard — только вектор (без реранка).
    hybrid    — BM25+вектор (global) или вектор+реранк (non-global); включает реранк если он в конфиге.
    reranking — только реранк по конфигу.
    auto      — по конфигу и флагу запроса.
    """
    st = (strategy or "auto").lower()
    if st == "standard":
        return False
    if st in ("hybrid", "reranking"):
        if not cfg_rerank_enabled:
            return False
        return True if requested is None else bool(requested)
    return (requested if requested is not None else cfg_rerank_enabled) and cfg_rerank_enabled


def resolve_auto_pipeline_strategy(
    query: str,
    *,
    store: str,
    document_id: Optional[int],
    hierarchical_available: bool,
    graph_available: bool,
    hybrid_available: bool,
) -> str:
    """
    Для strategy=auto выбирает фактический режим: hierarchical | graph | reranking | standard.

    - RAG_AUTO_MODE=heuristic (по умолчанию): эвристики по тексту запроса + доступности.
    - RAG_AUTO_MODE=priority: первый доступный из списка приоритетов.

    Примечания:
    - Иерархический — только глобальное хранилище и без ограничения одним document_id.
    - Hybrid (BM25+вектор) — только global. Для KB/memory/project выбирается "reranking"
      (вектор + cross-encoder реранк) вместо "hybrid", т.к. BM25 там не поддерживается.
    """
    q = (query or "").strip().lower()
    qlen = len(q)
    mode = (os.environ.get("RAG_AUTO_MODE") or "heuristic").strip().lower()

    can_h = bool(hierarchical_available and document_id is None and store == "global")
    can_g = bool(graph_available)
    # Гибрид с BM25 только в global; для остальных хранилищ доступен "reranking"
    can_hybrid_bm25 = bool(hybrid_available and store == "global")
    can_reranking = bool(hybrid_available and store != "global")
    if document_id is not None:
        can_h = False

    if mode == "priority":
        if store == "global":
            order = ["hybrid", "graph", "hierarchical", "standard"]
        else:
            order = ["reranking", "graph", "standard"]
        avail = {
            "hybrid": can_hybrid_bm25,
            "reranking": can_reranking,
            "graph": can_g,
            "hierarchical": can_h,
            "standard": True,
        }
        for choice in order:
            if avail.get(choice):
                return choice
        return "standard"

    # --- heuristic ---
    scores: Dict[str, float] = {"standard": 0.5}
    if can_hybrid_bm25:
        scores["hybrid"] = 2.0
        if qlen < 72 and q.count(" ") <= 10:
            scores["hybrid"] += 1.5
        if any(ch.isdigit() for ch in q) and qlen < 100:
            scores["hybrid"] += 0.8
    if can_reranking:
        scores["reranking"] = 1.8
        if qlen < 72 and q.count(" ") <= 10:
            scores["reranking"] += 1.2
    if can_g:
        scores["graph"] = 1.2
        if any(
            tok in q
            for tok in (
                "связ",
                "почему",
                "как связ",
                "отличи",
                "сравни",
                "между",
                "влияни",
                "последств",
                "цепочк",
                "граф",
                "нескольк",
            )
        ):
            scores["graph"] += 2.2
        if "?" in q and qlen > 35:
            scores["graph"] += 0.6
        if qlen > 140:
            scores["graph"] += 0.4
    if can_h:
        scores["hierarchical"] = 1.0
        if any(
            tok in q
            for tok in (
                "кратк",
                "обзор",
                "summary",
                "целиком",
                "о чем документ",
                "содержан",
                "структур",
                "раздел",
            )
        ):
            scores["hierarchical"] += 2.5
        if qlen > 220:
            scores["hierarchical"] += 0.8

    tie = ("hybrid", "reranking", "graph", "hierarchical", "standard")
    best = min(scores.keys(), key=lambda s: (-scores[s], tie.index(s) if s in tie else 99))
    return best


def vector_fetch_limit(
    k: int,
    *,
    graph: bool,
    document_id: Optional[int],
    use_rerank: bool,
    rerank_top_k: int,
) -> int:
    """Сколько чанков забрать из pgvector до реранка / диверсификации."""
    if graph:
        return max(k * 4, 36)
    if document_id is not None:
        return max(56, k * 5)
    if use_rerank:
        return max(rerank_top_k, k * 10, 120)
    return max(120, k * 14, 100)


def filter_by_min_vector_similarity(
    hits: List[Tuple[DocumentVector, float]],
    min_similarity: float,
    k: int,
) -> List[Tuple[DocumentVector, float]]:
    """
    Отсекает чанки с косинусным сходством ниже порога до реранка.
    Если ничего не прошло порог — возвращает пустой список: LLM получит пустой контекст
    и правильно ответит «документов по теме нет». Fallback-минимум убран намеренно.
    """
    if min_similarity <= 0 or not hits:
        return hits
    filtered = [h for h in hits if h[1] >= min_similarity]
    if filtered:
        if len(filtered) < len(hits):
            logger.info(
                "[RAG] min_vector_similarity=%.3f: %d/%d чанков выше порога (отброшено %d нерелевантных)",
                min_similarity,
                len(filtered),
                len(hits),
                len(hits) - len(filtered),
            )
        return filtered
    logger.info(
        "[RAG] min_vector_similarity=%.3f: все %d чанков ниже порога → пустой контекст (LLM скажет «не найдено»)",
        min_similarity,
        len(hits),
    )
    return []


_KEYWORD_STOPWORDS = {
    "и", "в", "на", "по", "из", "с", "к", "у", "о", "а", "но", "что", "как",
    "это", "не", "он", "она", "они", "мы", "вы", "я", "его", "её", "их", "был",
    "для", "или", "при", "за", "до", "без", "то", "бы", "ли", "уже", "ещё",
    "the", "is", "in", "of", "to", "and", "for", "are", "was", "with",
}


def keyword_boost_hits(
    hits: List[Tuple[DocumentVector, float]],
    query: str,
    boost_factor: float = 0.30,
) -> List[Tuple[DocumentVector, float]]:
    """Повышает скор чанков с точными вхождениями слов запроса.

    Критично для имён собственных, аббревиатур и цифр — сигналов, которые
    embedding-модель нивелирует в пользу тематических слов.
    boost_factor: макс. надбавка к скору при 100% совпадении слов (0.30 = +30%).
    """
    if not hits or not query.strip():
        return hits
    query_words = {
        w.lower()
        for w in re.findall(r"\b\w{3,}\b", query)
        if w.lower() not in _KEYWORD_STOPWORDS
    }
    if not query_words:
        return hits
    boosted = []
    for dv, score in hits:
        content_lower = (dv.content or "").lower()
        matched = sum(1 for w in query_words if w in content_lower)
        ratio = matched / len(query_words)
        new_score = float(score) * (1.0 + boost_factor * ratio)
        boosted.append((dv, new_score))
    return sorted(boosted, key=lambda x: x[1], reverse=True)


def diversify_result_rows(
    rows: List[Tuple[str, float, Optional[int], Optional[int]]],
    pool_limit: int,
) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
    """
    Post-rerank диверсификация для финального списка (content, score, doc_id, chunk_idx).
    Гарантирует хотя бы 1 строку от каждого документа в первых pool_limit результатах.
    """
    if not rows or pool_limit <= 0:
        return []
    rows_sorted = sorted(rows, key=lambda x: x[1], reverse=True)
    best_per_doc: Dict[Optional[int], Tuple[str, float, Optional[int], Optional[int]]] = {}
    for row in rows_sorted:
        did = row[2]
        if did not in best_per_doc or row[1] > best_per_doc[did][1]:
            best_per_doc[did] = row

    merged: List[Tuple[str, float, Optional[int], Optional[int]]] = []
    seen: set = set()
    for item in sorted(best_per_doc.values(), key=lambda x: x[1], reverse=True):
        if len(merged) >= pool_limit:
            break
        key = (item[2], item[3])
        if key not in seen:
            merged.append(item)
            seen.add(key)

    for row in rows_sorted:
        if len(merged) >= pool_limit:
            break
        key = (row[2], row[3])
        if key not in seen:
            merged.append(row)
            seen.add(key)

    return merged


def diversify_hits_by_document(
    hits: List[Tuple[DocumentVector, float]],
    pool_limit: int,
) -> List[Tuple[DocumentVector, float]]:
    """
    Из расширенного пула берём до pool_limit чанков: сначала лучший чанк с каждого document_id,
    затем добор по общему скору. Так PDF не вытесняется одними только топ-чанками больших DOCX.
    """
    if not hits or pool_limit <= 0:
        return []
    hits_sorted = sorted(hits, key=lambda x: x[1], reverse=True)
    best_per_doc: Dict[int, Tuple[DocumentVector, float]] = {}
    for dv, sc in hits_sorted:
        did = dv.document_id
        if did is None:
            continue
        if did not in best_per_doc or sc > best_per_doc[did][1]:
            best_per_doc[did] = (dv, sc)

    merged: List[Tuple[DocumentVector, float]] = []
    seen: set = set()
    for item in sorted(best_per_doc.values(), key=lambda x: x[1], reverse=True):
        if len(merged) >= pool_limit:
            break
        dv, sc = item
        key = (dv.document_id, dv.chunk_index)
        if key not in seen:
            merged.append((dv, sc))
            seen.add(key)

    for dv, sc in hits_sorted:
        if len(merged) >= pool_limit:
            break
        key = (dv.document_id, dv.chunk_index)
        if key not in seen:
            merged.append((dv, sc))
            seen.add(key)

    return merged



BANNER_WIDTH = 72


def build_retrieval_metrics_lines(
    hits: List[Tuple[str, float, Optional[int], Optional[int]]],
    k_requested: int,
) -> List[str]:
    """Эвристики по финальному списку чанков (без эталонных ответов — для мониторинга в логах)."""
    if not hits:
        return [
            f"hits_в_ответе=0 k_запрошено={k_requested}",
            "подсказка: проверьте пороги релевантности, парсинг документов и запрос",
        ]

    scores = [float(h[1]) for h in hits]
    contents = [(h[0] or "") for h in hits]
    doc_ids = [h[2] for h in hits if h[2] is not None]
    uniq_docs = len(set(doc_ids)) if doc_ids else 0
    n = len(scores)
    mean_s = sum(scores) / n
    var = sum((s - mean_s) ** 2 for s in scores) / n if n else 0.0
    std_s = math.sqrt(var)

    lines = [
        f"hits_в_ответе={n} k_запрошено={k_requested}",
        f"score: top1={scores[0]:.4f} mean={mean_s:.4f} min={min(scores):.4f} max={max(scores):.4f} std={std_s:.4f}",
    ]
    if n >= 2:
        margin = scores[0] - scores[1]
        lines.append(f"margin_top1_minus_top2={margin:.4f} (мало → похожие кандидаты, выше неоднозначность)")
    lines.append(f"уникальных_document_id={uniq_docs} (мало при многих файлах в корпусе → узкий захват)")

    lens = [len(c) for c in contents]
    total_ctx = sum(lens)
    avg_len = total_ctx // n if n else 0
    lines.append(f"текст_чанков_симв: avg={avg_len} min={min(lens)} max={max(lens)} сумма_в_контекст={total_ctx}")

    short = sum(1 for L in lens if L < 80)
    if short:
        lines.append(f"очень_коротких_чанков(<80 симв)={short} → мало сигнала для LLM")

    empty_c = sum(1 for c in contents if not c.strip())
    if empty_c:
        lines.append(f"пустых_чанков={empty_c} → проверьте индексацию/парсинг")

    low_score = sum(1 for s in scores if s < 0.15)
    if low_score and n >= 2:
        lines.append(f"низкий_score(<0.15)={low_score} → риск «слабой опоры», смотрите пороги на backend")

    return lines


def log_rag_retrieval_report(
    *,
    store: str,
    strategy_resolved: str,
    pipeline: str,
    extra_lines: Optional[List[str]] = None,
    final_hits: List[Tuple[str, float, Optional[int], Optional[int]]],
    k_requested: int,
    search_seconds: Optional[float] = None,
    eval_lines: Optional[List[str]] = None,
) -> None:
    """Один блок в логах: стратегия + параметры + метрики по выдаче."""
    bar = "*" * BANNER_WIDTH
    stdout_metrics = os.environ.get("RAG_METRICS_STDOUT", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    stdout_lines: List[str] = []

    def _emit(text: str) -> None:
        logger.info("%s", text)
        if stdout_metrics:
            stdout_lines.append(text)

    _emit(bar)
    _emit(f"[SVC-RAG] Использована стратегия поиска: {strategy_resolved}")
    _emit(f"[SVC-RAG] Хранилище: {store}")
    _emit(f"[SVC-RAG] Пайплайн: {pipeline}")
    if extra_lines:
        for line in extra_lines:
            _emit(f"[SVC-RAG] {line}")
    if search_seconds is not None:
        _emit(
            f"[SVC-RAG] время_поиска_с={search_seconds:.4f} (retrieval, постобработка, опционально LLM-judge)"
        )
    _emit("[SVC-RAG] --- Метрики retrieval (финальная выдача) ---")
    for line in build_retrieval_metrics_lines(final_hits, k_requested):
        _emit(f"[SVC-RAG]   {line}")
    if eval_lines:
        _emit("[SVC-RAG] --- Метрики оценки (gold / LLM-judge) ---")
        for line in eval_lines:
            _emit(f"[SVC-RAG]   {line}")
    _emit(bar)
    if stdout_metrics and stdout_lines:
        try:
            sys.stderr.write("\n".join(stdout_lines) + "\n")
            sys.stderr.flush()
        except Exception:
            pass
