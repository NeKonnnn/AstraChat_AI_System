# Индексация документов и поиск: парсинг → чанки → эмбеддинги (RAG-MODELS) → pgvector, опционально BM25 и реранк
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from rank_bm25 import BM25Okapi

from app.clients.rag_models_client import RagModelsClient
from app.core.config import get_settings
from app.database.models import Document, DocumentVector
from app.database.repository import DocumentRepository, VectorRepository
from app.services.chunker import split_into_chunks
from app.services.document_parser import parse_document
from app.services.hierarchical import DocumentSummarizer, OptimizedDocumentIndex

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
    ):
        self.document_repo = document_repo
        self.vector_repo = vector_repo
        self.rag_client = rag_models_client
        cfg = get_settings().rag
        self._cfg = cfg

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

        if not text:
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

        chunks = split_into_chunks(text)
        if not chunks:
            return {"ok": False, "error": "После разбиения чанков не осталось", "document_id": None}

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
            DocumentVector(document_id=doc_id, chunk_index=i, embedding=emb, content=chunks[i], metadata={})
            for i, emb in enumerate(embeddings)
        ]
        created = await self.vector_repo.create_vectors_batch(vectors)

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
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """
        Поиск: эмбеддинг запроса → векторный поиск → опционально гибрид с BM25 → опционально rerank.

        strategy:
        - "auto" (по умолчанию) - как в backend DocumentProcessor: приоритет reranking → hierarchical → hybrid → standard.
        - "reranking" - векторный/гибридный/иерархический поиск + rerank.
        - "hierarchical" - умный поиск по иерархии (OptimizedDocumentIndex).
        - "hybrid" - только гибрид (BM25 + векторный), без rerank.
        - "standard" - только векторный поиск (pgvector), без BM25 и rerank.
        Также поддерживается "flat" как синоним "standard".

        Возвращает список (content, score, document_id, chunk_index), где score - комбинированный
        скор (для reranking: 0.7 * rerank_score + 0.3 * original_score, как в backend).
        """
        if not query or not query.strip():
            return []

        user_strategy = (strategy or "auto").lower()
        if user_strategy == "flat":
            user_strategy = "standard"

        # Явный иерархический поиск - отдельная ветка
        if user_strategy == "hierarchical" and self._optimized_index is not None:
            try:
                return await self._optimized_index.smart_search_async(query, k=k, search_strategy="auto")
            except Exception as e:
                logger.warning("Иерархический поиск не удался, fallback на плоский: %s", e)

        # Определяем, использовать ли rerank 
        cfg_rerank_enabled = self._cfg.use_reranking
        if user_strategy == "standard" or user_strategy == "hybrid":
            use_rerank = False
        elif user_strategy == "reranking":
            use_rerank = cfg_rerank_enabled
        else:  # "auto" или любые другие значения по умолчанию
            use_rerank = (use_reranking if use_reranking is not None else cfg_rerank_enabled) and cfg_rerank_enabled

        limit = self._cfg.rerank_top_k if use_rerank else max(k, 50)

        try:
            query_embedding = await self.rag_client.embed_single(query)
        except Exception as e:
            logger.warning("Embed query failed: %s", e)
            return []

        pairs = await self.vector_repo.similarity_search(
            query_embedding,
            limit=limit,
            document_id=document_id,
        )
        if not pairs:
            return []

        # Гибридный поиск (BM25 + векторный) 
        use_hybrid = self.use_hybrid_search and not document_id
        if user_strategy == "standard":
            use_hybrid = False
        elif user_strategy == "hybrid":
            use_hybrid = self.use_hybrid_search and not document_id

        if use_hybrid and self.bm25_index:
            hybrid_results = await self._hybrid_combine(query, pairs, k=limit)
            pairs = [(v, score) for v, score in hybrid_results]

        if use_rerank and len(pairs) > 1:
            passages = [v.content for v, _ in pairs]
            try:
                reranked = await self.rag_client.rerank(query, passages, top_k=k)
                out = []
                for idx, sc in reranked:
                    if idx < len(pairs):
                        v, orig_score = pairs[idx]
                        rerank_score = float(sc)
                        original_score = float(orig_score)
                        final_score = 0.7 * rerank_score + 0.3 * original_score
                        out.append((v.content, final_score, v.document_id, v.chunk_index))
                return out
            except Exception as e:
                logger.warning("Rerank failed, using vector order: %s", e)

        return [(v.content, score, v.document_id, v.chunk_index) for v, score in pairs[:k]]

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
                # Для чанков, которых нет в векторном топе, пытаемся найти их через БД
                vectors = await self.vector_repo.get_vectors_by_document(doc_id)
                vec = next((vv for vv in vectors if vv.chunk_index == chunk_index), None)
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

    async def delete_document(self, document_id: int) -> bool:
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
