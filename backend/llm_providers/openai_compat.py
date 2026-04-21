"""
Базовый OpenAI-совместимый провайдер.

Используется как основа для vLLM, Ollama (OpenAI-mode), LiteLLM, OpenRouter,
OpenAI и любых custom-серверов, поддерживающих ``/v1/chat/completions``.
Реализует:

- ``chat`` через POST /v1/chat/completions;
- ``stream_chat`` через POST /v1/chat/completions со SSE;
- ``list_models`` через GET /v1/models;
- ``health`` через GET /v1/health с fallback на /v1/models (если health нет);
- ``ensure_model_loaded`` по умолчанию = проверка, что model_id есть
  в списке моделей провайдера (без сетевых побочных эффектов).

Подклассы могут переопределить любой метод (например, ``LlmSvcProvider``
добавляет POST /v1/models/load в ``ensure_model_loaded``).
"""

from __future__ import annotations

import html as _html_module
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from .base import (
    LLMProvider,
    LLMProviderConfig,
    ModelInfo,
    ProviderCapabilities,
    ProviderHealth,
    StreamCallback,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Очистка ответа LLM от артефактов chat template (перенесено из llm_client.py)
# =============================================================================


_CHAT_TEMPLATE_RE_START = [
    re.compile(r"<\|im_start\|>.*", re.DOTALL),
    re.compile(r"&lt;\|im_start\|&gt;.*", re.DOTALL),
    re.compile(r"&amp;lt;\|im_start\|&amp;gt;.*", re.DOTALL),
    re.compile(r"&amp;amp;lt;\|im_start\|&amp;amp;gt;.*", re.DOTALL),
    re.compile(r"&amp;amp;amp;lt;\|im_start\|&amp;amp;amp;gt;.*", re.DOTALL),
]
_CHAT_TEMPLATE_RE_END = [
    re.compile(r"<\|im_end\|>.*", re.DOTALL),
    re.compile(r"&lt;\|im_end\|&gt;.*", re.DOTALL),
    re.compile(r"&amp;lt;\|im_end\|&amp;gt;.*", re.DOTALL),
]


def clean_llm_response(text: str) -> str:
    """Убирает хвост ``<|im_start|>`` / ``<|im_end|>`` и HTML entities."""
    if not text:
        return text
    for rx in _CHAT_TEMPLATE_RE_START:
        text = rx.sub("", text)
    for rx in _CHAT_TEMPLATE_RE_END:
        text = rx.sub("", text)
    # Вложенный HTML escaping иногда встречается (после нескольких прогонов).
    for _ in range(3):
        new_text = _html_module.unescape(text)
        if new_text == text:
            break
        text = new_text
    return text.rstrip()


# =============================================================================
# OpenAICompatProvider
# =============================================================================


class OpenAICompatProvider(LLMProvider):
    """Провайдер для любого OpenAI-совместимого REST."""

    #: Путь health-эндпоинта. Подклассы могут переопределить (у OpenAI нет
    #: health; у vLLM — ``/health`` без тела).
    HEALTH_PATH: str = "/v1/health"

    #: Если True — ``health()`` падает на ``list_models`` при 404/405 на
    #: HEALTH_PATH (полезно для OpenAI.com, у которого health просто нет).
    HEALTH_FALLBACK_TO_MODELS: bool = True

    _capabilities = ProviderCapabilities(
        hot_swap=False,
        multi_loaded=True,  # В OpenAI-compat ответе /v1/models все модели «доступны».
        native_chat_api=True,
        streaming=True,
        vision=True,
    )

    def __init__(self, config: LLMProviderConfig) -> None:
        super().__init__(config)
        self._timeout_read = float(config.timeout)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    # ---- HTTP helpers -----------------------------------------------------

    def _headers(self, *, accept_sse: bool = False) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if accept_sse:
            headers["Accept"] = "text/event-stream"
        api_key = self.get_api_key()
        if api_key:
            # OpenAI-style. Для llm-svc заголовок игнорируется.
            headers["Authorization"] = f"Bearer {api_key}"
            # На всякий случай дублируем — некоторые custom-серверы ждут X-API-Key.
            headers["X-API-Key"] = api_key
        return headers

    def _short_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0)

    def _request_timeout(self, seconds: Optional[float] = None) -> httpx.Timeout:
        t = float(seconds) if seconds is not None else self._timeout_read
        return httpx.Timeout(t, connect=10.0, read=t, write=10.0)

    # ---- health -----------------------------------------------------------

    async def health(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=self._short_timeout()) as client:
                response = await client.get(
                    f"{self.base_url}{self.HEALTH_PATH}",
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except Exception:
                        payload = {}
                    if isinstance(payload, dict):
                        return self._interpret_health_payload(payload)
                    return ProviderHealth(healthy=True, raw={"value": payload})
                if response.status_code in (404, 405) and self.HEALTH_FALLBACK_TO_MODELS:
                    return await self._health_via_models(client)
                return ProviderHealth(
                    healthy=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )
        except Exception as e:
            return ProviderHealth(healthy=False, error=str(e))

    def _interpret_health_payload(self, payload: Dict[str, Any]) -> ProviderHealth:
        """Из произвольного health-JSON извлекаем список загруженных моделей."""
        loaded: List[str] = []
        lm = payload.get("loaded_models")
        if isinstance(lm, list):
            loaded = [str(x) for x in lm if x]
        elif payload.get("model_loaded") and payload.get("model_name"):
            loaded = [str(payload["model_name"])]
        status = str(payload.get("status", "")).lower()
        healthy = (not status) or status in ("ok", "healthy", "up", "ready")
        return ProviderHealth(healthy=healthy, loaded_models=loaded, raw=payload)

    async def _health_via_models(self, client: httpx.AsyncClient) -> ProviderHealth:
        try:
            response = await client.get(f"{self.base_url}/v1/models", headers=self._headers())
            if response.status_code == 200:
                return ProviderHealth(healthy=True, raw={"fallback": "models"})
            return ProviderHealth(healthy=False, error=f"/v1/models HTTP {response.status_code}")
        except Exception as e:
            return ProviderHealth(healthy=False, error=f"/v1/models: {e}")

    # ---- list models ------------------------------------------------------

    async def list_models(self) -> List[ModelInfo]:
        static = (self._config.static_model or "").strip()
        try:
            async with httpx.AsyncClient(timeout=self._short_timeout()) as client:
                response = await client.get(f"{self.base_url}/v1/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
            items: List[ModelInfo] = []
            for row in data.get("data", []) or []:
                if not isinstance(row, dict):
                    continue
                mid = str(row.get("id") or "").strip()
                if not mid:
                    continue
                items.append(
                    ModelInfo(
                        provider_id=self.id,
                        model_id=mid,
                        display_name=str(row.get("display_name") or row.get("name") or mid),
                        extra={k: v for k, v in row.items() if k not in {"id"}},
                    )
                )
            if not items and static:
                # Сервер вернул пустой список, но в конфиге есть static_model.
                items.append(
                    ModelInfo(
                        provider_id=self.id,
                        model_id=static,
                        display_name=static,
                        extra={"synthetic": True, "reason": "empty_list_with_static_model"},
                    )
                )
            return items
        except Exception as e:
            if static:
                logger.warning(
                    "Provider %s /v1/models failed (%s); fallback на static_model=%r",
                    self.id, e, static,
                )
                return [
                    ModelInfo(
                        provider_id=self.id, model_id=static, display_name=static,
                        extra={"synthetic": True, "reason": f"fallback:{type(e).__name__}"},
                    )
                ]
            logger.error("Provider %s /v1/models error: %s", self.id, e)
            return []

    # ---- ensure model loaded ---------------------------------------------

    async def ensure_model_loaded(self, model_id: str) -> bool:
        """
        Базовая реализация: проверяем, что model_id есть в list_models() или
        совпадает со static_model. Никаких сетевых побочных эффектов.
        Подклассы (LlmSvcProvider) переопределяют это.
        """
        mid = (model_id or "").strip()
        if not mid:
            return False
        static = (self._config.static_model or "").strip()
        if static and mid == static:
            return True
        try:
            models = await self.list_models()
        except Exception as e:
            logger.warning("ensure_model_loaded(%s): list_models error: %s", mid, e)
            return bool(static and mid == static)
        for m in models:
            if m.model_id == mid:
                return True
        logger.warning(
            "Provider %s: модель %r отсутствует в /v1/models. "
            "Она должна быть запущена на стороне сервера (для vLLM/OpenAI свап невозможен).",
            self.id, mid,
        )
        return False

    # ---- chat / stream_chat ----------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        logger.info("[%s] POST /v1/chat/completions model=%r", self.id, model)
        async with httpx.AsyncClient(timeout=self._request_timeout()) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choices = data.get("choices") or []
        if not choices:
            logger.error("[%s] chat: нет choices в ответе: %s", self.id, data)
            return "Ошибка генерации ответа"
        msg = choices[0].get("message") or {}
        content = msg.get("content") or ""
        return clean_llm_response(content)

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        callback: StreamCallback,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = self._headers(accept_sse=True)
        # Большой RAG-контекст → первый токен может идти долго, read-timeout поднимаем.
        stream_timeout = httpx.Timeout(300.0, connect=10.0, read=300.0, write=10.0)
        accumulated = ""
        logger.info("[%s] POST /v1/chat/completions stream=True model=%r", self.id, model)
        try:
            async with httpx.AsyncClient(timeout=stream_timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        chunk = delta.get("content")
                        if not chunk:
                            continue
                        accumulated += chunk
                        # Если модель начала «галлюцинировать» служебные теги — останавливаемся.
                        if "<|im_start|>" in accumulated or "<|im_end|>" in accumulated:
                            logger.info("[%s] обнаружен chat-template tag, обрезаем поток", self.id)
                            break
                        if callback(chunk, accumulated) is False:
                            logger.info("[%s] поток прерван callback'ом", self.id)
                            return clean_llm_response(accumulated)
        except httpx.HTTPStatusError as e:
            logger.error("[%s] stream HTTP %s: %s", self.id, e.response.status_code, e)
            if e.response.status_code == 503:
                detail = ""
                try:
                    detail = str((e.response.json() or {}).get("detail", ""))
                except Exception:
                    detail = (e.response.text or "")[:500]
                low = detail.lower()
                if "not loaded" in low or "не загруж" in low:
                    return (
                        "Модель не загружена в LLM-бэкенде (503). "
                        "Проверьте, что модель активна на стороне провайдера."
                    )
                return "Сервис LLM недоступен (503). Повторите запрос через несколько секунд."
            return f"Ошибка потока: {e}"
        except Exception as e:
            logger.error("[%s] stream error: %s", self.id, e)
            return f"Ошибка потока: {e}"
        return clean_llm_response(accumulated)
