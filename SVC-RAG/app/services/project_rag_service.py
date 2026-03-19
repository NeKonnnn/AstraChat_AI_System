# RAG-сервис для файлов проектов: project_rag_documents + project_rag_vectors
# Каждый документ привязан к project_id; при удалении проекта всё чистится через delete_by_project.
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.clients.rag_models_client import RagModelsClient
from app.database.project_rag_repository import (
    ProjectRagDocumentRepository,
    ProjectRagVectorRepository,
)
from app.database.models import Document, DocumentVector
from app.services.chunker import split_into_chunks
from app.services.document_parser import parse_document

logger = logging.getLogger(__name__)


class ProjectRagService:
    def __init__(
        self,
        doc_repo: ProjectRagDocumentRepository,
        vector_repo: ProjectRagVectorRepository,
        rag_models_client: RagModelsClient,
    ):
        self.doc_repo = doc_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client

    async def index_document(
        self,
        file_data: bytes,
        filename: str,
        project_id: str,
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
            "source": "project",
            "project_id": project_id,
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
        doc_id = await self.doc_repo.create_document(project_id, doc)
        if doc_id is None:
            return {"ok": False, "error": "Ошибка сохранения документа в БД", "document_id": None}

        chunks = split_into_chunks(text)
        if not chunks:
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": "Не удалось нарезать чанки", "document_id": None}

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            logger.error("Ошибка эмбеддингов project_rag: %s", e)
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": f"Ошибка эмбеддингов: {e}", "document_id": None}

        vectors = [
            DocumentVector(
                document_id=doc_id,
                chunk_index=idx,
                embedding=embedding,
                content=chunk,
                metadata={"chunk_index": idx, "document_filename": filename},
            )
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        created = await self.vector_repo.create_vectors_batch(vectors)
        logger.info(
            "project_rag: проиндексирован '%s' (project=%s, id=%s), %s чанков",
            filename, project_id, doc_id, created,
        )
        return {
            "ok": True,
            "document_id": doc_id,
            "filename": filename,
            "chunks_count": created,
            "project_id": project_id,
        }

    async def search(
        self,
        query: str,
        project_id: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        try:
            query_emb = await self.rag_client.embed([query])
        except Exception as e:
            logger.error("Ошибка эмбеддинга запроса project_rag: %s", e)
            return []
        if not query_emb:
            return []

        hits = await self.vector_repo.similarity_search(
            query_embedding=query_emb[0],
            limit=k,
            project_id=project_id,
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
                logger.warning("Реранкинг project_rag не удался: %s", e)

        return [
            (dv.content, score, dv.document_id, dv.chunk_index)
            for dv, score in hits
        ]

    async def list_documents(self, project_id: str) -> List[Dict[str, Any]]:
        docs = await self.doc_repo.get_documents_by_project(project_id)
        return [
            {
                "id": d["id"],
                "filename": d["filename"],
                "metadata": d["metadata"],
                "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
                "size": (d["metadata"] or {}).get("size", 0),
                "file_type": (d["metadata"] or {}).get("file_type", ""),
                "project_id": d["project_id"],
            }
            for d in docs
        ]

    async def delete_document(self, document_id: int) -> Dict[str, Any]:
        """Удаляет документ; возвращает minio-ключи для очистки бэкендом."""
        doc = await self.doc_repo.get_document(document_id)
        if not doc:
            return {"ok": False, "error": "not_found"}
        meta = doc["metadata"] or {}
        await self.vector_repo.delete_vectors_by_document(document_id)
        await self.doc_repo.delete_document(document_id)
        logger.info("project_rag: удалён документ id=%s", document_id)
        return {
            "ok": True,
            "document_id": document_id,
            "minio_object": meta.get("minio_object"),
            "minio_bucket": meta.get("minio_bucket"),
        }

    async def delete_by_project(self, project_id: str) -> Dict[str, Any]:
        """
        Удаляет все документы и векторы проекта.
        Перед вызовом нужно получить список minio-ключей, чтобы удалить файлы из MinIO.
        """
        docs = await self.doc_repo.get_documents_by_project(project_id)
        minio_keys = [
            {
                "minio_object": (d["metadata"] or {}).get("minio_object"),
                "minio_bucket": (d["metadata"] or {}).get("minio_bucket"),
            }
            for d in docs
            if (d["metadata"] or {}).get("minio_object")
        ]
        deleted_count = await self.doc_repo.delete_documents_by_project(project_id)
        logger.info(
            "project_rag: удалено %s документов для project_id=%s",
            deleted_count, project_id,
        )
        return {
            "ok": True,
            "project_id": project_id,
            "deleted_count": deleted_count,
            "minio_keys": minio_keys,
        }
