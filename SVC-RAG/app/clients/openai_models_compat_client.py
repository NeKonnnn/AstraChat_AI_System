# Клиент моделей RAG к OpenAI-совместимому провайдеру (Phoenix / LiteLLM, свой vLLM).
# Контракт совпадает с RagModelsClient: embed, embed_single, rerank, health.
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

class OpenAICompatModelsClient:
    """Эмбеддинги и реранк через OpenAI-совместимый HTTP API.

    Параметры приходят снаружи (из фабрики), конфиг класс не читает —
    так один и тот же клиент обслуживает и Phoenix, и будущий свой vLLM.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key_env: Optional[str] = None,
        embedding_model: Optional[str] = None,
        reranker_model: Optional[str] = None,
        timeout: float = 300.0,
        embed_batch_size: int = 24,
    ) -> None:
        self.provider_id = provider_id
        self.base_url = (base_url or "").rstrip("/")
        self.api_key_env = api_key_env
        self.embedding_model = embedding_model
        self.reranker_model = reranker_model
        self.timeout = float(timeout)
        self.embed_batch_size = max(1, int(embed_batch_size or 24))
        self._logged_dim = False

    # ---------- инфраструктура ----------

    def get_api_key(self) -> str:
        if not self.api_key_env:
            return ""
        return str(os.getenv(self.api_key_env, "") or "").strip()

    def _headers(self) -> Dict[str, str]:
        # Как в backend/llm_providers/openai_compat.py: LiteLLM принимает оба варианта.
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_key = self.get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-Key"] = api_key
        return headers

    def _http_verify(self) -> Any:
        """TLS verify. Приоритет: TLS_CERT_PATH -> SSL_CERT_FILE -> REQUESTS_CA_BUNDLE -> True.

        Тот же порядок, что у backend. Phoenix за внутренним CA — без этого
        будет SSLCertVerificationError на первом же вызове.
        """
        for env_name in ("TLS_CERT_PATH", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
            cert_path = str(os.getenv(env_name, "") or "").strip()
            if cert_path:
                return cert_path
        return True

    def _client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        t = float(timeout if timeout is not None else self.timeout)
        return httpx.AsyncClient(
            timeout=httpx.Timeout(t, connect=10.0, read=t, write=10.0),
            verify=self._http_verify(),
        )

    def _log_http_error(self, what: str, err: Exception) -> None:
        """Подробный лог ошибки. В банке нет curl — это единственная диагностика."""
        if isinstance(err, httpx.HTTPStatusError):
            body = (err.response.text or "")[:500]
            logger.error(
                "[%s] %s: HTTP %s, тело=%s (api_key_env=%s, ключ_задан=%s)",
                self.provider_id,
                what,
                err.response.status_code,
                body,
                self.api_key_env,
                bool(self.get_api_key()),
            )
            return
        logger.error(
            "[%s] %s: %s: %s (base_url=%s). Расшифровка: "
            "'missing protocol' → base_url без схемы; "
            "'Name or service not known' → неверный хост/namespace; "
            "'Connection refused' → порт; "
            "'SSL'/'certificate' → CA-сертификат (TLS_CERT_PATH).",
            self.provider_id,
            what,
            type(err).__name__,
            err,
            self.base_url,
        )

    # ---------- discovery ----------

    async def list_models(self) -> List[str]:
        """Список id моделей провайдера. Пишем в лог — это и есть discovery без curl."""
        url = f"{self.base_url}/v1/models"
        try:
            async with self._client(timeout=30.0) as client:
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self._log_http_error("GET /v1/models", e)
            return []
        items = data.get("data") or []
        ids = [
            str(item.get("id"))
            for item in items
            if isinstance(item, dict) and item.get("id")
        ]
        logger.info("[%s] models: %s", self.provider_id, ids)
        return ids

    # ---------- эмбеддинги ----------

    def _check_dim(self, dim: int) -> None:
        """Гард размерности: НЕ мигрируем БД молча (в отличие от RagModelsClient).

        Авто-миграция здесь стёрла бы корпус первым же embed'ом запроса после
        случайного выбора модели с другой размерностью. Явная миграция —
        POST /v1/schema/embedding-dim (backend делает это в select-флоу).
        """
        from app.core.config import get_settings

        db_dim = int(get_settings().postgresql.embedding_dim or 0)
        if db_dim and dim != db_dim:
            raise RuntimeError(
                f"[{self.provider_id}] модель {self.embedding_model} даёт dim={dim}, "
                f"а БД настроена на dim={db_dim}. Автоматическая миграция запрещена "
                f"(она очищает корпус). Либо выполните явную миграцию "
                f'POST /v1/schema/embedding-dim {{"embedding_dim": {dim}}} и '
                f"переиндексируйте документы, либо выберите модель с dim={db_dim}."
            )

    @staticmethod
    def _parse_embeddings(data: Dict[str, Any], expected: int) -> List[List[float]]:
        """Разбор ответа /v1/embeddings.

        Порядок data[] по спеке НЕ гарантирован — сортируем по index, иначе
        векторы молча разъедутся с текстами.
        """
        items = data.get("data") or []
        if len(items) != expected:
            raise ValueError(
                f"Число эмбеддингов ({len(items)}) не совпадает с размером батча ({expected})"
            )
        ordered = sorted(items, key=lambda it: int(it.get("index") or 0))
        return [list(it.get("embedding") or []) for it in ordered]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Эмбеддинги для списка текстов. Один текст — один вектор."""
        if not texts:
            return []
        if not self.embedding_model:
            raise ValueError(
                f"[{self.provider_id}] embedding_model не задан — выберите модель в UI"
            )
        url = f"{self.base_url}/v1/embeddings"
        all_embeddings: List[List[float]] = []
        batch_size = self.embed_batch_size
        async with self._client() as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                if len(texts) > batch_size:
                    logger.info(
                        "[%s] embed: батч %s–%s из %s",
                        self.provider_id,
                        start + 1,
                        start + len(batch),
                        len(texts),
                    )
                try:
                    resp = await client.post(
                        url,
                        headers=self._headers(),
                        json={"model": self.embedding_model, "input": batch},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self._log_http_error("POST /v1/embeddings", e)
                    raise
                part = self._parse_embeddings(data, len(batch))
                if part and part[0]:
                    self._check_dim(len(part[0]))
                all_embeddings.extend(part)

        if all_embeddings and not self._logged_dim:
            logger.info(
                "[%s] embed dim=%s (model=%s)",
                self.provider_id,
                len(all_embeddings[0]),
                self.embedding_model,
            )
            self._logged_dim = True
        return all_embeddings

    async def embed_single(self, text: str) -> List[float]:
        """Один текст — один вектор."""
        vectors = await self.embed([text])
        return vectors[0] if vectors else []

    async def probe_dim(self) -> int:
        """Размерность embedding-модели одним пробным вызовом (БЕЗ dim-гарда).

        Используется эндпоинтом переключения: узнать dim ДО решения о миграции.
        """
        if not self.embedding_model:
            raise ValueError(
                f"[{self.provider_id}] embedding_model не задан - probe_dim невозможен"
            )
        url = f"{self.base_url}/v1/embeddings"
        try:
            async with self._client(timeout=60.0) as client:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"model": self.embedding_model, "input": ["ping"]},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self._log_http_error("POST /v1/embeddings (probe)", e)
            raise
        vectors = self._parse_embeddings(data, 1)
        dim = len(vectors[0]) if vectors and vectors[0] else 0
        logger.info(
            "[%s] probe dim=%s (model=%s)", self.provider_id, dim, self.embedding_model
        )
        return dim

    # ---------- реранк ----------

    async def rerank(
        self, query: str, passages: List[str], top_k: int = 20
    ) -> List[Tuple[int, float]]:
        """Реранк пассажей. Возвращает пары (индекс в passages, скор).

        При ошибке — подробный лог и re-raise, как у нативного RagModelsClient.
        НЕ возвращать пустой список: вызывающий код (rerank_helpers) ловит
        исключение и откатывается на векторный порядок — это и есть graceful
        fallback, а [] неотличим от «реранкер счёл всё нерелевантным».
        """
        if not passages:
            return []
        if not self.reranker_model:
            raise ValueError(
                f"[{self.provider_id}] reranker_model не задан — выберите модель в UI "
                "(вызывающий код продолжит без реранка)"
            )
        url = f"{self.base_url}/v1/rerank"
        payload = {
            "model": self.reranker_model,
            "query": query,
            "documents": passages,
            "top_n": min(int(top_k), len(passages)),
        }
        try:
            async with self._client() as client:
                resp = await client.post(url, headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            self._log_http_error("POST /v1/rerank", e)
            raise

        results = data.get("results") or []
        pairs: List[Tuple[int, float]] = []
        for item in results:
            if not isinstance(item, dict) or item.get("index") is None:
                continue
            pairs.append(
                (int(item["index"]), float(item.get("relevance_score") or 0.0))
            )
        logger.info(
            "[%s] rerank: ok, вернулось %s из %s (model=%s)",
            self.provider_id,
            len(pairs),
            len(passages),
            self.reranker_model,
        )
        return pairs

    # ---------- health ----------

    async def health(self) -> bool:
        """Доступность провайдера.

        Бьём в /v1/models, а не в health/liveliness: liveliness отвечает 200 и
        без ключа, а нам надо знать, что сеть + CA + авторизация в порядке.
        """
        try:
            async with self._client(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.base_url}/v1/models", headers=self._headers()
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning("[%s] health check failed: %s", self.provider_id, e)
            return False