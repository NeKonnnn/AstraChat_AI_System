# Индексация документов и поиск: парсинг → чанки → эмбеддинги (RAG-MODELS) → pgvector, опционально BM25 и реранк
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rank_bm25 import BM25Okapi

from app.clients.rag_models_client import RagModelsClient
from app.core.config import get_settings
from app.database.models import Document, DocumentVector
from app.database.repository import DocumentRepository, VectorRepository
from app.database.search_filters import DocumentVectorSearchFilters
from app.services.hit_postprocess import apply_rerank_min_and_window
from app.services.retrieval_eval import log_retrieval_with_eval
from app.services.rag_search_helpers import (
    diversify_hits_by_document,
    effective_use_reranking,
    filter_low_signal_chunks,
    filter_by_min_vector_similarity,
    keyword_boost_hits,
    merge_vector_and_keyword_hits,
    resolve_auto_pipeline_strategy,
    should_diversify_hits,
    vector_fetch_limit,
)
from app.database.fts import crude_russian_stem, extract_filenames, extract_proper_nouns
from app.database.graph_repository import GraphRepository
from app.services.chunker import split_into_chunks, split_into_chunks_with_meta
from app.services.document_parser import parse_document
from app.services.hierarchical import DocumentSummarizer, OptimizedDocumentIndex
from app.services.retrieval_pipeline import _is_enumeration_query

logger = logging.getLogger(__name__)


def _tokenize_ru_en(text: str) -> List[str]:
    """Простая токенизация для BM25: по пробелам и пунктуации."""
    import re
    text = (text or "").lower()
    return re.findall(r"\b\w+\b", text)


