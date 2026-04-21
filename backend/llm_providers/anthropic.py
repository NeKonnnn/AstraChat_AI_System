"""
Провайдер Anthropic (api.anthropic.com/v1/messages).

Anthropic **не** OpenAI-совместим:

- endpoint ``/v1/messages`` вместо ``/v1/chat/completions``;
- тело запроса другое: ``system`` — отдельное поле (не элемент messages);
- role ``assistant``/``user`` сохранились, но API требует чередования;
- streaming формат не SSE ``data:`` OpenAI-style, а собственный SSE с
  ``event: content_block_delta``;
- заголовок ``x-api-key`` (не ``Authorization``) + ``anthropic-version``.

Здесь реализуем ``chat`` и ``stream_chat``. ``list_models`` — через
``/v1/models`` (Anthropic добавили этот endpoint в 2024).
"""

from __future__ import annotations

import json
import logging
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


ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Anthropic REST — собственный формат, не OpenAI-совместимый."""

    _capabilities = ProviderCapabilities(
        hot_swap=False,
        multi_loaded=True,
        native_chat_api=False,  # не OpenAI-compat
        streaming=True,
        vision=True,
    )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    # ---- helpers ----------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        api_key = self.get_api_key()
        if not api_key:
            logger.warning(
                "AnthropicProvider %s: API-ключ отсутствует (ENV %s)",
                self.id, self._config.api_key_env,
            )
        version = (self._config.extra or {}).get("anthropic_version") or ANTHROPIC_API_VERSION
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key or "",
            "anthropic-version": str(version),
        }

    def _timeout(self, read: float = 120.0) -> httpx.Timeout:
        return httpx.Timeout(read, connect=10.0, read=read, write=10.0)

    @staticmethod
    def _split_system(messages: List[Dict[str, Any]]) -> "tuple[Optional[str], List[Dict[str, Any]]]":
        """Anthropic ожидает system отдельным полем. Выдёргиваем первое system-сообщение."""
        system_prompt: Optional[str] = None
        rest: List[Dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system" and system_prompt is None:
                content = m.get("content") or ""
                if isinstance(content, list):
                    # Приведение к плоской строке (ожидание Anthropic для system).
                    parts = [c.get("text", "") for c in content if isinstance(c, dict)]
                    system_prompt = "\n".join(p for p in parts if p)
                else:
                    system_prompt = str(content)
            else:
                rest.append(m)
        return system_prompt, rest

    # ---- health / list_models --------------------------------------------

    async def health(self) -> ProviderHealth:
        """Anthropic не имеет health. Используем пинг ``/v1/models``."""
        if not self.has_api_key():
            return ProviderHealth(healthy=False, error="API-ключ не задан")
        try:
            async with httpx.AsyncClient(timeout=self._timeout(read=10.0)) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models", headers=self._headers(),
                )
                if response.status_code == 200:
                    return ProviderHealth(healthy=True)
                return ProviderHealth(
                    healthy=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )
        except Exception as e:
            return ProviderHealth(healthy=False, error=str(e))

    async def list_models(self) -> List[ModelInfo]:
        if not self.has_api_key():
            return []
        try:
            async with httpx.AsyncClient(timeout=self._timeout(read=10.0)) as client:
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
                        display_name=str(row.get("display_name") or mid),
                        extra={k: v for k, v in row.items() if k != "id"},
                    )
                )
            return items
        except Exception as e:
            logger.error("[%s:anthropic] list_models error: %s", self.id, e)
            return []

    async def ensure_model_loaded(self, model_id: str) -> bool:
        mid = (model_id or "").strip()
        if not mid:
            return False
        # Anthropic раздаёт все модели сразу. Считаем ok если ключ задан.
        return self.has_api_key()

    # ---- chat -------------------------------------------------------------

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> Dict[str, Any]:
        system_prompt, rest = self._split_system(messages)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": rest,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=False)
        logger.info("[%s:anthropic] POST /v1/messages model=%r", self.id, model)
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        # Anthropic: content = [{"type": "text", "text": "..."}]
        content_blocks = data.get("content") or []
        text_parts: List[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        return "".join(text_parts)

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        callback: StreamCallback,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True)
        accumulated = ""
        try:
            timeout = httpx.Timeout(300.0, connect=10.0, read=300.0, write=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/v1/messages",
                    headers={**self._headers(), "Accept": "text/event-stream"},
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        ev_type = event.get("type")
                        if ev_type == "content_block_delta":
                            delta = event.get("delta") or {}
                            if delta.get("type") == "text_delta":
                                chunk = str(delta.get("text", ""))
                                if chunk:
                                    accumulated += chunk
                                    if callback(chunk, accumulated) is False:
                                        return accumulated
                        elif ev_type == "message_stop":
                            break
        except httpx.HTTPStatusError as e:
            logger.error("[%s:anthropic] stream HTTP %s", self.id, e.response.status_code)
            return f"Ошибка Anthropic: HTTP {e.response.status_code}"
        except Exception as e:
            logger.error("[%s:anthropic] stream error: %s", self.id, e)
            return f"Ошибка Anthropic: {e}"
        return accumulated
