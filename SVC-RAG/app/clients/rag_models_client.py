# Клиент к SVC-RAG-MODELS: эмбеддинги и реранкер по HTTP
import logging
from typing import List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RagModelsClient:
    """Вызовы эмбеддинга и реранкера в SVC-RAG-MODELS."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        cfg = get_settings().rag_models_client
        self.base_url = (base_url or cfg.base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else cfg.timeout

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Получить эмбеддинги для списка текстов. Один текст — один вектор."""
        if not texts:
            return []
        url = f"{self.base_url}/v1/embed"
        payload = {"texts": texts}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        embeddings = data.get("embeddings", [])
        return embeddings

    async def embed_single(self, text: str) -> List[float]:
        """Один текст — один вектор."""
        vectors = await self.embed([text])
        return vectors[0] if vectors else []

    async def rerank(self, query: str, passages: List[str], top_k: int = 20) -> List[tuple[int, float]]:
        """
        Реранк пассажей по релевантности к запросу.
        Возвращает список пар (индекс в passages, скор).
        """
        if not passages:
            return []
        url = f"{self.base_url}/v1/rerank"
        payload = {"query": query, "passages": passages, "top_k": min(top_k, len(passages))}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        indices = data.get("indices", [])
        scores = data.get("scores", [])
        return list(zip(indices, scores))

    async def health(self) -> bool:
        """Проверка доступности SVC-RAG-MODELS."""
        try:
            url = f"{self.base_url}/v1/health"
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url)
                return r.status_code == 200
        except Exception as e:
            logger.warning("RAG-MODELS health check failed: %s", e)
            return False