class RagService:
    def __init__(
        self,
        document_repo: DocumentRepository,
        vector_repo: VectorRepository,
        rag_models_client: RagModelsClient,
        graph_repo: Optional[GraphRepository] = None,
    ):
        self.document_repo = document_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client
        cfg = get_settings().rag
        self._cfg = cfg
        self.graph_repo = graph_repo
        self.graph_enabled: bool = bool(getattr(cfg, "enable_graph_rag", True))

        # BM25 / гибридный поиск 
        self.use_hybrid_search: bool = cfg.use_hybrid_search
        self.hybrid_bm25_weight: float = cfg.hybrid_bm25_weight
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_texts: List[str] = []
        self.bm25_metadatas: List[Dict[str, Any]] = []
        self._bm25_needs_rebuild: bool = False

        # Иерархия: суммаризатор и оптимизированный индекс (при включённой настройке)
        self._summarizer: Optional[DocumentSummarizer] = None
        self._optimized_index: Optional[OptimizedDocumentIndex] = None
        if cfg.use_hierarchical_indexing:
            llm_cfg = get_settings().llm_service
            async def _llm_summarize(prompt: str) -> str:
                try:
                    async with httpx.AsyncClient(timeout=llm_cfg.timeout) as client:
                        r = await client.post(
                            f"{llm_cfg.base_url.rstrip('/')}/v1/chat/completions",
                            json={
                                "model": llm_cfg.default_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.3,
                                "max_tokens": 2000,
                                "stream": False,
                            },
                        )
                        r.raise_for_status()
                        data = r.json()
                        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                except Exception as e:
                    logger.warning("LLM суммаризация не удалась: %s", e)
                    return ""

            self._summarizer = DocumentSummarizer(
                llm_function=_llm_summarize,
                max_chunk_size=cfg.hierarchical_chunk_size,
                chunk_overlap=cfg.hierarchical_chunk_overlap,
                intermediate_summary_chunks=cfg.intermediate_summary_chunks,
            )
            self._optimized_index = OptimizedDocumentIndex(self.rag_client, self.vector_repo)

    async def warm_up(self) -> None:
        """Прогрев сервиса на старте SVC-RAG.

        Сейчас собирает BM25-индекс один раз, чтобы первый гибридный/auto-запрос
        не висел 1-5 секунд на горячем построении индекса (особенно после рестарта).
        Безопасно вызывать многократно: перестроит при ``_bm25_needs_rebuild=True``.
        """
        if not self.use_hybrid_search:
            return
        try:
            await self._build_bm25_index()
            self._bm25_needs_rebuild = False
            logger.info(
                "[SVC-RAG] warm_up: BM25-индекс готов (chunks=%d)", len(self.bm25_texts)
            )
        except Exception as e:
            logger.warning("[SVC-RAG] warm_up: BM25 не построен: %s", e)

    async def _finalize_hit_rows(
        self,
        rows: List[Tuple[str, float, Optional[int], Optional[int]]],
        *,
        used_rerank: bool,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        return await apply_rerank_min_and_window(
            self.vector_repo,
            rows,
            rerank_min_score=float(getattr(self._cfg, "rerank_min_score", 0) or 0),
            sentence_window=int(getattr(self._cfg, "sentence_window", 0) or 0),
            used_rerank=used_rerank,
        )

    async def index_document(
        self,
        file_data: bytes,
        filename: str,
        image_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Парсим файл, режем на чанки, получаем эмбеддинги из SVC-RAG-MODELS, пишем в БД.

        image_meta: опциональные данные о файле/MinIO:
            {
                "path": str | None,
                "minio_object": str | None,
                "minio_bucket": str | None,
            }
        Эти данные сохраняются в metadata документа (ключ image_info), чтобы backend
        мог восстановить информацию об изображении/объекте MinIO.
        """
        parsed = await parse_document(file_data, filename)
        if not parsed:
            return {"ok": False, "error": "Не удалось извлечь текст или формат не поддерживается", "document_id": None}

        text = (parsed.get("text") or "").strip()
        confidence_info = parsed.get("confidence_info")
        ftype = (parsed.get("file_type") or "").lower()

        if not text:
            if ftype == "pdf":
                return {
                    "ok": False,
                    "error": "PDF без извлекаемого текста (скан без OCR или сбой ocr-service/poppler). См. логи svc-rag.",
                    "document_id": None,
                }
            return {"ok": False, "error": "Не удалось извлечь текст или формат не поддерживается", "document_id": None}

        use_hierarchical = (
            self._cfg.use_hierarchical_indexing
            and len(text) > self._cfg.hierarchical_threshold
            and self._summarizer is not None
            and self._optimized_index is not None
        )

        if use_hierarchical:
            hierarchical_doc = await self._summarizer.create_hierarchical_summary_async(
                text,
                filename,
                create_full_summary=self._cfg.create_full_summary_via_llm,
            )
            meta: Dict[str, Any] = {
                "chunks_count": hierarchical_doc["metadata"]["total_chunks"],
                "source": "svc-rag",
                "hierarchical": True,
            }
            if confidence_info:
                meta["confidence_data"] = confidence_info
            if image_meta:
                meta["image_info"] = {
                    "path": image_meta.get("path"),
                    "minio_object": image_meta.get("minio_object"),
                    "minio_bucket": image_meta.get("minio_bucket"),
                }
            doc = Document(
                filename=filename,
                content=text,
                metadata=meta,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            doc_id = await self.document_repo.create_document(doc)
            if not doc_id:
                return {"ok": False, "error": "Не удалось сохранить документ в БД", "document_id": None}
            ok = await self._optimized_index.index_document_hierarchical_async(hierarchical_doc, doc_id)
            if not ok:
                await self.document_repo.delete_document(doc_id)
                return {"ok": False, "error": "Ошибка иерархической индексации", "document_id": None}
            if self.use_hybrid_search:
                self._bm25_needs_rebuild = True
            return {
                "ok": True,
                "document_id": doc_id,
                "filename": filename,
                "chunks_count": hierarchical_doc["metadata"]["total_chunks"],
            }

        chunks_with_meta = split_into_chunks_with_meta(text)
        if not chunks_with_meta:
            return {"ok": False, "error": "После разбиения чанков не осталось", "document_id": None}
        chunks = [c for c, _m in chunks_with_meta]

        metadata: Dict[str, Any] = {"chunks_count": len(chunks), "source": "svc-rag"}
        if confidence_info:
            metadata["confidence_data"] = confidence_info
        if image_meta:
            metadata["image_info"] = {
                "path": image_meta.get("path"),
                "minio_object": image_meta.get("minio_object"),
                "minio_bucket": image_meta.get("minio_bucket"),
            }

        doc = Document(
            filename=filename,
            content=text,
            metadata=metadata,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        doc_id = await self.document_repo.create_document(doc)
        if not doc_id:
            return {"ok": False, "error": "Не удалось сохранить документ в БД", "document_id": None}

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            await self.document_repo.delete_document(doc_id)
            return {"ok": False, "error": f"Ошибка эмбеддингов: {e}", "document_id": None}

        if len(embeddings) != len(chunks):
            await self.document_repo.delete_document(doc_id)
            return {"ok": False, "error": "Число эмбеддингов не совпадает с числом чанков", "document_id": None}

        vectors = [
            DocumentVector(
                document_id=doc_id,
                chunk_index=i,
                embedding=emb,
                content=chunks_with_meta[i][0],
                metadata=dict(chunks_with_meta[i][1]),
            )
            for i, emb in enumerate(embeddings)
        ]
        created = await self.vector_repo.create_vectors_batch(vectors)
        if self.graph_repo and self.graph_enabled:
            try:
                await self.graph_repo.rebuild_document_graph(
                    store_type="global",
                    document_id=doc_id,
                    chunks=[(v.chunk_index, v.content) for v in vectors],
                )
            except Exception as e:
                logger.warning("Graph индекс не собран для документа %s: %s", doc_id, e)

        # После добавления документа помечаем BM25 индекс на пересборку
        if self.use_hybrid_search:
            self._bm25_needs_rebuild = True

        return {
            "ok": True,
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": created,
        }

    async def search(
        self,
        query: str,
        k: int = 10,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
        vector_query: Optional[str] = None,
        filters: Optional[DocumentVectorSearchFilters] = None,
        eval_gold_document_ids: Optional[List[int]] = None,
        eval_gold_chunks: Optional[List[Tuple[int, int]]] = None,
        eval_llm_judge: bool = False,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """
        Поиск: эмбеддинг запроса → векторный поиск → опционально гибрид с BM25 → опционально rerank.

        strategy:
        - "auto" (по умолчанию) - умный выбор пайплайна среди hierarchical / graph / hybrid / standard
          по доступности (BM25, граф, OptimizedDocumentIndex) и эвристикам запроса; RAG_AUTO_MODE=heuristic|priority.
          Реранк для auto остаётся с семантикой режима auto (как в effective_use_reranking).
        - "reranking" - векторный/гибридный/иерархический поиск + rerank.
        - "hierarchical" - умный поиск по иерархии (OptimizedDocumentIndex).
        - "hybrid" - гибрид (BM25 + векторный); cross-encoder rerank — если RAG_USE_RERANKING=true в SVC-RAG.
        - "standard" - векторный поиск с постобработкой качества (без BM25/rerank).
        - "raw_cosine" - сырой векторный поиск (pgvector cosine) без постобработки.
        - "graph" - seed retrieval + расширение по графу связей чанков.
        Также поддерживается "flat" как синоним "standard".

        Возвращает список (content, score, document_id, chunk_index), где score - комбинированный
        скор (для reranking: 0.7 * rerank_score + 0.3 * original_score, как в backend).
        """
        q_text = (query or "").strip()
        vq_text = (vector_query or "").strip()
        if not q_text and not vq_text:
            return []
        embed_source = vq_text or q_text
        t_search_start = time.perf_counter()

        user_strategy = (strategy or "auto").lower()
        if user_strategy == "flat":
            user_strategy = "standard"

        original_strategy = user_strategy
        rerank_key = user_strategy
        if user_strategy == "auto":
            hybrid_ok = bool(self.use_hybrid_search and self.bm25_index is not None)
            graph_ok = bool(self.graph_repo and self.graph_enabled)
            hier_ok = self._optimized_index is not None
            picked = resolve_auto_pipeline_strategy(
                q_text,
                store="global",
                document_id=document_id,
                hierarchical_available=hier_ok,
                graph_available=graph_ok,
                hybrid_available=hybrid_ok,
            )
            user_strategy = picked
            rerank_key = "auto"
            logger.info(
                "[SVC-RAG] global strategy=auto → %s (hybrid_ready=%s graph=%s hierarchical=%s)",
                picked,
                hybrid_ok,
                graph_ok,
                hier_ok,
            )

        # Явный иерархический поиск - отдельная ветка
        if user_strategy == "hierarchical" and self._optimized_index is None:
            logger.info(
                "[SVC-RAG] search store=global strategy=hierarchical недоступен (optimized_index выключен/не создан) → обычный pgvector/BM25/rerank путь"
            )
        if user_strategy == "hierarchical" and self._optimized_index is not None:
            try:
                hits_h = await self._optimized_index.smart_search_async(q_text, k=k, search_strategy="auto")
                final_h = await self._finalize_hit_rows(list(hits_h), used_rerank=False)
                await log_retrieval_with_eval(
                    store="global (глобальные документы)",
                    strategy_resolved="hierarchical",
                    pipeline="OptimizedDocumentIndex.smart_search_async",
                    extra_lines=[f"k={k}", f"document_id={document_id}"],
                    final_hits=final_h,
                    k_requested=k,
                    query_for_eval=q_text,
                    search_started_perf=t_search_start,
                    gold_document_ids=eval_gold_document_ids,
                    gold_chunks=eval_gold_chunks,
                    llm_judge=eval_llm_judge,
                )
                return final_h
            except Exception as e:
                logger.warning("Иерархический поиск не удался, fallback на плоский: %s", e)
                user_strategy = "hybrid" if (self.use_hybrid_search and self.bm25_index) else "standard"
                logger.info("[SVC-RAG] после сбоя hierarchical используем pipeline=%s", user_strategy)

        if user_strategy == "graph":
            return await self._graph_search(
                q_text,
                k=k,
                document_id=document_id,
                use_reranking=use_reranking,
                vector_query=vq_text or None,
                filters=filters,
                search_started_perf=t_search_start,
                eval_gold_document_ids=eval_gold_document_ids,
                eval_gold_chunks=eval_gold_chunks,
                eval_llm_judge=eval_llm_judge,
            )

        cfg_rerank_enabled = self._cfg.use_reranking
        use_rerank = effective_use_reranking(
            use_reranking, cfg_rerank_enabled, rerank_key, query_text=q_text
        )

        # Как в KB/project/memory: широкий пул из pgvector + диверсификация по document_id.
        # Иначе при rerank_top_k=20 весь пул забивают чанки 1–2 больших DOCX, а PDF (напр. CV) не попадает в реранк.
        # Для перечислительных запросов расширяем k×3, чтобы успеть собрать
        # кандидатов от всех документов, где есть entity.
        _fetch_k_seed = k * 3 if _is_enumeration_query(q_text) else k
        fetch_lim = vector_fetch_limit(
            _fetch_k_seed,
            graph=False,
            document_id=document_id,
            use_rerank=use_rerank,
            rerank_top_k=int(self._cfg.rerank_top_k or 20),
        )

        try:
            query_embedding = await self.rag_client.embed_single(embed_source)
        except Exception as e:
            logger.warning("Embed query failed: %s", e)
            await log_retrieval_with_eval(
                store="global (глобальные документы)",
                strategy_resolved=user_strategy,
                pipeline="(ошибка эмбеддинга запроса)",
                extra_lines=[f"k={k}"],
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=t_search_start,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        pairs = await self.vector_repo.similarity_search(
            query_embedding,
            limit=fetch_lim,
            document_id=document_id,
            filters=filters,
        )
        if not pairs:
            await log_retrieval_with_eval(
                store="global (глобальные документы)",
                strategy_resolved=user_strategy,
                pipeline="pgvector_cosine → нет кандидатов",
                extra_lines=[f"k={k}", f"лимит_pgvector={fetch_lim}", f"document_id={document_id}"],
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=t_search_start,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        raw_mode = user_strategy == "raw_cosine"
        if raw_mode:
            out_raw = [(v.content, score, v.document_id, v.chunk_index) for v, score in pairs[:k]]
            await log_retrieval_with_eval(
                store="global (глобальные документы)",
                strategy_resolved="raw_cosine",
                pipeline="pgvector_cosine_similarity (raw, no_postprocess)",
                extra_lines=[f"k={k}", f"лимит_pgvector={fetch_lim}", f"document_id={document_id}"],
                final_hits=out_raw,
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=t_search_start,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return out_raw

        # --- Keyword FTS (OR) + Entity lane ---
        # Те же принципы, что и в retrieval_pipeline.py для нон-global хранилищ:
        #  1. OR-семантика FTS уже внутри VectorRepository.keyword_search (fts.py).
        #  2. Entity lane — targeted FTS только по собственным именам/кодам,
        #     найденные чанки переживают фильтры (pinned).
        #  3. Enumeration-запросы получают более высокий keyword_weight и не диверсифицируются.
        # Filename anchor: запросы вида «саммари по X.docx» семантически не
        # совпадают с содержанием файла — резолвим имя в document_id и принудительно
        # поднимаем весь документ (см. _fetch_all_chunks ниже).
        filename_mentions: List[str] = extract_filenames(q_text) if q_text else []
        filename_doc_ids: List[int] = []
        if filename_mentions and hasattr(self.doc_repo, "find_document_ids_by_filename"):
            for fn in filename_mentions:
                try:
                    ids = await self.doc_repo.find_document_ids_by_filename(fn)
                except Exception as e:
                    logger.warning("[global] find_docs_by_filename(%r) failed: %s", fn, e)
                    continue
                if ids:
                    filename_doc_ids.extend(ids)
                else:
                    stem = fn.rsplit(".", 1)[0]
                    if stem and stem != fn:
                        try:
                            ids2 = await self.doc_repo.find_document_ids_by_filename(stem)
                            if ids2:
                                filename_doc_ids.extend(ids2)
                        except Exception:
                            pass
            seen_fid: set = set()
            filename_doc_ids = [d for d in filename_doc_ids if not (d in seen_fid or seen_fid.add(d))]
            if filename_doc_ids:
                logger.info(
                    "[global] filename_anchor: %s → document_ids=%s",
                    filename_mentions, filename_doc_ids,
                )

        # Имена файлов в запросе → включаем режим enumeration (широкий пул, без диверсификации).
        enumeration = _is_enumeration_query(q_text) or bool(filename_doc_ids)
        entity_tokens: List[str] = extract_proper_nouns(q_text) if q_text else []

        keyword_hits: List[Tuple[DocumentVector, float]] = []
        if q_text:
            try:
                keyword_hits = await self.vector_repo.keyword_search(
                    q_text,
                    limit=max(k * 6, 48),
                    document_id=document_id,
                    filters=filters,
                )
            except Exception as e:
                # Warning, чтобы тихие провалы keyword-поиска были видны в логах.
                logger.warning("keyword_search(global) failed: %s", e)

        entity_hits: List[Tuple[DocumentVector, float]] = []
        entity_keys: set = set()
        if entity_tokens and q_text:
            # (1) FTS по именам.
            try:
                fts_hits = await self.vector_repo.keyword_search(
                    " ".join(entity_tokens),
                    limit=max(k * 8, 64),
                    document_id=document_id,
                    filters=filters,
                )
                entity_hits.extend(fts_hits)
            except Exception as e:
                logger.warning("entity_lane(global) FTS failed: %s", e)

            # (2) ILIKE со stemmer'ом — ВСЕГДА, не только при FTS=0. Лечит
            # падежи: «Константина» → %Константи%, найдёт «Константин Олегович».
            stemmed_tokens = [crude_russian_stem(t) for t in entity_tokens]
            lookup_tokens = list(dict.fromkeys([t for t in stemmed_tokens if t]))
            if lookup_tokens:
                try:
                    ilike_hits = await self.vector_repo.substring_search(
                        lookup_tokens, limit=max(k * 8, 64), document_id=document_id
                    )
                    existing = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}
                    for dv, sc in ilike_hits:
                        if (dv.document_id, dv.chunk_index) not in existing:
                            entity_hits.append((dv, sc))
                            existing.add((dv.document_id, dv.chunk_index))
                    if ilike_hits:
                        logger.info(
                            "[global] entity_lane ILIKE-stemmed: %s → %s → %d чанков",
                            entity_tokens, lookup_tokens, len(ilike_hits),
                        )
                except Exception as e:
                    logger.warning("entity_ilike_stemmed(global) failed: %s", e)

            # (3) Entity-in-filename: имена героев часто зашиты в имя файла
            # («..._Некрасов_СК0050629.pdf»). Если у документа имя совпадает
            # с extracted entity — тянем первые 4 чанка как entity-хиты.
            if (
                hasattr(self.doc_repo, "find_document_ids_by_filename")
                and hasattr(self.vector_repo, "get_vectors_by_document")
            ):
                filename_probe = [t for t in stemmed_tokens if len(t) >= 4 and not t.isdigit()]
                matched_docs: set = set()
                for tok in filename_probe:
                    try:
                        ids = await self.doc_repo.find_document_ids_by_filename(tok)
                        if ids:
                            matched_docs.update(ids)
                    except Exception as e:
                        logger.warning("entity_find_docs_by_filename(%r, global) failed: %s", tok, e)
                matched_docs_list = sorted(matched_docs)[:8]
                if matched_docs_list:
                    existing = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}
                    added = 0
                    for doc_id in matched_docs_list:
                        try:
                            chunks = await self.vector_repo.get_vectors_by_document(doc_id)
                        except Exception as e:
                            logger.warning("get_vectors_by_document(%d, global) failed: %s", doc_id, e)
                            continue
                        if not chunks:
                            continue
                        chunks_sorted = sorted(
                            chunks, key=lambda d: int(getattr(d, "chunk_index", 0) or 0)
                        )
                        for dv in chunks_sorted[:4]:
                            key = (dv.document_id, dv.chunk_index)
                            if key in existing:
                                continue
                            entity_hits.append((dv, 0.5))
                            existing.add(key)
                            added += 1
                    if added:
                        logger.info(
                            "[global] entity_lane filename-match: %s → docs %s → +%d chunks",
                            entity_tokens, matched_docs_list, added,
                        )

            entity_keys = {(dv.document_id, dv.chunk_index) for dv, _ in entity_hits}

        if keyword_hits or entity_hits:
            combined_kw = list(keyword_hits) + list(entity_hits)
            kw_weight = 0.65 if (user_strategy == "standard" and not use_rerank) else 0.35
            if enumeration:
                kw_weight = max(kw_weight, 0.7)
            pairs = merge_vector_and_keyword_hits(pairs, combined_kw, keyword_weight=kw_weight)

        # Фильтрация явно нерелевантных чанков до реранка/гибрида.
        # Entity-хиты обходят min_sim / low_signal — без этого именно «Константина»
        # в глобальном хранилище тоже теряется.
        min_sim = float(getattr(self._cfg, "min_vector_similarity", 0.0) or 0.0)
        if entity_keys:
            pinned = [h for h in pairs if (h[0].document_id, h[0].chunk_index) in entity_keys]
            rest = [h for h in pairs if (h[0].document_id, h[0].chunk_index) not in entity_keys]
            rest = filter_by_min_vector_similarity(rest, min_sim, k)
            rest = filter_low_signal_chunks(
                rest,
                min_len=int(getattr(self._cfg, "min_chunk_length", 40)),
                rescue_keep=max(k * 3, 12),
            )
            pairs = pinned + rest
        else:
            pairs = filter_by_min_vector_similarity(pairs, min_sim, k)
            pairs = filter_low_signal_chunks(
                pairs,
                min_len=int(getattr(self._cfg, "min_chunk_length", 40)),
                rescue_keep=max(k * 3, 12),
            )
        pairs = keyword_boost_hits(pairs, q_text)

        use_hybrid = self.use_hybrid_search and not document_id
        if user_strategy == "standard":
            use_hybrid = False
        elif user_strategy == "hybrid":
            use_hybrid = self.use_hybrid_search and not document_id

        hybrid_applied = False
        if use_hybrid and self.bm25_index:
            hybrid_results = await self._hybrid_combine(q_text, pairs, k=fetch_lim)
            pairs = [(v, score) for v, score in hybrid_results]
            hybrid_applied = True

        if (
            document_id is None
            and pairs
            and not enumeration
            and should_diversify_hits(pairs)
        ):
            pool_div = max(int(self._cfg.rerank_top_k or 20), k * 6, 56)
            pairs = diversify_hits_by_document(pairs, min(pool_div, len(pairs)))

        pipeline_desc = "pgvector_cosine_similarity"
        if document_id is not None:
            pipeline_desc += " (doc_scoped)"
        if use_hybrid:
            if hybrid_applied:
                pipeline_desc += " + bm25_hybrid_merge"
            else:
                pipeline_desc += " + bm25_skipped(no_index_yet_or_disabled)"
        if use_rerank:
            pipeline_desc += " + cross_encoder_rerank"
        else:
            pipeline_desc += " (no_rerank)"

        report_extras = [
            f"k={k}",
            f"лимит_векторов_pgvector={fetch_lim}",
            f"гибрид_BM25_в_конфиге={self.use_hybrid_search}",
            (
                f"гибрид_применён={'да' if hybrid_applied else 'нет'}"
                if use_hybrid
                else "гибрид=выключен_для_этой_стратегии"
            ),
            f"реранк_cross_encoder={'да' if use_rerank else 'нет'}",
        ]

        final_limit = k * 2 if enumeration else k

        # Parent-document expansion — см. подробный комментарий в retrieval_pipeline.py.
        # Короткая версия:
        #   * filename-anchor (пользователь назвал файл) — override: 20 чанков документа целиком, пиним.
        #   * entity-anchor (имя встретилось в документе) — мягкий сигнал: 2 соседних
        #     с entity чанка, НЕ пиним весь документ (иначе «magnet»-эффект: CV
        #     сосёт все запросы, где упомянут Константин, даже если вопрос про другой файл).
        #   * enumeration без entity — top-3 документа, по 4 чанка, без пининга всего.
        pin_whole_doc_ids: set = set(filename_doc_ids or [])
        entity_anchor_doc_ids: set = set()
        enum_anchor_doc_ids: set = set()
        sibling_rows_by_key: Dict[Tuple[Any, Any], Tuple[str, float, Optional[int], Optional[int]]] = {}
        if entity_keys:
            for v, _ in pairs:
                if (v.document_id, v.chunk_index) in entity_keys:
                    entity_anchor_doc_ids.add(v.document_id)
        if enumeration and pairs and not entity_anchor_doc_ids:
            seen_doc_best: Dict[Any, float] = {}
            for v, sc in pairs:
                if v.document_id not in seen_doc_best or float(sc) > seen_doc_best[v.document_id]:
                    seen_doc_best[v.document_id] = float(sc)
            for doc_id, _ in sorted(seen_doc_best.items(), key=lambda x: x[1], reverse=True)[:3]:
                enum_anchor_doc_ids.add(doc_id)
        all_anchor_doc_ids: set = pin_whole_doc_ids | entity_anchor_doc_ids | enum_anchor_doc_ids

        if all_anchor_doc_ids:
            existing = {(v.document_id, v.chunk_index) for v, _ in pairs}
            base_sib_score = min((float(sc) for _, sc in pairs), default=0.01) * 0.5
            if base_sib_score <= 0:
                base_sib_score = 0.01
            # Entity-сиблинги ещё ниже, чтобы не выжимать чанки других доков с тем же именем.
            entity_sib_score = base_sib_score * 0.5

            def _cap_global(doc_id: Any) -> int:
                if doc_id in pin_whole_doc_ids:
                    return 20
                if doc_id in entity_anchor_doc_ids:
                    return 2
                if doc_id in enum_anchor_doc_ids:
                    return 4
                return 0

            for doc_id in all_anchor_doc_ids:
                cap = _cap_global(doc_id)
                if cap <= 0:
                    continue
                try:
                    doc_chunks = await self.vector_repo.get_vectors_by_document(doc_id)
                except Exception as e:
                    logger.warning("[global] parent_expansion get_vectors_by_document(%s): %s", doc_id, e)
                    continue
                if not doc_chunks:
                    continue
                doc_chunks.sort(key=lambda d: int(getattr(d, "chunk_index", 0) or 0))
                entity_chunk_indices = {
                    v.chunk_index for v in doc_chunks
                    if (v.document_id, v.chunk_index) in entity_keys
                }
                if doc_id in entity_anchor_doc_ids and entity_chunk_indices:
                    def _prox(ci: int, anchors: set = entity_chunk_indices) -> int:
                        return min(abs(ci - a) for a in anchors)
                    doc_chunks.sort(
                        key=lambda d: (
                            _prox(int(getattr(d, "chunk_index", 0) or 0)),
                            int(getattr(d, "chunk_index", 0) or 0),
                        )
                    )
                taken = 0
                sib_score = entity_sib_score if doc_id in entity_anchor_doc_ids else base_sib_score
                for dv in doc_chunks:
                    if taken >= cap:
                        break
                    key = (dv.document_id, dv.chunk_index)
                    if key in existing:
                        continue
                    if doc_id in entity_anchor_doc_ids and entity_chunk_indices:
                        ci = int(getattr(dv, "chunk_index", 0) or 0)
                        if min(abs(ci - a) for a in entity_chunk_indices) > 2:
                            break
                    sibling_rows_by_key[key] = (dv.content, sib_score, dv.document_id, dv.chunk_index)
                    pairs.append((dv, sib_score))
                    existing.add(key)
                    taken += 1
            if sibling_rows_by_key:
                logger.info(
                    "[global] parent-expansion: +%s sibling-чанков "
                    "(pin_whole=%s, entity_anchor=%s, enum_anchor=%s)",
                    len(sibling_rows_by_key),
                    sorted(list(pin_whole_doc_ids)),
                    sorted(list(entity_anchor_doc_ids)),
                    sorted(list(enum_anchor_doc_ids)),
                )

        def _cut_with_entity_pin(rows: List[Tuple[str, float, Optional[int], Optional[int]]]) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
            """Срезает до ``final_limit`` и пиннит ТОЛЬКО:
              * сами entity-чанки (точечное попадание — без них перечисление сломается);
              * чанки filename-anchor документов (пользователь явно назвал файл).

            Entity-anchor siblings и enum siblings в пининг НЕ попадают — они просто
            лежат в общей куче с пониженным score и пробиваются по общему ранжированию.
            Это лекарство от «magnet»-эффекта: CV не будет цеплять все запросы с
            упоминанием имени, если оно есть и в других документах.
            """
            if not rows:
                return []
            if not entity_keys and not pin_whole_doc_ids:
                return rows[:final_limit]
            anchor_rows: List[Tuple[str, float, Optional[int], Optional[int]]] = []
            seen: set = set()
            for row in rows:
                _, _, doc_id, chunk_idx = row
                key = (doc_id, chunk_idx)
                if key in seen:
                    continue
                is_entity = key in entity_keys
                is_whole_doc_pin = doc_id in pin_whole_doc_ids
                if is_entity or is_whole_doc_pin:
                    anchor_rows.append(row)
                    seen.add(key)
            anchor_rows.sort(key=lambda r: (int(r[2] or 0), int(r[3] or 0)))
            others = [r for r in rows if (r[2], r[3]) not in seen]
            merged = anchor_rows + others
            return merged[: max(final_limit, len(anchor_rows))]

        if use_rerank and len(pairs) > 1:
            passages = [v.content for v, _ in pairs]
            try:
                # top_k=len(pairs) — получаем полный ранжированный список для пост-реранк диверсификации
                reranked = await self.rag_client.rerank(q_text, passages, top_k=len(pairs))
                out = []
                for idx, sc in reranked:
                    if idx < len(pairs):
                        v, orig_score = pairs[idx]
                        rerank_score = float(sc)
                        original_score = float(orig_score)
                        final_score = 0.7 * rerank_score + 0.3 * original_score
                        out.append((v.content, final_score, v.document_id, v.chunk_index))
                logger.info("[SVC-RAG] search store=global rerank=ok hits=%s", len(out))
                final_out = await self._finalize_hit_rows(_cut_with_entity_pin(out), used_rerank=True)
                await log_retrieval_with_eval(
                    store="global (глобальные документы)",
                    strategy_resolved=user_strategy,
                    pipeline=pipeline_desc,
                    extra_lines=report_extras + ["реранк_статус=успех"],
                    final_hits=final_out,
                    k_requested=k,
                    query_for_eval=q_text,
                    search_started_perf=t_search_start,
                    gold_document_ids=eval_gold_document_ids,
                    gold_chunks=eval_gold_chunks,
                    llm_judge=eval_llm_judge,
                )
                return final_out
            except Exception as e:
                logger.warning("Rerank failed, using vector order: %s", e)

        out_pairs_all = [(v.content, score, v.document_id, v.chunk_index) for v, score in pairs]
        out_pairs = _cut_with_entity_pin(out_pairs_all)
        logger.info("[SVC-RAG] search store=global done hits=%s (final order без rerank или после сбоя rerank)", len(out_pairs))
        final_pairs = await self._finalize_hit_rows(out_pairs, used_rerank=False)
        await log_retrieval_with_eval(
            store="global (глобальные документы)",
            strategy_resolved=user_strategy,
            pipeline=pipeline_desc,
            extra_lines=report_extras + ["реранк_статус=нет_или_сбой"],
            final_hits=final_pairs,
            k_requested=k,
            query_for_eval=q_text,
            search_started_perf=t_search_start,
            gold_document_ids=eval_gold_document_ids,
            gold_chunks=eval_gold_chunks,
            llm_judge=eval_llm_judge,
        )
        return final_pairs

    async def _build_bm25_index(self) -> None:
        """Построение BM25 индекса из всех документов """
        if not self.use_hybrid_search:
            return

        try:
            rows = await self.vector_repo.get_all_contents_for_bm25()
            if not rows:
                logger.warning("Нет текстов для построения BM25 индекса")
                self.bm25_index = None
                self.bm25_texts = []
                self.bm25_metadatas = []
                return

            all_texts: List[str] = []
            all_metadatas: List[Dict[str, Any]] = []
            for document_id, chunk_index, content in rows:
                all_texts.append(content)
                all_metadatas.append(
                    {
                        "document_id": document_id,
                        "chunk": chunk_index,
                    }
                )

            tokenized_texts = [_tokenize_ru_en(t) for t in all_texts]
            self.bm25_index = BM25Okapi(tokenized_texts)
            self.bm25_texts = all_texts
            self.bm25_metadatas = all_metadatas
            logger.info("BM25 индекс построен: %s чанков", len(all_texts))
        except Exception as e:
            logger.error("Ошибка построения BM25 индекса: %s", e)
            self.bm25_index = None
            self.bm25_texts = []
            self.bm25_metadatas = []

    async def _bm25_search(self, query: str, k: int) -> List[Tuple[int, int, float]]:
        """BM25 поиск: возвращает список (document_id, chunk_index, score)."""
        if not self.use_hybrid_search:
            return []

        if self._bm25_needs_rebuild or not self.bm25_index:
            logger.info("Пересоздание BM25 индекса перед поиском...")
            await self._build_bm25_index()
            self._bm25_needs_rebuild = False

        if not self.bm25_index or not self.bm25_texts:
            return []

        try:
            q_tokens = _tokenize_ru_en(query)
            scores = self.bm25_index.get_scores(q_tokens)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            results: List[Tuple[int, int, float]] = []
            for idx in top_indices:
                meta = self.bm25_metadatas[idx]
                results.append((meta["document_id"], meta["chunk"], float(scores[idx])))
            return results
        except Exception as e:
            logger.error("Ошибка BM25 поиска: %s", e)
            return []

    async def _hybrid_combine(
        self,
        query: str,
        vector_pairs: List[Tuple[DocumentVector, float]],
        k: int,
    ) -> List[Tuple[DocumentVector, float]]:
        """Гибридный поиск: объединяет векторные результаты и BM25 по формуле как в backend."""
        if not self.use_hybrid_search:
            return vector_pairs[:k]

        bm25_results = await self._bm25_search(query, k * 2)

        # Нормализация векторных скоров
        if vector_pairs:
            max_vector_score = max(score for _, score in vector_pairs) or 1.0
        else:
            max_vector_score = 1.0

        # Нормализация BM25 скоров
        if bm25_results:
            max_bm25_score = max(score for _, _, score in bm25_results) or 1.0
        else:
            max_bm25_score = 1.0

        combined: Dict[Tuple[int, int], Dict[str, Any]] = {}

        # Добавляем векторные результаты
        for v, vec_score in vector_pairs:
            key = (v.document_id, v.chunk_index)
            normalized_vec = vec_score / max_vector_score if max_vector_score > 0 else 0.0
            combined[key] = {
                "vector": v,
                "vector_score": vec_score,
                "bm25_score": 0.0,
                "final_score": normalized_vec * (1.0 - self.hybrid_bm25_weight),
            }

        # Добавляем/обновляем BM25 результаты
        for doc_id, chunk_index, bm25_score in bm25_results:
            key = (doc_id, chunk_index)
            normalized_bm25 = bm25_score / max_bm25_score if max_bm25_score > 0 else 0.0
            if key in combined:
                combined[key]["bm25_score"] = bm25_score
                combined[key]["final_score"] += normalized_bm25 * self.hybrid_bm25_weight
            else:
                # Точечный запрос вместо загрузки всех векторов документа
                vec = await self.vector_repo.get_vector_by_document_and_chunk(doc_id, chunk_index)
                if not vec:
                    continue
                combined[key] = {
                    "vector": vec,
                    "vector_score": 0.0,
                    "bm25_score": bm25_score,
                    "final_score": normalized_bm25 * self.hybrid_bm25_weight,
                }

        final = sorted(combined.values(), key=lambda x: x["final_score"], reverse=True)[:k]
        return [(item["vector"], float(item["final_score"])) for item in final]

    async def _graph_search(
        self,
        query: str,
        k: int = 10,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        vector_query: Optional[str] = None,
        filters: Optional[DocumentVectorSearchFilters] = None,
        *,
        search_started_perf: float,
        eval_gold_document_ids: Optional[List[int]] = None,
        eval_gold_chunks: Optional[List[Tuple[int, int]]] = None,
        eval_llm_judge: bool = False,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Graph RAG: seed retrieval -> expansion по графу -> optional rerank."""
        q_text = (query or "").strip()
        embed_source = (vector_query or "").strip() or q_text
        pipeline_base = "pgvector_cosine_seeds → graph_expand_neighbors → (опционально) cross_encoder_rerank"
        graph_extras = [
            f"k={k}",
            f"document_id={document_id}",
            f"seed_limit={max(k * 4, 36)}",
        ]
        try:
            query_embedding = await self.rag_client.embed_single(embed_source)
        except Exception as e:
            logger.warning("Embed query failed for graph search: %s", e)
            await log_retrieval_with_eval(
                store="global (глобальные документы)",
                strategy_resolved="graph",
                pipeline=f"{pipeline_base} (ошибка эмбеддинга запроса)",
                extra_lines=graph_extras,
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=search_started_perf,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        seed_limit = max(k * 4, 36)
        pairs = await self.vector_repo.similarity_search(
            query_embedding,
            limit=seed_limit,
            document_id=document_id,
            filters=filters,
        )
        if not pairs:
            await log_retrieval_with_eval(
                store="global (глобальные документы)",
                strategy_resolved="graph",
                pipeline=f"{pipeline_base} → нет seed-кандидатов",
                extra_lines=graph_extras,
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=search_started_perf,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        seed_pairs = [
            (v.document_id, v.chunk_index)
            for v, _ in pairs[: min(12, len(pairs))]
            if v.document_id is not None
        ]
        seed_chunk_indexes = [p[1] for p in seed_pairs]
        graph_scores: Dict[Tuple[int, int], float] = {}
        if self.graph_repo and self.graph_enabled:
            try:
                graph_scores = await self.graph_repo.expand_neighbors(
                    store_type="global",
                    document_id=document_id,
                    seed_chunk_indexes=seed_chunk_indexes,
                    max_hops=2,
                    max_nodes=max(k * 4, 40),
                    seed_doc_chunk_pairs=seed_pairs if document_id is None else None,
                )
            except Exception as e:
                logger.warning("Graph expand failed, fallback to seeds: %s", e)

        scored: List[Tuple[DocumentVector, float]] = []
        for vec, base_score in pairs:
            gscore = graph_scores.get((vec.document_id, vec.chunk_index), 0.0)
            final = 0.7 * float(base_score) + 0.3 * float(gscore)
            scored.append((vec, final))
        scored.sort(key=lambda x: x[1], reverse=True)

        if (use_reranking if use_reranking is not None else self._cfg.use_reranking) and len(scored) > 1:
            n_take = min(len(scored), max(k * 2, 12))
            subset = scored[:n_take]
            passages = [v.content for v, _ in subset]
            try:
                reranked = await self.rag_client.rerank(q_text, passages, top_k=k)
                out: List[Tuple[str, float, Optional[int], Optional[int]]] = []
                for idx, sc in reranked:
                    if idx < len(subset):
                        v, graph_mix_score = subset[idx]
                        final_score = 0.7 * float(sc) + 0.3 * float(graph_mix_score)
                        out.append((v.content, final_score, v.document_id, v.chunk_index))
                if out:
                    logger.info(
                        "[SVC-RAG] search store=global strategy=graph done hits=%s rerank=ok seeds=%s graph_nodes=%s",
                        len(out[:k]),
                        len(seed_chunk_indexes),
                        len(graph_scores),
                    )
                    final_g = await self._finalize_hit_rows(out[:k], used_rerank=True)
                    await log_retrieval_with_eval(
                        store="global (глобальные документы)",
                        strategy_resolved="graph",
                        pipeline=pipeline_base,
                        extra_lines=graph_extras
                        + [
                            f"seeds={len(seed_chunk_indexes)} graph_nodes={len(graph_scores)}",
                            "реранк_статус=успех",
                        ],
                        final_hits=final_g,
                        k_requested=k,
                        query_for_eval=q_text,
                        search_started_perf=search_started_perf,
                        gold_document_ids=eval_gold_document_ids,
                        gold_chunks=eval_gold_chunks,
                        llm_judge=eval_llm_judge,
                    )
                    return final_g
            except Exception as e:
                logger.warning("Graph rerank failed: %s", e)

        out_final = [(v.content, score, v.document_id, v.chunk_index) for v, score in scored[:k]]
        logger.info(
            "[SVC-RAG] search store=global strategy=graph done hits=%s rerank=no seeds=%s graph_nodes=%s",
            len(out_final),
            len(seed_chunk_indexes),
            len(graph_scores),
        )
        final_nf = await self._finalize_hit_rows(out_final, used_rerank=False)
        await log_retrieval_with_eval(
            store="global (глобальные документы)",
            strategy_resolved="graph",
            pipeline=pipeline_base,
            extra_lines=graph_extras
            + [
                f"seeds={len(seed_chunk_indexes)} graph_nodes={len(graph_scores)}",
                "реранк_статус=нет_или_сбой",
            ],
            final_hits=final_nf,
            k_requested=k,
            query_for_eval=q_text,
            search_started_perf=search_started_perf,
            gold_document_ids=eval_gold_document_ids,
            gold_chunks=eval_gold_chunks,
            llm_judge=eval_llm_judge,
        )
        return final_nf

    async def delete_document(self, document_id: int) -> bool:
        if self.graph_repo and self.graph_enabled:
            try:
                await self.graph_repo.delete_document_graph("global", document_id)
            except Exception:
                pass
        await self.vector_repo.delete_vectors_by_document(document_id)
        await self.document_repo.delete_document(document_id)
        if self.use_hybrid_search:
            self._bm25_needs_rebuild = True
        return True

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = await self.document_repo.get_all_documents()
        return [
            {"id": d.id, "filename": d.filename, "created_at": d.created_at.isoformat() if d.created_at else None}
            for d in docs
        ]

    async def delete_document_by_filename(self, filename: str) -> bool:
        """Удаление документа по имени файла (аналог remove_document в backend, но без MinIO)."""
        doc = await self.document_repo.get_document_by_filename(filename)
        if not doc or doc.id is None:
            return False
        await self.delete_document(doc.id)
        return True

    async def get_document_chunks(
        self,
        document_id: int,
        start: int = 0,
        limit: int = 3,
    ) -> List[Tuple[str, int, int]]:
        """
        Получить чанки документа по порядку (например, начало документа с оглавлением).
        Возвращает список (content, document_id, chunk_index).
        """
        vectors = await self.vector_repo.get_vectors_by_document(document_id)
        if not vectors:
            return []
        # Сначала чанки с неотрицательным индексом (начало документа), затем специальные (-2, -1)
        vectors = sorted(vectors, key=lambda v: (1 if v.chunk_index < 0 else 0, v.chunk_index))
        selected = vectors[start : start + limit]
        return [(v.content, v.document_id, v.chunk_index) for v in selected]

    async def get_image_minio_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """Вернуть информацию о MinIO/пути для изображения по имени файла."""
        doc = await self.document_repo.get_document_by_filename(filename)
        if not doc:
            return None
        meta = doc.metadata or {}
        image_info = meta.get("image_info") or {}
        if not isinstance(image_info, dict):
            return None
        return {
            "minio_object": image_info.get("minio_object"),
            "minio_bucket": image_info.get("minio_bucket"),
            "path": image_info.get("path"),
        }

    async def get_confidence_report(self) -> Dict[str, Any]:
        """Агрегированный отчёт об уверенности (аналог get_confidence_report_data в backend)."""
        docs = await self.document_repo.get_all_documents()
        confidence_map: Dict[str, Dict[str, Any]] = {}
        for d in docs:
            meta = d.metadata or {}
            cd = meta.get("confidence_data")
            if cd:
                confidence_map[d.filename] = cd

        if not confidence_map:
            return {
                "total_documents": 0,
                "documents": [],
                "average_confidence": 0.0,
                "overall_confidence": 0.0,
                "total_words": 0,
                "formatted_texts": [],
            }

        documents_info: List[Dict[str, Any]] = []
        formatted_texts: List[Dict[str, Any]] = []
        total_confidence = 0.0
        total_weighted_confidence = 0.0
        total_words = 0

        for filename, info in confidence_map.items():
            words = info.get("words", []) or []

            # Форматируем текст с процентами над словами
            formatted_lines: List[str] = []
            current_line: List[str] = []

            for word_info in words:
                word = word_info.get("word", "")
                conf = float(word_info.get("confidence", 0.0))
                if not word:
                    continue
                formatted_word = f"{conf:.0f}%\n{word}"
                current_line.append(formatted_word)
                if len(current_line) >= 10:
                    formatted_lines.append("  ".join(current_line))
                    current_line = []

            if current_line:
                formatted_lines.append("  ".join(current_line))

            formatted_text = "\n".join(formatted_lines)

            # Средняя уверенность по документу
            doc_avg_confidence = float(info.get("confidence", 0.0))
            if words:
                doc_avg_confidence = (
                    sum(float(w.get("confidence", 0.0)) for w in words) / len(words)
                )

            documents_info.append(
                {
                    "filename": filename,
                    "confidence": doc_avg_confidence,
                    "text_length": int(info.get("text_length", 0)),
                    "file_type": info.get("file_type", "unknown"),
                    "words_count": len(words),
                }
            )

            formatted_texts.append(
                {
                    "filename": filename,
                    "formatted_text": formatted_text,
                    "words": words,
                }
            )

            total_confidence += doc_avg_confidence
            if words:
                total_weighted_confidence += sum(
                    float(w.get("confidence", 0.0)) for w in words
                )
                total_words += len(words)

        avg_confidence = total_confidence / len(documents_info) if documents_info else 0.0
        overall_confidence = (
            total_weighted_confidence / total_words if total_words > 0 else avg_confidence
        )

        return {
            "total_documents": len(documents_info),
            "documents": documents_info,
            "average_confidence": avg_confidence,
            "overall_confidence": overall_confidence,
            "total_words": total_words,
            "formatted_texts": formatted_texts,
        }
