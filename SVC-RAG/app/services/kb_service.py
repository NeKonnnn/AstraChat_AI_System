# Сервис постоянной Базы Знаний (Knowledge Base)
# Логика аналогична RagService, но работает с таблицами kb_documents/kb_vectors
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.clients.rag_models_client import RagModelsClient
from app.database.kb_repository import KbDocumentRepository, KbVectorRepository
from app.database.models import Document, DocumentVector
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
    ):
        self.doc_repo = doc_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client

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
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Векторный поиск по базе знаний.

        Возвращает список (content, score, document_id, chunk_index).
        """
        try:
            query_emb = await self.rag_client.embed([query])
        except Exception as e:
            logger.error("Ошибка эмбеддинга запроса KB: %s", e)
            return []

        if not query_emb:
            return []

        hits = await self.vector_repo.similarity_search(
            query_embedding=query_emb[0],
            limit=k,
            document_id=document_id,
        )

        if use_reranking and hits:
            try:
                contents = [dv.content for dv, _ in hits]
                rerank_scores = await self.rag_client.rerank(query, contents)
                hits_reranked = []
                for (dv, orig_score), rr_score in zip(hits, rerank_scores):
                    combined = 0.7 * rr_score + 0.3 * orig_score
                    hits_reranked.append((dv, combined))
                hits_reranked.sort(key=lambda x: x[1], reverse=True)
                hits = hits_reranked
            except Exception as e:
                logger.warning("Реранкинг KB не удался, используем исходные результаты: %s", e)

        return [
            (dv.content, score, dv.document_id, dv.chunk_index)
            for dv, score in hits
        ]

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
