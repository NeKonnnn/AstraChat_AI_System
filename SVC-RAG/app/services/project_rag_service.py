# RAG-сервис для файлов проектов: project_rag_documents + project_rag_vectors
# Каждый документ привязан к project_id; при удалении проекта всё чистится через delete_by_project.
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from app.clients.rag_models_client import RagModelsClient
from app.core.config import get_settings
from app.database.search_filters import DocumentVectorSearchFilters
from app.database.project_rag_repository import (
    ProjectRagDocumentRepository,
    ProjectRagVectorRepository,
)
from app.database.models import Document, DocumentVector
from app.database.graph_repository import GraphRepository
from app.services.chunker import split_into_chunks_with_meta
from app.services.document_parser import parse_document
from app.services.retrieval_pipeline import RetrievalTrace, run_retrieval_pipeline

logger = logging.getLogger(__name__)


class ProjectRagService:
    def __init__(
        self,
        doc_repo: ProjectRagDocumentRepository,
        vector_repo: ProjectRagVectorRepository,
        rag_models_client: RagModelsClient,
        graph_repo: Optional[GraphRepository] = None,
    ):
        self.doc_repo = doc_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client
        self.graph_repo = graph_repo

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

        chunks_with_meta = split_into_chunks_with_meta(text)
        if not chunks_with_meta:
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": "Не удалось нарезать чанки", "document_id": None}
        chunks = [c for c, _m in chunks_with_meta]

        try:
            embeddings = await self.rag_client.embed(chunks)
        except Exception as e:
            logger.error("Ошибка эмбеддингов project_rag: %s", e)
            await self.doc_repo.delete_document(doc_id)
            return {"ok": False, "error": f"Ошибка эмбеддингов: {e}", "document_id": None}

        vectors = []
        for idx, ((chunk, cmeta), embedding) in enumerate(zip(chunks_with_meta, embeddings)):
            vmeta = {"chunk_index": idx, "document_filename": filename}
            vmeta.update(cmeta)
            vectors.append(
                DocumentVector(
                    document_id=doc_id,
                    chunk_index=idx,
                    embedding=embedding,
                    content=chunk,
                    metadata=vmeta,
                )
            )

        created = await self.vector_repo.create_vectors_batch(vectors)
        if self.graph_repo:
            try:
                await self.graph_repo.rebuild_document_graph(
                    store_type="project",
                    document_id=doc_id,
                    chunks=[(v.chunk_index, v.content) for v in vectors],
                )
            except Exception as e:
                logger.warning("project graph индекс не собран для документа %s: %s", doc_id, e)
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
        cfg = get_settings().rag

        async def _vectors(emb, lim):
            return await self.vector_repo.similarity_search(
                query_embedding=emb,
                limit=lim,
                project_id=project_id,
                document_id=document_id,
                filters=filters,
            )

        async def _keywords(text, lim):
            return await self.vector_repo.keyword_search(
                text,
                limit=lim,
                project_id=project_id,
                document_id=document_id,
                filters=filters,
            )

        async def _substring(tokens, lim):
            return await self.vector_repo.substring_search(
                tokens,
                limit=lim,
                project_id=project_id,
                document_id=document_id,
            )

        async def _fetch_doc(doc_id: int):
            return await self.vector_repo.get_vectors_by_document(doc_id)

        async def _find_docs_by_filename(name: str):
            # В проектных RAG запросы всегда скоупятся к project_id —
            # иначе саммари по одному файлу могло бы «склеиваться» с тем же
            # именем из другого проекта.
            return await self.doc_repo.find_document_ids_by_filename(
                name, project_id=project_id
            )

        hits, trace = await run_retrieval_pipeline(
            store="project",
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
            log_store_label=f"project_rag (project_id={project_id})",
        )
        return (hits, trace) if return_trace else hits

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
        if self.graph_repo:
            try:
                await self.graph_repo.delete_document_graph("project", document_id)
            except Exception:
                pass
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
