"""
Тонкий async-клиент для SVC-RAG.
"""
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import get_settings


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
    ) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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

        return await self._request("POST", "/documents", files=files, data=data)

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
        body: Dict[str, Any] = {
            "query": query,
            "k": k,
        }
        if document_id is not None:
            body["document_id"] = document_id
        if use_reranking is not None:
            body["use_reranking"] = use_reranking
        if strategy is not None:
            body["strategy"] = strategy

        resp = await self._request("POST", "/search", json=body)
        hits = resp.get("hits", [])
        return [
            (
                h.get("content", ""),
                float(h.get("score", 0.0)),
                h.get("document_id"),
                h.get("chunk_index"),
            )
            for h in hits
        ]

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
        return await self._request("POST", "/kb/documents", files=files)

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
    ) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
        """Поиск по Базе Знаний.

        Возвращает список (content, score, document_id, chunk_index).
        """
        body: Dict[str, Any] = {"query": query, "k": k}
        if document_id is not None:
            body["document_id"] = document_id
        if use_reranking is not None:
            body["use_reranking"] = use_reranking

        resp = await self._request("POST", "/kb/search", json=body)
        hits = resp.get("hits", [])
        return [
            (
                h.get("content", ""),
                float(h.get("score", 0.0)),
                h.get("document_id"),
                h.get("chunk_index"),
            )
            for h in hits
        ]


_rag_client_singleton: Optional[RagClient] = None


def get_rag_client() -> RagClient:
    global _rag_client_singleton
    if _rag_client_singleton is None:
        _rag_client_singleton = RagClient()
    return _rag_client_singleton
