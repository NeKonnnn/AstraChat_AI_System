# Сервис постоянной Базы Знаний (Knowledge Base)
# Логика аналогична RagService, но работает с таблицами kb_documents/kb_vectors
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.clients.rag_models_client import RagModelsClient
from app.core.config import get_settings
from app.database.search_filters import DocumentVectorSearchFilters
from app.services.hit_postprocess import apply_rerank_min_and_window
from app.services.rag_search_helpers import (
    diversify_hits_by_document,
    effective_use_reranking,
    filter_by_min_vector_similarity,
    keyword_boost_hits,
    resolve_auto_pipeline_strategy,
    vector_fetch_limit,
)
from app.services.retrieval_eval import log_retrieval_with_eval
from app.services.rerank_helpers import rerank_vector_hits
from app.database.kb_repository import KbDocumentRepository, KbVectorRepository
from app.database.models import Document, DocumentVector
from app.database.graph_repository import GraphRepository
from app.services.chunker import split_into_chunks
from app.services.document_parser import parse_document

logger = logging.getLogger(__name__)

MAX_KB_CONTEXT_CHARS = 12000


class KbService:
    def __init__(
        self,
        doc_repo: KbDocumentRepository,
        vector_repo: KbVectorRepository,
        rag_models_client: RagModelsClient,
        graph_repo: Optional[GraphRepository] = None,
    ):
        self.doc_repo = doc_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client
        self.graph_repo = graph_repo

    # ─── Индексация ─────────────────────────────────────────────────────────────

    async def index_document(
        self,
        file_data: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Парсим файл, режем на чанки, получаем эмбеддинги и сохраняем в kb_documents/kb_vectors."""
        parsed = await parse_document(file_data, filename)
        if not parsed:
            return {
                "ok": False,
                "error": "Не удалось извлечь текст или формат не поддерживается",
                "document_id": None,
            }

        text = parsed.get("text", "")
        if not text.strip():
            return {"ok": False, "error": "Документ пустой", "document_id": None}

        doc = Document(
            filename=filename,
            content=text,
            metadata={
                "file_type": parsed.get("file_type", ""),
                "pages": parsed.get("pages", 0),
                "size": len(file_data),
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        doc_id = await self.doc_repo.create_document(doc)
        if doc_id is None:
            return {"ok": False, "error": "Ошибка сохранения документа в БД", "document_id": None}

        chunks = split_into_chunks(text)
        if not chunks:
            return {"ok": False, "error": "Не удалось нарезать чанки", "document_id": doc_id}

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            logger.error("Ошибка получения эмбеддингов для KB: %s", e)
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": f"Ошибка эмбеддингов: {e}", "document_id": None}

        vectors = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors.append(
                DocumentVector(
                    document_id=doc_id,
                    chunk_index=idx,
                    embedding=embedding,
                    content=chunk,
                    metadata={"start": idx},
                )
            )

        created = await self.vector_repo.create_vectors_batch(vectors)
        if self.graph_repo:
            try:
                await self.graph_repo.rebuild_document_graph(
                    store_type="kb",
                    document_id=doc_id,
                    chunks=[(v.chunk_index, v.content) for v in vectors],
                )
            except Exception as e:
                logger.warning("KB graph индекс не собран для документа %s: %s", doc_id, e)
        logger.info(
            "KB: проиндексирован документ '%s' (id=%s), %s чанков", filename, doc_id, created
        )
        return {
            "ok": True,
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": created,
        }

    # ─── Поиск ──────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
        vector_query: Optional[str] = None,
        filters: Optional[DocumentVectorSearchFilters] = None,
        eval_gold_document_ids: Optional[List[int]] = None,
        eval_gold_chunks: Optional[List[Tuple[int, int]]] = None,
        eval_llm_judge: bool = False,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Векторный поиск по базе знаний.

        Возвращает список (content, score, document_id, chunk_index).
        """
        cfg = get_settings().rag
        q_text = (query or "").strip()
        vq = (vector_query or "").strip()
        if not q_text and not vq:
            return []
        emb_src = vq or q_text
        t0 = time.perf_counter()
        user_strategy = (strategy or "auto").lower()
        original_strategy = user_strategy
        if user_strategy == "auto":
            graph_ok = bool(self.graph_repo) and bool(getattr(cfg, "enable_graph_rag", True))
            user_strategy = resolve_auto_pipeline_strategy(
                q_text,
                store="kb",
                document_id=document_id,
                hierarchical_available=False,
                graph_available=graph_ok,
                hybrid_available=bool(cfg.use_reranking),
            )
            logger.info("[SVC-RAG] KB strategy=auto → %s", user_strategy)
        rerank_key = "auto" if original_strategy == "auto" else user_strategy
        eff_rr = effective_use_reranking(use_reranking, cfg.use_reranking, rerank_key)
        fetch_lim = vector_fetch_limit(
            k,
            graph=(user_strategy == "graph"),
            document_id=document_id,
            use_rerank=eff_rr,
            rerank_top_k=int(cfg.rerank_top_k or 20),
        )
        pipeline = ["embed_query", f"pgvector_cosine(limit={fetch_lim})"]
        if user_strategy == "graph":
            pipeline.append("graph_expand_neighbors")
        if eff_rr:
            pipeline.append("cross_encoder_rerank")
        if document_id is None:
            pipeline.append("diversify_by_document")
        pipeline_str = " -> ".join(pipeline)
        report_extras = [
            f"k={k}",
            f"document_id={'все' if document_id is None else document_id}",
            f"кандидатов_из_pgvector={fetch_lim}",
            f"реранк_cross_encoder={'да' if eff_rr else 'нет'}",
        ]
        try:
            query_emb = await self.rag_client.embed([emb_src])
        except Exception as e:
            logger.error("Ошибка эмбеддинга запроса KB: %s", e)
            await log_retrieval_with_eval(
                store="kb (база знаний)",
                strategy_resolved=user_strategy,
                pipeline=f"{pipeline_str} (ошибка embed)",
                extra_lines=report_extras,
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=t0,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        if not query_emb:
            await log_retrieval_with_eval(
                store="kb (база знаний)",
                strategy_resolved=user_strategy,
                pipeline=f"{pipeline_str} (пустой embed)",
                extra_lines=report_extras,
                final_hits=[],
                k_requested=k,
                query_for_eval=q_text,
                search_started_perf=t0,
                gold_document_ids=eval_gold_document_ids,
                gold_chunks=eval_gold_chunks,
                llm_judge=eval_llm_judge,
            )
            return []

        hits = await self.vector_repo.similarity_search(
            query_embedding=query_emb[0],
            limit=fetch_lim,
            document_id=document_id,
            filters=filters,
        )

        # Фильтрация нерелевантных чанков по косинусному порогу
        min_sim = float(getattr(cfg, "min_vector_similarity", 0.0) or 0.0)
        hits = filter_by_min_vector_similarity(hits, min_sim, k)

        # Keyword-boost: повышаем скор чанков с точными словами запроса
        hits = keyword_boost_hits(hits, q_text)

        if document_id is None and hits and user_strategy != "graph":
            pool = max(int(cfg.rerank_top_k or 20), k * 6, 56)
            hits = diversify_hits_by_document(hits, min(pool, len(hits)))

        if user_strategy == "graph" and hits:
            seed_pairs = [
                (dv.document_id, dv.chunk_index)
                for dv, _ in hits[: min(12, len(hits))]
                if dv.document_id is not None
            ]
            seed_chunk_indexes = [p[1] for p in seed_pairs]
            graph_scores: Dict[Tuple[int, int], float] = {}
            if self.graph_repo:
                try:
                    graph_scores = await self.graph_repo.expand_neighbors(
                        store_type="kb",
                        document_id=document_id,
                        seed_chunk_indexes=seed_chunk_indexes,
                        max_hops=2,
                        max_nodes=max(k * 4, 40),
                        seed_doc_chunk_pairs=seed_pairs if document_id is None else None,
                    )
                except Exception as e:
                    logger.warning("KB graph expand failed: %s", e)
            boosted = []
            for dv, base_score in hits:
                gscore = graph_scores.get((dv.document_id, dv.chunk_index), 0.0)
                boosted.append((dv, 0.7 * float(base_score) + 0.3 * float(gscore)))
            boosted.sort(key=lambda x: x[1], reverse=True)
            hits = boosted

        used_rr = False
        if eff_rr and hits:
            try:
                hits = await rerank_vector_hits(
                    q_text,
                    hits,
                    self.rag_client,
                    top_k=max(len(hits), k * 4, int(cfg.rerank_top_k or 20)),
                    vector_weight=0.3,
                )
                used_rr = True
            except Exception as e:
                logger.warning("Реранкинг KB не удался, используем исходные результаты: %s", e)

        rows = [(dv.content, float(score), dv.document_id, dv.chunk_index) for dv, score in hits[:k]]
        final = await apply_rerank_min_and_window(
            self.vector_repo,
            rows,
            rerank_min_score=float(cfg.rerank_min_score or 0),
            sentence_window=int(cfg.sentence_window or 0),
            used_rerank=used_rr,
        )
        await log_retrieval_with_eval(
            store="kb (база знаний)",
            strategy_resolved=user_strategy,
            pipeline=pipeline_str,
            extra_lines=report_extras + [f"реранк_применён={'да' if used_rr else 'нет'}"],
            final_hits=final,
            k_requested=k,
            query_for_eval=q_text,
            search_started_perf=t0,
            gold_document_ids=eval_gold_document_ids,
            gold_chunks=eval_gold_chunks,
            llm_judge=eval_llm_judge,
        )
        return final

    # ─── Управление документами ─────────────────────────────────────────────────

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = await self.doc_repo.get_all_documents()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "metadata": d.metadata,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "size": d.metadata.get("size", 0),
                "file_type": d.metadata.get("file_type", ""),
            }
            for d in docs
        ]

    async def delete_document(self, document_id: int) -> bool:
        doc = await self.doc_repo.get_document(document_id)
        if not doc:
            return False
        if self.graph_repo:
            try:
                await self.graph_repo.delete_document_graph("kb", document_id)
            except Exception:
                pass
        await self.vector_repo.delete_vectors_by_document(document_id)
        await self.doc_repo.delete_document(document_id)
        logger.info("KB: удалён документ id=%s ('%s')", document_id, doc.filename)
        return True

    async def get_document_info(self, document_id: int) -> Optional[Dict[str, Any]]:
        doc = await self.doc_repo.get_document(document_id)
        if not doc:
            return None
        return {
            "id": doc.id,
            "filename": doc.filename,
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
