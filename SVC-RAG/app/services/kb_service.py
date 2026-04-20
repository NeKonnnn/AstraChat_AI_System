# Сервис постоянной Базы Знаний (Knowledge Base)
# Логика аналогична RagService, но работает с таблицами kb_documents/kb_vectors
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from app.clients.rag_models_client import RagModelsClient
from app.core.config import get_settings
from app.database.search_filters import DocumentVectorSearchFilters
from app.database.kb_repository import KbDocumentRepository, KbVectorRepository
from app.database.models import Document, DocumentVector
from app.database.graph_repository import GraphRepository
from app.services.chunker import split_into_chunks_with_meta
from app.services.document_parser import parse_document
from app.services.retrieval_pipeline import RetrievalTrace, run_retrieval_pipeline

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

        chunks_with_meta = split_into_chunks_with_meta(text)
        if not chunks_with_meta:
            return {"ok": False, "error": "Не удалось нарезать чанки", "document_id": doc_id}
        chunks = [c for c, _m in chunks_with_meta]

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            logger.error("Ошибка получения эмбеддингов для KB: %s", e)
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": f"Ошибка эмбеддингов: {e}", "document_id": None}

        vectors = []
        for idx, ((chunk, cmeta), embedding) in enumerate(zip(chunks_with_meta, embeddings)):
            meta = {"start": idx}
            meta.update(cmeta)
            vectors.append(
                DocumentVector(
                    document_id=doc_id,
                    chunk_index=idx,
                    embedding=embedding,
                    content=chunk,
                    metadata=meta,
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
        return_trace: bool = False,
    ) -> Union[
        List[Tuple[str, float, Optional[int], Optional[int]]],
        Tuple[List[Tuple[str, float, Optional[int], Optional[int]]], RetrievalTrace],
    ]:
        """Векторный поиск по базе знаний.

        Возвращает список (content, score, document_id, chunk_index).
        При ``return_trace=True`` — кортеж (hits, RetrievalTrace).
        """
        cfg = get_settings().rag

        async def _vectors(emb, lim):
            return await self.vector_repo.similarity_search(
                query_embedding=emb,
                limit=lim,
                document_id=document_id,
                filters=filters,
            )

        async def _keywords(text, lim):
            return await self.vector_repo.keyword_search(
                text,
                limit=lim,
                document_id=document_id,
                filters=filters,
            )

        async def _substring(tokens, lim):
            return await self.vector_repo.substring_search(
                tokens, limit=lim, document_id=document_id
            )

        async def _fetch_doc(doc_id: int):
            return await self.vector_repo.get_vectors_by_document(doc_id)

        async def _find_docs_by_filename(name: str):
            return await self.doc_repo.find_document_ids_by_filename(name)

        hits, trace = await run_retrieval_pipeline(
            store="kb",
            query=query,
            vector_query=vector_query,
            k=k,
            document_id=document_id,
            use_reranking=use_reranking,
            strategy=strategy,
            filters=filters,
            rag_client=self.rag_client,
            graph_repo=self.graph_repo,
            cfg=cfg,
            search_vectors=_vectors,
            search_keywords=_keywords,
            substring_search=_substring,
            fetch_document_chunks=_fetch_doc,
            find_docs_by_filename=_find_docs_by_filename,
            vector_repo_for_window=self.vector_repo,
            eval_gold_document_ids=eval_gold_document_ids,
            eval_gold_chunks=eval_gold_chunks,
            eval_llm_judge=eval_llm_judge,
            log_store_label="kb (база знаний)",
        )
        return (hits, trace) if return_trace else hits

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
