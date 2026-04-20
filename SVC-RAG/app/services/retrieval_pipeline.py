"""Общий retrieval-пайплайн для хранилищ KB / memory / project.

Выделен из дублирующихся ``search()``-методов. Единая логика обработки стратегий
``standard`` / ``hybrid`` (= reranking на этих сторах, потому что BM25 только у global)
/ ``graph`` / ``raw_cosine`` / ``hierarchical`` (с грейсфул fallback на standard).

Сервис передаёт два замыкания:
  - ``search_vectors(query_embedding, limit)`` — обычно обёртка над ``vector_repo.similarity_search``
    с подставленными store-специфичными аргументами (например, ``project_id``);
  - ``search_keywords(query_text, limit)`` — аналогичная обёртка над
    ``vector_repo.keyword_search``.

Возвращает:
  - ``hits`` — финальный список (content, score, document_id, chunk_index);
  - ``trace`` — ``RetrievalTrace`` со счётчиками по шагам (для ``debug_trace`` в ответе /search).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import re

from app.clients.rag_models_client import RagModelsClient
from app.database.fts import crude_russian_stem, extract_filenames, extract_proper_nouns
from app.database.graph_repository import GraphRepository
from app.database.models import DocumentVector
from app.database.search_filters import DocumentVectorSearchFilters
from app.services.hit_postprocess import apply_rerank_min_and_window
from app.services.rag_search_helpers import (
    diversify_hits_by_document,
    effective_use_reranking,
    filter_by_min_vector_similarity,
    filter_low_signal_chunks,
    keyword_boost_hits,
    merge_vector_and_keyword_hits,
    resolve_auto_pipeline_strategy,
    should_diversify_hits,
    vector_fetch_limit,
)
from app.services.rerank_helpers import rerank_vector_hits
from app.services.retrieval_eval import log_retrieval_with_eval


# Эвристика «перечислительного / меты» запроса.
# Ключевой сигнал, что пользователь хочет не ОДИН лучший ответ, а обзор по корпусу:
# «перечисли / выведи список / в каких документах / у кого / все упоминания / сколько».
# На таких запросах:
#  - расширяем пул кандидатов (widen_k),
#  - не дёргаем диверсификацию слишком агрессивно (она режет дубли по doc_id,
#    но именно эти дубли и нужны — по одному хиту на документ),
#  - entity lane (ниже) становится особенно важна.
_ENUM_PATTERNS = re.compile(
    r"(\bперечисл(и|ить)\b|\bвывед[иь]\b|\bсостав(ь|ить)\s+список\b|"
    r"\bсписок\s+документ|\bв\s+каких\s+документ|\bкакие\s+документ|"
    r"\bвсе\s+документ|\bвсе\s+упоминан|\bгде\s+упомина|\bупомина[ею]тся\b|"
    r"\bупомянут|\bсколько\s+документ|"
    # Расширение: вопросы, требующие полного перечисления по корпусу / документу.
    # «В каких местах работал X», «где учился X», «какие проекты», «какими навыками»
    # — все требуют ВЕСЬ документ (CV / биография), а не один лучший чанк.
    # ``\w+\s+`` (0–2 слов) допускает прилагательные между «какие/какими» и
    # опорным словом: «какими **хард** скиллами», «какие **мои** проекты».
    r"\bв\s+каких\s+(\w+\s+){0,2}(мест|компани|проект|вуз|университет|организаци|отдел)|"
    r"\bв\s+каком\s+(\w+\s+){0,2}(месте|университете|вузе|проекте|отделе|отделе)|"
    r"\bгде\s+(работал|училс|стажиров|преподавал|жил|трудилс|служил|практиков)|"
    r"\bкакие\s+(\w+\s+){0,2}(мест|компани|должност|проект|навык|скилл|hard|soft|язык|технолог|инструмент)|"
    r"\bкаким[иы]\s+(\w+\s+){0,2}(навык|скилл|hard|soft|технолог|язык|инструмент|проект)|"
    r"\bкакие\s+у\s+\S+\s+(есть|были|имеют|навык|скилл|проект|компетенц)|"
    r"\bчто\s+делал\b|\bчем\s+занимал|\bкаков\s+опыт|\bопыт\s+работы\b|"
    r"\bкем\s+работал|\bна\s+каких\s+должност|"
    r"\blist\s+all\b|\bwhich\s+documents?\b|\bmentions?\s+of\b|"
    r"\bwhere\s+(did|has)\s+\w+\s+work|\bwhat\s+(skills|projects)\b)"
)


def _is_enumeration_query(text: str) -> bool:
    if not text:
        return False
    return bool(_ENUM_PATTERNS.search(text.lower()))

logger = logging.getLogger(__name__)


SearchVectorsFn = Callable[
    [List[float], int],
    Awaitable[List[Tuple[DocumentVector, float]]],
]
SearchKeywordsFn = Callable[[str, int], Awaitable[List[Tuple[DocumentVector, float]]]]
# ILIKE-fallback: принимает список токенов (имена/коды из запроса) и возвращает
# чанки, где они встречаются буквально. Страховка на случай, когда FTS не
# сработал (tsvector не заполнен / OCR / редкая токенизация).
SubstringSearchFn = Callable[[List[str], int], Awaitable[List[Tuple[DocumentVector, float]]]]
# Parent-document expansion: для документа, чьи чанки попали в выдачу, можно
# вытащить соседние чанки (или весь документ). Это лечит классическую проблему
# "имя упомянуто один раз в начале документа, а подробности — в следующих
# чанках, в которых имени уже нет". Без этого CV/биография/отчёт почти всегда
# отвечают только первым чанком — не видя остального.
FetchDocumentChunksFn = Callable[[int], Awaitable[List[DocumentVector]]]
# Поиск document_id по имени файла (ILIKE). Нужен для запросов вида
# «сделай саммари по Воронин_Михаил.docx»: векторный поиск по тексту
# такого запроса не найдёт содержание документа — оно ему семантически
# перпендикулярно, но имя в запросе указано явно, и это надёжный сигнал.
FindDocsByFilenameFn = Callable[[str], Awaitable[List[int]]]


@dataclass
class RetrievalTrace:
    """Пошаговые метрики пайплайна для debug_trace в /search."""

    store: str
    requested_strategy: str
    resolved_strategy: str
    pipeline: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    used_rerank: bool = False
    warnings: List[str] = field(default_factory=list)
    seconds: float = 0.0

    def add(self, name: str, *, count: int, details: Optional[Dict[str, Any]] = None) -> None:
        entry: Dict[str, Any] = {"stage": name, "count": count}
        if details:
            entry.update(details)
        self.steps.append(entry)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("[%s] %s", self.store, msg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "store": self.store,
            "requested_strategy": self.requested_strategy,
            "resolved_strategy": self.resolved_strategy,
            "pipeline": self.pipeline,
            "used_rerank": self.used_rerank,
            "warnings": list(self.warnings),
            "steps": list(self.steps),
            "seconds": round(self.seconds, 4),
        }


async def run_retrieval_pipeline(
    *,
    store: str,
    query: str,
    vector_query: Optional[str],
    k: int,
    document_id: Optional[int],
    use_reranking: Optional[bool],
    strategy: Optional[str],
    filters: Optional[DocumentVectorSearchFilters],
    rag_client: RagModelsClient,
    graph_repo: Optional[GraphRepository],
    cfg: Any,
    search_vectors: SearchVectorsFn,
    search_keywords: SearchKeywordsFn,
    substring_search: Optional[SubstringSearchFn] = None,
    fetch_document_chunks: Optional[FetchDocumentChunksFn] = None,
    find_docs_by_filename: Optional[FindDocsByFilenameFn] = None,
    vector_repo_for_window: Any = None,
    # Метаданные для retrieval_eval / логов — опциональны:
    eval_gold_document_ids: Optional[List[int]] = None,
    eval_gold_chunks: Optional[List[Tuple[int, int]]] = None,
    eval_llm_judge: bool = False,
    log_store_label: Optional[str] = None,
) -> Tuple[List[Tuple[str, float, Optional[int], Optional[int]]], RetrievalTrace]:
    """Единая реализация retrieval-пайплайна для нон-global хранилищ."""

    q_text = (query or "").strip()
    vq = (vector_query or "").strip()
    t0 = time.perf_counter()

    requested = (strategy or "auto").lower()
    if requested == "flat":
        requested = "standard"
    # ``hierarchical`` в нон-global пока не поддерживается индексной стороной — graceful fallback.
    if requested == "hierarchical" and store != "global":
        logger.info(
            "[%s] strategy=hierarchical не поддерживается этим хранилищем, fallback=standard", store
        )
        resolved = "standard"
    elif requested == "auto":
        graph_ok = bool(graph_repo) and bool(getattr(cfg, "enable_graph_rag", True))
        resolved = resolve_auto_pipeline_strategy(
            q_text,
            store=store,
            document_id=document_id,
            hierarchical_available=False,
            graph_available=graph_ok,
            hybrid_available=bool(cfg.use_reranking),
        )
        logger.info("[%s] strategy=auto → %s", store, resolved)
    else:
        resolved = requested

    eff_rr = effective_use_reranking(
        use_reranking,
        cfg.use_reranking,
        "auto" if requested == "auto" else resolved,
        query_text=q_text,
    )

    # Имена файлов в запросе («сделай саммари по Воронин_Михаил.docx»).
    # Резолвим их в document_id ПРЕЖДЕ чем делать поиск — потому что такие
    # запросы семантически не совпадают с содержимым файла, и нормальный
    # retrieval их проваливает. Найденные документы станут anchor'ами и будут
    # целиком вытянуты parent-expansion'ом.
    filename_mentions: List[str] = extract_filenames(q_text) if q_text else []
    filename_doc_ids: List[int] = []
    if filename_mentions and find_docs_by_filename is not None:
        for fn in filename_mentions:
            try:
                ids = await find_docs_by_filename(fn)
            except Exception as e:
                logger.warning("[%s] find_docs_by_filename(%r) failed: %s", store, fn, e)
                continue
            if ids:
                filename_doc_ids.extend(ids)
            else:
                # Пробуем по стему (без расширения) — иногда пользователь пишет
                # «по Воронин_Михаил» без ".docx".
                stem = fn.rsplit(".", 1)[0]
                if stem and stem != fn:
                    try:
                        ids2 = await find_docs_by_filename(stem)
                        if ids2:
                            filename_doc_ids.extend(ids2)
                    except Exception:
                        pass
        # Дедуп с сохранением порядка.
        seen: set = set()
        filename_doc_ids = [d for d in filename_doc_ids if not (d in seen or seen.add(d))]
        if filename_doc_ids:
            logger.info(
                "[%s] filename_anchor: query mentions %s → document_ids=%s",
                store, filename_mentions, filename_doc_ids,
            )

    # Энумеративные запросы расширяем пул: топ-8 на 50-документном корпусе не даёт
    # собрать все упоминания «Константина», если среди них есть хотя бы один слабый
    # по вектору чанк. widen_k влияет на vector_fetch_limit и пост-обработку.
    # Если в запросе есть имя файла — ведём себя как при enumeration (пользователь
    # по сути просит «весь документ»).
    enumeration = _is_enumeration_query(q_text) or bool(filename_doc_ids)
    effective_k_for_fetch = k
    if enumeration:
        effective_k_for_fetch = max(k * 3, 24)

    fetch_lim = vector_fetch_limit(
        effective_k_for_fetch,
        graph=(resolved == "graph"),
        document_id=document_id,
        use_rerank=eff_rr,
        rerank_top_k=int(cfg.rerank_top_k or 20),
    )

    # Entity lane: собираем собственные имена / аббревиатуры / числовые коды
    # из запроса и готовимся в отдельной ветке достать ВСЕ чанки, где они есть.
    entity_tokens: List[str] = extract_proper_nouns(q_text) if q_text else []
    pipeline_parts = ["embed_query", f"pgvector_cosine(limit={fetch_lim})"]
    if resolved != "raw_cosine":
        pipeline_parts.append("keyword_fts_merge(OR)")
        if entity_tokens:
            pipeline_parts.append(f"entity_lane(tokens={len(entity_tokens)})")
        pipeline_parts.append(f"min_vector_similarity({float(getattr(cfg, 'min_vector_similarity', 0.0) or 0.0):.2f})")
        pipeline_parts.append(f"low_signal_filter(min_len={int(getattr(cfg, 'min_chunk_length', 40))})")
        pipeline_parts.append("keyword_boost")
    if resolved == "graph":
        pipeline_parts.append("graph_expand_neighbors")
    if document_id is None and resolved != "graph" and resolved != "raw_cosine" and not enumeration:
        pipeline_parts.append("diversify_by_document")
    if eff_rr:
        pipeline_parts.append("cross_encoder_rerank")

    trace = RetrievalTrace(
        store=store,
        requested_strategy=requested,
        resolved_strategy=resolved,
        pipeline=" -> ".join(pipeline_parts),
    )

    if not q_text and not vq:
        trace.warn("empty_query: ни query, ни vector_query не заданы")
        trace.seconds = time.perf_counter() - t0
        return [], trace

    emb_src = vq or q_text
    try:
        query_emb = await rag_client.embed([emb_src])
    except Exception as e:
        trace.warn(f"embed_error: {e}")
        await log_retrieval_with_eval(
            store=log_store_label or store,
            strategy_resolved=resolved,
            pipeline=f"{trace.pipeline} (ошибка embed)",
            extra_lines=[f"k={k}"],
            final_hits=[],
            k_requested=k,
            query_for_eval=q_text,
            search_started_perf=t0,
            gold_document_ids=eval_gold_document_ids,
            gold_chunks=eval_gold_chunks,
            llm_judge=eval_llm_judge,
        )
        trace.seconds = time.perf_counter() - t0
        return [], trace

    if not query_emb:
        trace.warn("empty_embedding: сервис rag-models вернул пустой список")
        trace.seconds = time.perf_counter() - t0
        return [], trace

    hits: List[Tuple[DocumentVector, float]] = await search_vectors(query_emb[0], fetch_lim)
    trace.add("vector_search", count=len(hits), details={"limit": fetch_lim})

    if resolved == "raw_cosine":
        rows = [(dv.content, float(sc), dv.document_id, dv.chunk_index) for dv, sc in hits[:k]]
        trace.add("raw_cosine_cut", count=len(rows))
        trace.seconds = time.perf_counter() - t0
        await log_retrieval_with_eval(
            store=log_store_label or store,
            strategy_resolved="raw_cosine",
            pipeline=f"embed_query -> pgvector_cosine(limit={fetch_lim}) (raw, no_postprocess)",
            extra_lines=[f"k={k}"],
            final_hits=rows,
            k_requested=k,
            query_for_eval=q_text,
            search_started_perf=t0,
            gold_document_ids=eval_gold_document_ids,
            gold_chunks=eval_gold_chunks,
            llm_judge=eval_llm_judge,
        )
        return rows, trace

    # --- Keyword FTS (OR-семантика) ---
    keyword_hits: List[Tuple[DocumentVector, float]] = []
    if q_text:
        try:
            keyword_hits = await search_keywords(q_text, max(k * 6, 48))
        except Exception as e:
            # Был debug — теперь warning: тихий провал keyword_search приводит
            # к чисто векторному поиску, что и ломало recall на именах/кодах.
            logger.warning("[%s] keyword_search_failed: %s", store, e)
            trace.warn(f"keyword_search_failed: {e}")
    trace.add("keyword_search", count=len(keyword_hits))

    # --- Entity lane: targeted поиск по собственным именам/кодам ---
    #
    # Это фикс кейса «упоминается Константин, но RAG говорит, что нет». Работает
    # сразу по трём каналам — все три объединяются в entity_hits:
    #
    #   1) FTS по именам (to_tsquery). Быстро и лемматизирует падежи через
    #      russian-словарь. Но может пропустить документы, где имя встречается
    #      редко (низкий ts_rank), если по другому документу совпадений много.
    #
    #   2) ILIKE-fallback со STEMMED-токенами. Раньше запускался только если FTS
    #      вернул 0 — это была ошибка: стоило одному документу много раз
    #      упомянуть имя, как ILIKE выключался и остальные файлы выпадали.
    #      Теперь — ВСЕГДА, параллельно. И с грубым стеммером: «Константина»
    #      (в запросе) ищется как %Константи%, чтобы поймать «Константин
    #      Олегович» в тексте документа. Без стеммера падежи ломают ILIKE.
    #
    #   3) Entity-in-filename. Если имя сущности встречается в ИМЕНИ файла
    #      (типичный паттерн: `Биохимия_Некрасов_СК0050629.pdf`), документ
    #      автоматически становится релевантным, даже если векторный поиск и
    #      FTS его пропустили (в теле — таблицы/цифры, OCR мог дать мусор).
    #      Тянем первые 4 чанка такого документа как entity-hits.
    entity_hits: List[Tuple[DocumentVector, float]] = []
    entity_keys: set = set()
    entity_fts_hits_n = 0
    entity_ilike_hits_n = 0
    entity_filename_docs: List[int] = []
    entity_filename_hits_n = 0
    if entity_tokens and q_text:
        # (1) FTS
        entity_query = " ".join(entity_tokens)
        try:
            fts_hits = await search_keywords(entity_query, max(k * 8, 64))
            entity_fts_hits_n = len(fts_hits)
            entity_hits.extend(fts_hits)
        except Exception as e:
            logger.warning("[%s] entity_lane_fts_failed: %s", store, e)
            trace.warn(f"entity_lane_fts_failed: {e}")

        # (2) ILIKE с падежным stemmer'ом — всегда, не только при FTS=0.
        if substring_search is not None:
            stemmed_tokens = [crude_russian_stem(t) for t in entity_tokens]
            # Не дублируем токены, если stemmer ничего не поменял.
            lookup_tokens = list(dict.fromkeys([t for t in stemmed_tokens if t]))
            if lookup_tokens:
                try:
                    ilike_hits = await substring_search(lookup_tokens, max(k * 8, 64))
                    entity_ilike_hits_n = len(ilike_hits)
                    # Дедуп с FTS-хитами: одинаковые (doc_id, chunk_idx) не добавляем.
                    existing = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}
                    for dv, sc in ilike_hits:
                        if (dv.document_id, dv.chunk_index) not in existing:
                            entity_hits.append((dv, sc))
                            existing.add((dv.document_id, dv.chunk_index))
                    if ilike_hits:
                        logger.info(
                            "[%s] entity_lane ILIKE-stemmed: tokens %s → stemmed %s → %d чанков",
                            store, entity_tokens, lookup_tokens, len(ilike_hits),
                        )
                except Exception as e:
                    logger.warning("[%s] entity_ilike_failed: %s", store, e)
                    trace.warn(f"entity_ilike_failed: {e}")

        # (3) Entity-in-filename: ищем имя в имени файла, тянем первые чанки
        # найденных документов как entity-хиты.
        if find_docs_by_filename is not None and fetch_document_chunks is not None:
            stemmed_for_filename = [crude_russian_stem(t) for t in entity_tokens]
            # Отфильтруем слишком короткие / чисто числовые, чтобы не ловить
            # случайные совпадения по датам в имени. ≥4 символов достаточно.
            filename_probe = [t for t in stemmed_for_filename if len(t) >= 4 and not t.isdigit()]
            matched_docs: set = set()
            for tok in filename_probe:
                try:
                    ids = await find_docs_by_filename(tok)
                except Exception as e:
                    logger.warning("[%s] entity_find_docs_by_filename(%r)_failed: %s", store, tok, e)
                    continue
                if ids:
                    matched_docs.update(ids)
            # Разумный cap: не более 8 документов, чтобы не взорвать контекст.
            # Если пользователь ищет «Ivanov» и у него 50 файлов с Ivanov в имени
            # — это уже сигнал переформулировать запрос, а не RAG-магия.
            matched_docs_list = sorted(matched_docs)[:8]
            if matched_docs_list:
                entity_filename_docs = matched_docs_list
                existing = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}
                added = 0
                for doc_id in matched_docs_list:
                    try:
                        chunks = await fetch_document_chunks(doc_id)
                    except Exception as e:
                        trace.warn(f"fetch_document_chunks_filename({doc_id})_failed: {e}")
                        continue
                    if not chunks:
                        continue
                    chunks_sorted = sorted(
                        chunks, key=lambda d: int(getattr(d, "chunk_index", 0) or 0)
                    )
                    # Берём первые 4 чанка: обычно «обложка + введение», достаточно
                    # чтобы LLM понял, о каком документе речь. Скор — средний
                    # (0.5), чтобы они прошли min_vector_similarity и попали в пул.
                    for dv in chunks_sorted[:4]:
                        key = (dv.document_id, dv.chunk_index)
                        if key in existing:
                            continue
                        entity_hits.append((dv, 0.5))
                        existing.add(key)
                        added += 1
                entity_filename_hits_n = added
                if added:
                    logger.info(
                        "[%s] entity_lane filename-match: tokens %s → filenames of docs %s → +%d chunks",
                        store, entity_tokens, matched_docs_list, added,
                    )

        entity_keys = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}
    trace.add(
        "entity_lane",
        count=len(entity_hits),
        details={
            "entities": entity_tokens,
            "fts_hits": entity_fts_hits_n,
            "ilike_stemmed_hits": entity_ilike_hits_n,
            "filename_matched_docs": entity_filename_docs,
            "filename_hits_added": entity_filename_hits_n,
        },
    )

    if keyword_hits or entity_hits:
        # Entity-хиты идут ВМЕСТЕ с keyword_hits: их вес в merge такой же, но
        # позже они переживут фильтры благодаря must_keep-механике.
        combined_kw: List[Tuple[DocumentVector, float]] = list(keyword_hits) + list(entity_hits)
        kw_weight = 0.65 if (resolved == "standard" and not eff_rr) else 0.35
        if enumeration:
            # При enumeration сильнее опираемся на keyword: «в каких документах упоминается X»
            # — чисто лексический вопрос, вектор здесь даёт шум.
            kw_weight = max(kw_weight, 0.7)
        before = len(hits)
        hits = merge_vector_and_keyword_hits(hits, combined_kw, keyword_weight=kw_weight)
        trace.add(
            "merge_vector_keyword",
            count=len(hits),
            details={
                "vector_before": before,
                "keyword_weight": kw_weight,
                "enumeration": enumeration,
            },
        )

    # --- Фильтры. Entity-хиты в них «бессмертны». ---
    min_sim = float(getattr(cfg, "min_vector_similarity", 0.0) or 0.0)
    before = len(hits)
    if entity_keys:
        pinned = [h for h in hits if (h[0].document_id, h[0].chunk_index) in entity_keys]
        rest = [h for h in hits if (h[0].document_id, h[0].chunk_index) not in entity_keys]
        rest = filter_by_min_vector_similarity(rest, min_sim, k)
        hits = pinned + rest
    else:
        hits = filter_by_min_vector_similarity(hits, min_sim, k)
    trace.add(
        "min_similarity_filter",
        count=len(hits),
        details={
            "min_vector_similarity": min_sim,
            "before": before,
            "pinned_by_entity": len(entity_keys),
        },
    )

    before = len(hits)
    if entity_keys:
        pinned = [h for h in hits if (h[0].document_id, h[0].chunk_index) in entity_keys]
        rest = [h for h in hits if (h[0].document_id, h[0].chunk_index) not in entity_keys]
        rest = filter_low_signal_chunks(
            rest, min_len=int(getattr(cfg, "min_chunk_length", 40)), rescue_keep=max(k * 3, 12)
        )
        hits = pinned + rest
    else:
        hits = filter_low_signal_chunks(
            hits, min_len=int(getattr(cfg, "min_chunk_length", 40)), rescue_keep=max(k * 3, 12)
        )
    trace.add(
        "low_signal_filter",
        count=len(hits),
        details={"min_len": int(getattr(cfg, "min_chunk_length", 40)), "before": before},
    )

    before = len(hits)
    hits = keyword_boost_hits(hits, q_text)
    trace.add("keyword_boost", count=len(hits))

    # На enumeration-запросах диверсификация мешает: именно дубли по doc_id
    # (разные чанки одного файла, где встречается имя) — ценность, а не шум.
    # А внизу при обрезке до k мы дадим всем документам-носителям entity шанс.
    if (
        document_id is None
        and hits
        and resolved != "graph"
        and not enumeration
        and should_diversify_hits(hits)
    ):
        pool = max(int(cfg.rerank_top_k or 20), k * 6, 56)
        hits = diversify_hits_by_document(hits, min(pool, len(hits)))
        trace.add("diversify_by_document", count=len(hits))

    if resolved == "graph" and hits:
        seed_pairs = [
            (dv.document_id, dv.chunk_index)
            for dv, _ in hits[: min(12, len(hits))]
            if dv.document_id is not None
        ]
        seed_chunk_indexes = [p[1] for p in seed_pairs]
        graph_scores: Dict[Tuple[int, int], float] = {}
        if graph_repo and seed_pairs:
            try:
                graph_scores = await graph_repo.expand_neighbors(
                    store_type=store,
                    document_id=document_id,
                    seed_chunk_indexes=seed_chunk_indexes,
                    max_hops=2,
                    max_nodes=max(k * 4, 40),
                    seed_doc_chunk_pairs=seed_pairs if document_id is None else None,
                )
            except Exception as e:
                trace.warn(f"graph_expand_failed: {e}")
        boosted = []
        for dv, base_score in hits:
            gscore = graph_scores.get((dv.document_id, dv.chunk_index), 0.0)
            boosted.append((dv, 0.7 * float(base_score) + 0.3 * float(gscore)))
        boosted.sort(key=lambda x: x[1], reverse=True)
        hits = boosted
        trace.add("graph_expand", count=len(hits), details={"graph_neighbors": len(graph_scores)})

    used_rr = False
    if eff_rr and hits:
        try:
            hits = await rerank_vector_hits(
                q_text,
                hits,
                rag_client,
                top_k=max(len(hits), k * 4, int(cfg.rerank_top_k or 20)),
                vector_weight=0.3,
            )
            used_rr = True
            trace.add("cross_encoder_rerank", count=len(hits))
        except Exception as e:
            trace.warn(f"rerank_failed: {e}")
    trace.used_rerank = used_rr

    # --- Parent-document expansion ---
    #
    # Две разные ситуации — разные режимы агрессивности:
    #
    # 1) FILENAME-anchor: пользователь явно назвал файл («саммари по X.docx»).
    #    Это override — тянем ВЕСЬ документ (до 20 чанков), пиним его впереди.
    #
    # 2) ENTITY-anchor: имя встретилось в документе (entity FTS/ILIKE). Это
    #    мягкий сигнал: имя может быть в N документах, и не всегда документ с
    #    entity — тот, что реально нужен. Нельзя цеплять весь CV, если вопрос
    #    про другой документ, где тоже упомянут Константин. Здесь:
    #      - entity-чанки пиннятся (сами по себе, это точечное попадание),
    #      - сиблингов даём максимум 2 на документ и НЕ пиним весь документ,
    #      - score сиблингов существенно ниже — чтобы не выжимать другие доки.
    #
    # 3) ENUMERATION без entity («где работал Константин», а имя не извлеклось):
    #    средний режим — top-3 документа по скору, 4 сиблинга, без пининга всего.
    sibling_added = 0
    sibling_keys: set = set()
    # Документы, которые пиним целиком (только filename-anchor!).
    pin_whole_doc_ids: set = set(filename_doc_ids or [])
    # Все документы, из которых тянем сиблинги — для трейса и учёта в финальном срезе.
    all_anchor_docs: set = set(pin_whole_doc_ids)
    entity_anchor_docs: set = set()
    if fetch_document_chunks is not None and (hits or all_anchor_docs):
        # 2) Entity-anchor — документы, где entity реально нашёлся.
        for dv, _ in hits:
            if (dv.document_id, dv.chunk_index) in entity_keys:
                entity_anchor_docs.add(dv.document_id)
        all_anchor_docs.update(entity_anchor_docs)
        # 3) Enumeration top-3 (только если entity не извлеклась — иначе entity уже
        # описывает, какие документы релевантны, и доп. top-N нам не нужен).
        enum_anchor_docs: set = set()
        if enumeration and hits and not entity_anchor_docs:
            top_docs_by_score: Dict[Any, float] = {}
            for dv, sc in hits:
                if dv.document_id not in top_docs_by_score or float(sc) > top_docs_by_score[dv.document_id]:
                    top_docs_by_score[dv.document_id] = float(sc)
            for doc_id, _ in sorted(top_docs_by_score.items(), key=lambda x: x[1], reverse=True)[:3]:
                enum_anchor_docs.add(doc_id)
        all_anchor_docs.update(enum_anchor_docs)

        if all_anchor_docs:
            existing_keys = {(dv.document_id, dv.chunk_index) for dv, _ in hits}
            base_sibling_score = min((float(sc) for _, sc in hits), default=0.01) * 0.5
            if base_sibling_score <= 0:
                base_sibling_score = 0.01
            # Разные капы на разные режимы:
            #   filename: целиком документ (до 20 чанков);
            #   enumeration (без entity): по 4 чанка на топ-3;
            #   entity-anchor: по 2 чанка — только чтобы поймать ближайший контекст
            #     вокруг entity-чанка, НЕ весь документ.
            def _cap(doc_id: Any) -> int:
                if doc_id in pin_whole_doc_ids:
                    return 20
                if doc_id in entity_anchor_docs:
                    return 2
                if doc_id in enum_anchor_docs:
                    return 4
                return 0
            # Для entity-anchor используем ещё более низкий base_score, чтобы
            # сиблинги «CV» не вытесняли чанки других документов с таким же именем.
            entity_sibling_score = base_sibling_score * 0.5
            expanded: List[Tuple[DocumentVector, float]] = []
            for doc_id in all_anchor_docs:
                cap = _cap(doc_id)
                if cap <= 0:
                    continue
                try:
                    doc_chunks = await fetch_document_chunks(doc_id)
                except Exception as e:
                    trace.warn(f"fetch_document_chunks({doc_id})_failed: {e}")
                    continue
                if not doc_chunks:
                    continue
                doc_chunks_sorted = sorted(
                    doc_chunks, key=lambda d: int(getattr(d, "chunk_index", 0) or 0)
                )
                # Для entity-anchor тянем чанки соседние к entity-чанку (контекст),
                # а не c самого начала документа. Это разумнее: entity в середине
                # CV → берём сосед слева/справа, а не обложку документа.
                entity_chunk_indices = {
                    dv.chunk_index for dv in doc_chunks_sorted
                    if (dv.document_id, dv.chunk_index) in entity_keys
                }
                if doc_id in entity_anchor_docs and entity_chunk_indices:
                    # Сортируем по близости к entity-чанкам: индексы, которые
                    # соседние (±1, ±2) к entity, приоритетнее.
                    def _proximity(ci: int) -> int:
                        return min(abs(ci - e) for e in entity_chunk_indices)
                    doc_chunks_sorted = sorted(
                        doc_chunks_sorted,
                        key=lambda d: (
                            _proximity(int(getattr(d, "chunk_index", 0) or 0)),
                            int(getattr(d, "chunk_index", 0) or 0),
                        ),
                    )
                taken = 0
                sib_score = (
                    entity_sibling_score if doc_id in entity_anchor_docs
                    else base_sibling_score
                )
                for dv in doc_chunks_sorted:
                    if taken >= cap:
                        break
                    key = (dv.document_id, dv.chunk_index)
                    if key in existing_keys:
                        continue
                    # Для filename-anchor сиблинг — любая страница документа.
                    # Для entity-anchor — только соседи entity-чанка (proximity ≤ 2).
                    if doc_id in entity_anchor_docs and entity_chunk_indices:
                        if _proximity(int(getattr(dv, "chunk_index", 0) or 0)) > 2:
                            break
                    expanded.append((dv, sib_score))
                    existing_keys.add(key)
                    sibling_keys.add(key)
                    taken += 1
            if expanded:
                hits = hits + expanded
                sibling_added = len(expanded)
    trace.add(
        "parent_document_expansion",
        count=sibling_added,
        details={
            "pin_whole_doc_ids": sorted(list(pin_whole_doc_ids)),
            "entity_anchor_docs": sorted(list(entity_anchor_docs)),
            "enum_anchor_docs": sorted(list(all_anchor_docs - pin_whole_doc_ids - entity_anchor_docs)),
        },
    )

    # --- Финальный срез до k ---
    # Ключевое различие в пининге:
    #   - filename-anchor: ВСЕ чанки документа идут вперёд (override).
    #   - entity-anchor: ТОЛЬКО сами entity-чанки пиннятся (не весь документ).
    #     Сиблинги лежат в общей куче с пониженным score и пробиваются или нет
    #     по общему ранжированию — это и нужно, чтобы CV не «магнитил» запросы
    #     про другой документ.
    final_limit = k * 2 if enumeration else k
    hits_sorted = hits
    has_pinning = bool(entity_keys or pin_whole_doc_ids)
    if has_pinning:
        anchor_chunks: List[Tuple[DocumentVector, float]] = []
        seen_keys: set = set()
        for dv, sc in hits_sorted:
            key = (dv.document_id, dv.chunk_index)
            is_entity = key in entity_keys
            is_whole_doc_pin = dv.document_id in pin_whole_doc_ids
            # is_sibling сам по себе НЕ пиннится (см. комментарий выше).
            if is_entity or is_whole_doc_pin:
                if key not in seen_keys:
                    anchor_chunks.append((dv, float(sc)))
                    seen_keys.add(key)
        # Порядок anchor-чанков: по документу и chunk_index (естественный порядок чтения).
        anchor_chunks.sort(
            key=lambda t: (
                int(t[0].document_id or 0),
                int(getattr(t[0], "chunk_index", 0) or 0),
            )
        )
        others = [
            h for h in hits_sorted
            if (h[0].document_id, h[0].chunk_index) not in seen_keys
        ]
        merged = anchor_chunks + others
        # Расширяем лимит только на pinned anchor_chunks (entity+filename), а не
        # на все сиблинги — иначе вылезет старый magnet-эффект.
        hits_sorted = merged[: max(final_limit, len(anchor_chunks))]
        trace.add(
            "entity_documents_pinned",
            count=len(anchor_chunks),
            details={
                "entity_chunks": sum(
                    1 for dv, _ in anchor_chunks if (dv.document_id, dv.chunk_index) in entity_keys
                ),
                "whole_doc_pin_chunks": sum(
                    1 for dv, _ in anchor_chunks if dv.document_id in pin_whole_doc_ids
                ),
                "documents": sorted(list({dv.document_id for dv, _ in anchor_chunks})),
            },
        )
    else:
        hits_sorted = hits_sorted[:final_limit]

    # hits_sorted уже ограничен max(final_limit, len(anchor_chunks)) выше — не режем заново.
    rows = [(dv.content, float(sc), dv.document_id, dv.chunk_index) for dv, sc in hits_sorted]
    final = await apply_rerank_min_and_window(
        vector_repo_for_window,
        rows,
        rerank_min_score=float(cfg.rerank_min_score or 0),
        sentence_window=int(cfg.sentence_window or 0),
        used_rerank=used_rr,
    )
    trace.add("post_rerank_window", count=len(final))

    await log_retrieval_with_eval(
        store=log_store_label or store,
        strategy_resolved=resolved,
        pipeline=trace.pipeline,
        extra_lines=[
            f"k={k}",
            f"document_id={'все' if document_id is None else document_id}",
            f"кандидатов_из_pgvector={fetch_lim}",
            f"реранк_cross_encoder={'да' if eff_rr else 'нет'}",
            f"реранк_применён={'да' if used_rr else 'нет'}",
        ],
        final_hits=final,
        k_requested=k,
        query_for_eval=q_text,
        search_started_perf=t0,
        gold_document_ids=eval_gold_document_ids,
        gold_chunks=eval_gold_chunks,
        llm_judge=eval_llm_judge,
    )
    trace.seconds = time.perf_counter() - t0
    return final, trace
