# RAG по документам из настроек «библиотека памяти»: MinIO (оригинал) + memory_rag_* в Postgres
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.clients.rag_models_client import RagModelsClient
from app.database.memory_rag_repository import MemoryRagDocumentRepository, MemoryRagVectorRepository
from app.database.models import Document, DocumentVector
from app.services.chunker import split_into_chunks
from app.services.document_parser import parse_document

logger = logging.getLogger(__name__)


class MemoryRagService:
    def __init__(
        self,
        doc_repo: MemoryRagDocumentRepository,
        vector_repo: MemoryRagVectorRepository,
        rag_models_client: RagModelsClient,
    ):
        self.doc_repo = doc_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client

    async def index_document(
        self,
        file_data: bytes,
        filename: str,
        minio_object: Optional[str] = None,
        minio_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
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

        meta: Dict[str, Any] = {
            "file_type": parsed.get("file_type", ""),
            "pages": parsed.get("pages", 0),
            "size": len(file_data),
            "source": "memory_library",
        }
        if minio_object:
            meta["minio_object"] = minio_object
        if minio_bucket:
            meta["minio_bucket"] = minio_bucket

        doc = Document(
            filename=filename,
            content=text,
            metadata=meta,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        doc_id = await self.doc_repo.create_document(doc)
        if doc_id is None:
            return {"ok": False, "error": "Ошибка сохранения документа в БД", "document_id": None}

        chunks = split_into_chunks(text)
        if not chunks:
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": "Не удалось нарезать чанки", "document_id": None}

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            logger.error("Ошибка эмбеддингов memory_rag: %s", e)
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
                    metadata={
                        "chunk_index": idx,
                        "document_filename": filename,
                    },
                )
            )

        created = await self.vector_repo.create_vectors_batch(vectors)
        logger.info(
            "memory_rag: проиндексирован '%s' (id=%s), %s чанков", filename, doc_id, created
        )
        return {
            "ok": True,
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": created,
        }

    async def search(
        self,
        query: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        try:
            query_emb = await self.rag_client.embed([query])
        except Exception as e:
            logger.error("Ошибка эмбеддинга запроса memory_rag: %s", e)
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
                logger.warning("Реранкинг memory_rag не удался: %s", e)

        return [
            (dv.content, score, dv.document_id, dv.chunk_index)
            for dv, score in hits
        ]

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = await self.doc_repo.get_all_documents()
        return [
            {
                "id": d.id,
                "filename": d.filename,
                "metadata": d.metadata,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "size": (d.metadata or {}).get("size", 0),
                "file_type": (d.metadata or {}).get("file_type", ""),
            }
            for d in docs
        ]

    async def delete_document(self, document_id: int) -> Dict[str, Any]:
        """Удаляет из БД; возвращает minio-ключи для очистки в backend."""
        doc = await self.doc_repo.get_document(document_id)
        if not doc:
            return {"ok": False, "error": "not_found"}
        meta = doc.metadata or {}
        await self.vector_repo.delete_vectors_by_document(document_id)
        await self.doc_repo.delete_document(document_id)
        logger.info("memory_rag: удалён документ id=%s", document_id)
        return {
            "ok": True,
            "document_id": document_id,
            "minio_object": meta.get("minio_object"),
            "minio_bucket": meta.get("minio_bucket"),
        }
