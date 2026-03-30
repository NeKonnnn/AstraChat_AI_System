"""
Тонкий async-клиент для SVC-RAG.
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def _svc_rag_document_index_timeout() -> httpx.Timeout:
    """Ожидание ответа POST /…/documents: парсинг + чанки + серия embed к rag-models."""
    try:
        read_sec = float(os.getenv("SVC_RAG_INDEX_READ_TIMEOUT", "900"))
    except ValueError:
        read_sec = 900.0
    read_sec = max(60.0, read_sec)
    return httpx.Timeout(120.0, read=read_sec)


def _rag_query_preview(q: str, max_len: int = 72) -> str:
    s = (q or "").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _dedupe_jaccard_threshold() -> float:
    try:
        return float(os.getenv("RAG_DEDUP_JACCARD", "0.88"))
    except ValueError:
        return 0.88


def _log_backend_rag_strategy_banner(
    *,
    path: str,
    strategy: Optional[str],
    k: int,
    document_id: Optional[int],
    use_reranking: Optional[bool],
    hits: int,
    query_preview: str,
    prep_suffix: str,
    from_cache: bool,
) -> None:
    """Видно в `docker compose logs -f astrachat-backend` без svc-rag."""
    bar = "*" * 72
    logger.info(bar)
    logger.info("[astrachat-backend RAG] Использована стратегия в запросе к SVC-RAG: %s", strategy or "(default)")
    logger.info("[astrachat-backend RAG] endpoint=%s k=%s document_id=%s use_reranking=%s", path, k, document_id, use_reranking)
    logger.info("[astrachat-backend RAG] хитов после ответа=%s %s", hits, "(из кэша)" if from_cache else "")
    logger.info("[astrachat-backend RAG] запрос: %s", query_preview)
    if prep_suffix:
        logger.info("[astrachat-backend RAG] %s", prep_suffix.strip())
    logger.info(
        "[astrachat-backend RAG] Реальный пайплайн (косинус / BM25 / реранк / graph) смотрите в логах контейнера "
        "svc-rag — блок из %s звёздочек «Использована стратегия поиска».",
        len(bar),
    )
    logger.info(bar)


class RagClient:
    """
    Тонкий async‑клиент для SVC-RAG.
    Не содержит логики поиска - только HTTP‑вызовы.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 60.0):
        settings = get_settings()

        # URL можно задать через ENV (SVC_RAG_URL) или через конфиг (urls.rag_service_* при наличии)
        env_url = os.getenv("SVC_RAG_URL") or os.getenv("RAG_SERVICE_URL")
        if base_url:
            self.base_url = base_url.rstrip("/")
        elif env_url:
            self.base_url = env_url.rstrip("/")
        else:
            # Пытаемся взять из settings.urls, если там есть rag_service_docker / rag_service_port
            urls = getattr(settings, "urls", None)
            candidate = None
            if urls:
                if getattr(urls, "rag_service_docker", None):
                    candidate = urls.rag_service_docker
                elif getattr(urls, "rag_service_port", None):
                    candidate = urls.rag_service_port
            self.base_url = (candidate or "http://svc-rag:8000").rstrip("/")

        self.timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        http_timeout: Optional[Union[float, httpx.Timeout]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        client_timeout = self.timeout if http_timeout is None else http_timeout
        try:
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    files=files,
                    data=data,
                    params=params,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            detail = None
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise RuntimeError(f"SVC-RAG {method} {url} failed: {e.response.status_code} {detail}") from e
        except Exception as e:
            raise RuntimeError(f"SVC-RAG {method} {url} error: {e}") from e

    @staticmethod
    def _parse_hits(resp: Any) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        hits = resp.get("hits", []) if isinstance(resp, dict) else []
        return [
            (
                h.get("content", ""),
                float(h.get("score", 0.0)),
                h.get("document_id"),
                h.get("chunk_index"),
            )
            for h in hits
        ]

    async def _merge_variant_searches(
        self,
        path: str,
        base_body: Dict[str, Any],
        variants: List[str],
        k: int,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        merged: Dict[Tuple[Optional[int], Optional[int]], Tuple[str, float, Optional[int], Optional[int]]] = {}
        order_q: List[str] = []
        for q in [base_body["query"]] + list(variants):
            t = (q or "").strip()
            if t and t not in order_q:
                order_q.append(t)
        vq = base_body.get("vector_query")
        for idx, qtext in enumerate(order_q):
            body = {**base_body, "query": qtext}
            # HyDE/vector_query только для основной формулировки; варианты — отдельные эмбеддинги без HyDE.
            if idx > 0 or not vq:
                body.pop("vector_query", None)
            resp = await self._request("POST", path, json=body)
            for tup in self._parse_hits(resp):
                key = (tup[2], tup[3])
                prev = merged.get(key)
                if prev is None or float(tup[1]) > float(prev[1]):
                    merged[key] = tup
        out = sorted(merged.values(), key=lambda x: float(x[1]), reverse=True)
        return out[:k]

    async def _search_with_pipeline(
        self,
        path: str,
        query: str,
        k: int,
        *,
        log_tag: str,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        from backend.rag_query.pipeline import process_user_query
        from backend.rag_query.postprocess import dedupe_rag_hits
        from backend.rag_query.semantic_cache import (
            cache_get,
            cache_set,
            make_cache_key,
            semantic_cache_enabled,
        )

        from backend import app_state as _app_state

        _fix = bool(getattr(_app_state, "rag_query_fix_typos", False))
        _multi = bool(getattr(_app_state, "rag_multi_query_enabled", False))
        _hyde = bool(getattr(_app_state, "rag_hyde_enabled", False))
        pq = await process_user_query(
            query,
            fix_typos=_fix,
            multi_query=_multi,
            hyde=_hyde,
        )
        body: Dict[str, Any] = {"query": pq.query_for_search, "k": k}
        if document_id is not None:
            body["document_id"] = document_id
        if use_reranking is not None:
            body["use_reranking"] = use_reranking
        if strategy is not None:
            body["strategy"] = strategy
        if pq.vector_query:
            body["vector_query"] = pq.vector_query
        if pq.filters:
            body["filters"] = pq.filters

        cache_key = make_cache_key(
            path,
            pq.normalized,
            k,
            strategy,
            document_id,
            use_reranking,
            pq.filters,
            project_id,
            rag_fix_typos=_fix,
            rag_multi_query=_multi,
            rag_hyde=_hyde,
        )
        if semantic_cache_enabled():
            cached = cache_get(cache_key)
            if cached is not None:
                hits_cached = dedupe_rag_hits(cached, jaccard_threshold=_dedupe_jaccard_threshold())
                _log_backend_rag_strategy_banner(
                    path=path,
                    strategy=body.get("strategy"),
                    k=k,
                    document_id=document_id,
                    use_reranking=use_reranking,
                    hits=len(hits_cached),
                    query_preview=_rag_query_preview(pq.query_for_search),
                    prep_suffix="",
                    from_cache=True,
                )
                return hits_cached

        if pq.multi_variants:
            hits = await self._merge_variant_searches(path, body, pq.multi_variants, k)
        else:
            resp = await self._request("POST", path, json=body)
            hits = self._parse_hits(resp)

        hits = dedupe_rag_hits(hits, jaccard_threshold=_dedupe_jaccard_threshold())
        if semantic_cache_enabled():
            cache_set(cache_key, hits)
        prep_bits: List[str] = []
        if pq.multi_variants:
            prep_bits.append("multi-query")
        if pq.vector_query:
            prep_bits.append("HyDE(vector_query)")
        prep_s = f"препроцесс backend: {', '.join(prep_bits)}" if prep_bits else ""
        _log_backend_rag_strategy_banner(
            path=path,
            strategy=body.get("strategy"),
            k=k,
            document_id=document_id,
            use_reranking=use_reranking,
            hits=len(hits),
            query_preview=_rag_query_preview(pq.query_for_search),
            prep_suffix=prep_s,
            from_cache=False,
        )
        return hits

    async def health(self) -> Dict[str, Any]:
        return await self._request("GET", "/health")

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        minio_object: Optional[str] = None,
        minio_bucket: Optional[str] = None,
        original_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        files = {
            "file": (filename, file_bytes, "application/octet-stream"),
        }
        data: Dict[str, Any] = {}
        if minio_object:
            data["minio_object"] = minio_object
        if minio_bucket:
            data["minio_bucket"] = minio_bucket
        if original_path:
            data["original_path"] = original_path

        return await self._request(
            "POST",
            "/documents",
            files=files,
            data=data,
            http_timeout=_svc_rag_document_index_timeout(),
        )

    async def list_documents(self) -> List[Dict[str, Any]]:
        resp = await self._request("GET", "/documents")
        return resp

    async def delete_document_by_id(self, document_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/documents/{document_id}")

    async def delete_document_by_filename(self, filename: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/documents/by-filename/{filename}")

    async def get_document_start_chunks(
        self,
        document_id: int,
        max_chunks: int = 2,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        try:
            resp = await self._request(
                "GET",
                f"/documents/{document_id}/chunks",
                params={"start": 0, "limit": max_chunks},
            )
        except Exception:
            return []
        chunks = resp.get("chunks", [])
        return [
            (
                c.get("content", ""),
                1.0,
                c.get("document_id"),
                c.get("chunk_index"),
            )
            for c in chunks
        ]

    async def search(
        self,
        query: str,
        k: int = 10,
        strategy: Optional[str] = None,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        return await self._search_with_pipeline(
            "/search",
            query,
            k,
            log_tag="/search",
            document_id=document_id,
            use_reranking=use_reranking,
            strategy=strategy,
            project_id=None,
        )

    async def get_confidence_report(self) -> Dict[str, Any]:
        return await self._request("GET", "/documents/report/confidence")

    async def get_image_minio_info(self, filename: str) -> Optional[Dict[str, Any]]:
        resp = await self._request("GET", f"/documents/minio-info/{filename}")
        if resp is None:
            return None
        return resp

    # ─── Knowledge Base (постоянная база знаний) ─────────────────────────────

    async def kb_upload_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Загрузить документ в постоянную Базу Знаний."""
        files = {
            "file": (filename, file_bytes, "application/octet-stream"),
        }
        return await self._request(
            "POST",
            "/kb/documents",
            files=files,
            http_timeout=_svc_rag_document_index_timeout(),
        )

    async def kb_list_documents(self) -> List[Dict[str, Any]]:
        """Список документов в Базе Знаний."""
        resp = await self._request("GET", "/kb/documents")
        return resp if isinstance(resp, list) else []

    async def kb_delete_document(self, document_id: int) -> Dict[str, Any]:
        """Удалить документ из Базы Знаний."""
        return await self._request("DELETE", f"/kb/documents/{document_id}")

    async def kb_search(
        self,
        query: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Поиск по Базе Знаний.

        Возвращает список (content, score, document_id, chunk_index).
        """
        return await self._search_with_pipeline(
            "/kb/search",
            query,
            k,
            log_tag="/kb/search",
            document_id=document_id,
            use_reranking=use_reranking,
            strategy=strategy,
            project_id=None,
        )

    # ─── Библиотека памяти (настройки): memory_rag_documents / memory_rag_vectors ─

    async def memory_rag_index_document(
        self,
        file_bytes: bytes,
        filename: str,
        minio_object: Optional[str] = None,
        minio_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data: Dict[str, Any] = {}
        if minio_object:
            data["minio_object"] = minio_object
        if minio_bucket:
            data["minio_bucket"] = minio_bucket
        return await self._request(
            "POST",
            "/memory-rag/documents",
            files=files,
            data=data,
            http_timeout=_svc_rag_document_index_timeout(),
        )

    async def memory_rag_list_documents(self) -> List[Dict[str, Any]]:
        resp = await self._request("GET", "/memory-rag/documents")
        return resp if isinstance(resp, list) else []

    async def memory_rag_delete_document(self, document_id: int) -> Dict[str, Any]:
        return await self._request("DELETE", f"/memory-rag/documents/{document_id}")

    async def memory_rag_search(
        self,
        query: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        return await self._search_with_pipeline(
            "/memory-rag/search",
            query,
            k,
            log_tag="/memory-rag/search",
            document_id=document_id,
            use_reranking=use_reranking,
            strategy=strategy,
            project_id=None,
        )


    # ─── RAG проектов: project_rag_documents / project_rag_vectors ─────────────

    async def project_rag_upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        project_id: str,
        minio_object: Optional[str] = None,
        minio_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Загрузить документ в RAG-хранилище проекта."""
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data: Dict[str, Any] = {}
        if minio_object:
            data["minio_object"] = minio_object
        if minio_bucket:
            data["minio_bucket"] = minio_bucket
        return await self._request(
            "POST",
            f"/project-rag/projects/{project_id}/documents",
            files=files,
            data=data,
            http_timeout=_svc_rag_document_index_timeout(),
        )

    async def project_rag_list_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """Список документов проекта."""
        resp = await self._request("GET", f"/project-rag/projects/{project_id}/documents")
        return resp if isinstance(resp, list) else []

    async def project_rag_delete_document(self, project_id: str, document_id: int) -> Dict[str, Any]:
        """Удалить один документ из RAG проекта."""
        return await self._request(
            "DELETE", f"/project-rag/projects/{project_id}/documents/{document_id}"
        )

    async def project_rag_delete_project(self, project_id: str) -> Dict[str, Any]:
        """Удалить все RAG-данные проекта (при удалении проекта)."""
        return await self._request("DELETE", f"/project-rag/projects/{project_id}")

    async def project_rag_search(
        self,
        query: str,
        project_id: str,
        k: int = 8,
        document_id: Optional[int] = None,
        use_reranking: Optional[bool] = None,
        strategy: Optional[str] = None,
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Поиск по RAG-документам проекта."""
        path = f"/project-rag/projects/{project_id}/search"
        return await self._search_with_pipeline(
            path,
            query,
            k,
            log_tag=f"project-rag/{project_id}/search",
            document_id=document_id,
            use_reranking=use_reranking,
            strategy=strategy,
            project_id=project_id,
        )


_rag_client_singleton: Optional[RagClient] = None


def get_rag_client() -> RagClient:
    global _rag_client_singleton
    if _rag_client_singleton is None:
        _rag_client_singleton = RagClient()
    return _rag_client_singleton
