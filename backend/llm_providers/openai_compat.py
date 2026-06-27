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
import os
import re
import uuid
from typing import Any, Dict, List, Optional

import httpx

from backend.settings.cef_logger.cef_logger import (
    log_cef_int003_llm_request,
    log_cef_int006_llm_api_failure,
)

from .base import (
    LLMProvider,
    LLMProviderConfig,
    ChatResult,
    ModelInfo,
    ProviderCapabilities,
    ProviderHealth,
    StreamCallback,
    ToolCall,
)
from backend.settings.logging import get_logger

logger = get_logger(__name__)


def _invoke_stream_callback(callback: Any, chunk: str, acc: str, stream_role: str = "content") -> bool:
    """Вызывает callback стрима; поддерживает 2- и 3-аргументные колбэки."""
    try:
        return bool(callback(chunk, acc, stream_role))
    except TypeError:
        return bool(callback(chunk, acc))


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


def _strip_think_tags(text: str) -> str:
    """Удаляет блоки <think>...</think> и незакрытые <think>... из текста.

    Используется в режиме быстрого ответа (thinking_requested=False), чтобы
    рассуждения модели не попадали в финальный ответ пользователю.
    """
    if not text or "<think>" not in text.lower():
        return text
    # Закрытые блоки
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    # Незакрытый блок (модель не успела закрыть тег)
    text = re.sub(r"<think>[\s\S]*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _normalize_reasoning_payload(value: Any) -> str:
    """Нормализует reasoning payload к плоскому тексту."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                txt = item.get("text") or item.get("content") or item.get("reasoning")
                if isinstance(txt, str):
                    parts.append(txt)
        return "".join(parts)
    if isinstance(value, dict):
        txt = (
            value.get("text")
            or value.get("content")
            or value.get("reasoning")
            or value.get("reasoning_text")
            or value.get("thinking")
            or value.get("thought")
        )
        if isinstance(txt, str):
            return txt
        # Иногда reasoning лежит в массиве content-частей.
        nested_content = value.get("content")
        if isinstance(nested_content, list):
            return _normalize_reasoning_payload(nested_content)
        # Fallback: пробуем найти поле по "разумным" ключам вглубь.
        parts: List[str] = []
        for k, v in value.items():
            if any(token in str(k).lower() for token in ("reason", "think", "thought")):
                parts.append(_normalize_reasoning_payload(v))
        return "".join(parts)
    return str(value)


def _normalize_content_payload(value: Any) -> str:
    """Нормализует content payload к строке."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") in ("text", "output_text"):
                    txt = item.get("text") or item.get("content")
                    if isinstance(txt, str):
                        parts.append(txt)
                else:
                    txt = item.get("content") or item.get("text")
                    if isinstance(txt, str):
                        parts.append(txt)
        return "".join(parts)
    if isinstance(value, dict):
        txt = value.get("text") or value.get("content")
        return txt if isinstance(txt, str) else ""
    return str(value)


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
        multi_loaded=True,
        native_chat_api=True,
        streaming=True,
        vision=True,
        function_calling=True,
        prompt_json_fc=True,
        langgraph_agent=True,
    )

    def __init__(self, config: LLMProviderConfig) -> None:
        super().__init__(config)
        self._timeout_read = float(config.timeout)
        extra = config.extra or {}
        if "function_calling" in extra:
            fc = bool(extra.get("function_calling"))
            self._capabilities = ProviderCapabilities(
                hot_swap=self._capabilities.hot_swap,
                multi_loaded=self._capabilities.multi_loaded,
                native_chat_api=self._capabilities.native_chat_api,
                streaming=self._capabilities.streaming,
                vision=self._capabilities.vision,
                function_calling=fc,
                prompt_json_fc=bool(extra.get("prompt_json_fc", True)),
                langgraph_agent=bool(extra.get("langgraph_agent", True)),
            )

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

    def _auth_diag(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Безопасная диагностика авторизации (без вывода секретов)."""
        hdrs = headers or self._headers()
        return {
            "api_key_env": self._config.api_key_env,
            "api_key_set": bool(self.get_api_key()),
            "auth_header": "Authorization: Bearer *" if "Authorization" in hdrs else None,
            "x_api_key_header": "X-API-Key: *" if "X-API-Key" in hdrs else None,
        }

    def _safe_auth_diag(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Защитный вызов auth-диагностики.
        Нужен на случай старых рантаймов/оберток, где _auth_diag не принимает headers.
        """
        try:
            return self._auth_diag(headers)
        except TypeError:
            try:
                return self._auth_diag()  # type: ignore[call-arg]
            except Exception:
                return {"api_key_env": self._config.api_key_env, "api_key_set": bool(self.get_api_key())}
        except Exception:
            return {"api_key_env": self._config.api_key_env, "api_key_set": bool(self.get_api_key())}

    def _http_error_details(self, e: Exception) -> Dict[str, Any]:
        """
        Нормализованный payload ошибки HTTP для логов.
        Даёт максимально полезную причину: status code + кусок response body.
        """
        if isinstance(e, httpx.HTTPStatusError):
            response = e.response
            body = ""
            try:
                body = (response.text or "")[:500]
            except Exception:
                body = ""
            return {
                "error_type": type(e).__name__,
                "status_code": response.status_code,
                "reason": body or str(e),
            }
        return {
            "error_type": type(e).__name__,
            "status_code": None,
            "reason": str(e),
        }

    def _short_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0)

    def _request_timeout(self, seconds: Optional[float] = None) -> httpx.Timeout:
        t = float(seconds) if seconds is not None else self._timeout_read
        return httpx.Timeout(t, connect=10.0, read=t, write=10.0)

    def _http_verify(self) -> Any:
        """
        TLS verify для httpx.
        Приоритет: TLS_CERT_PATH -> SSL_CERT_FILE -> REQUESTS_CA_BUNDLE -> True.
        """
        for env_name in ("TLS_CERT_PATH", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
            cert_path = str(os.getenv(env_name, "") or "").strip()
            if cert_path:
                return cert_path
        return True

    # ---- health -----------------------------------------------------------

    async def health(self) -> ProviderHealth:
        url = f"{self.base_url}{self.HEALTH_PATH}"
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=self._short_timeout(), verify=self._http_verify()) as client:
                response = await client.get(
                    url,
                    headers=headers,
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
            details = self._http_error_details(e)
            logger.warning(
                "[LLM-PROVIDER][health] id=%s url=%s status=%s type=%s reason=%r auth=%s",
                self.id, url, details.get("status_code"), details.get("error_type"),
                details.get("reason"), self._safe_auth_diag(headers),
            )
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
        configured = [str(m).strip() for m in (self._config.models or []) if str(m or "").strip()]
        url = f"{self.base_url}/v1/models"
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=self._short_timeout(), verify=self._http_verify()) as client:
                response = await client.get(url, headers=headers)
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
            existing_ids = {m.model_id for m in items}
            # Ручной список моделей из конфига добавляем как fallback/override:
            # это позволяет стабильно показывать модели даже при неполном /v1/models.
            for mid in configured:
                if mid in existing_ids:
                    continue
                items.append(
                    ModelInfo(
                        provider_id=self.id,
                        model_id=mid,
                        display_name=mid,
                        extra={"synthetic": True, "reason": "configured_model"},
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
            details = self._http_error_details(e)
            logger.warning(
                "[LLM-PROVIDER][list_models] id=%s url=%s status=%s type=%s reason=%r auth=%s",
                self.id, url, details.get("status_code"), details.get("error_type"),
                details.get("reason"), self._safe_auth_diag(headers),
            )
            if static:
                logger.warning(
                    "Provider %s /v1/models failed (%s); fallback на static_model=%r",
                    self.id, e, static,
                )
                fallback_items = [
                    ModelInfo(
                        provider_id=self.id, model_id=static, display_name=static,
                        extra={"synthetic": True, "reason": f"fallback:{type(e).__name__}"},
                    )
                ]
                existing_ids = {m.model_id for m in fallback_items}
                for mid in configured:
                    if mid in existing_ids:
                        continue
                    fallback_items.append(
                        ModelInfo(
                            provider_id=self.id,
                            model_id=mid,
                            display_name=mid,
                            extra={"synthetic": True, "reason": "configured_model"},
                        )
                    )
                return fallback_items
            if configured:
                return [
                    ModelInfo(
                        provider_id=self.id,
                        model_id=mid,
                        display_name=mid,
                        extra={"synthetic": True, "reason": "configured_model"},
                    )
                    for mid in configured
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

    def _parse_chat_response(self, data: dict, *, cef_rid: str) -> ChatResult:
        choices = data.get("choices") or []
        if not choices:
            logger.error("[%s] chat: нет choices в ответе: %s", self.id, data)
            log_cef_int006_llm_api_failure(
                request_uuid=cef_rid,
                code_status="FORMAT",
                text_status=str(data)[:512],
                service_name=f"openai-compat-{self.id}",
                status_code=200,
            )
            return ChatResult(content="Ошибка генерации ответа")
        msg = choices[0].get("message") or {}
        tool_calls_raw = msg.get("tool_calls") or []
        tool_calls: List[ToolCall] = []
        for tc in tool_calls_raw:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            if not name:
                continue
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw or {})
            except json.JSONDecodeError:
                args = {"raw": args_raw}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or uuid.uuid4().hex),
                    name=name,
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        content = _normalize_content_payload(msg.get("content"))
        reasoning = _normalize_reasoning_payload(
            msg.get("reasoning_content") or msg.get("reasoning")
        ).strip()
        cleaned = clean_llm_response(content)
        if reasoning and "<think>" not in cleaned:
            cleaned = f"<think>{reasoning}</think>\n\n{cleaned}" if reasoning else cleaned
        return ChatResult(content=cleaned, tool_calls=tool_calls, raw_message=msg)

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        request_extra: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
        if request_extra:
            for k, v in request_extra.items():
                if v is not None:
                    payload[k] = v
        cef_rid = uuid.uuid4().hex
        log_cef_int003_llm_request(
            base_url=self.base_url,
            provider_id=self.id,
            model=model,
            request_uuid=cef_rid,
        )
        async with httpx.AsyncClient(timeout=self._request_timeout(), verify=self._http_verify()) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as he:
                log_cef_int006_llm_api_failure(
                    request_uuid=cef_rid,
                    code_status=str(he.response.status_code),
                    text_status=(he.response.text or "")[:512],
                    service_name=f"openai-compat-{self.id}",
                    status_code=he.response.status_code,
                )
                raise
            except Exception as e:
                log_cef_int006_llm_api_failure(
                    request_uuid=cef_rid,
                    code_status="EXCEPTION",
                    text_status=str(e)[:512],
                    service_name=f"openai-compat-{self.id}",
                    status_code=None,
                )
                raise
            data = response.json()
        return self._parse_chat_response(data, cef_rid=cef_rid)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        *,
        request_extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if request_extra:
            for k, v in request_extra.items():
                if v is not None:
                    payload[k] = v
        logger.info(
            "[%s] chat flags: enable_thinking=%r payload_keys=%s",
            self.id,
            payload.get("enable_thinking"),
            sorted(list(payload.keys())),
        )
        logger.info("[%s] POST /v1/chat/completions model=%r", self.id, model)
        result = await self.chat_completion(
            messages,
            model,
            temperature=temperature,
            max_tokens=max_tokens,
            request_extra=request_extra,
        )
        thinking_requested = bool((request_extra or {}).get("enable_thinking"))
        cleaned = result.content
        if not thinking_requested and "<think>" in cleaned.lower():
            return _strip_think_tags(cleaned)
        return cleaned

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        callback: StreamCallback,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        *,
        request_extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if request_extra:
            for k, v in request_extra.items():
                if v is not None:
                    payload[k] = v
        logger.info(
            "[%s] stream enable_thinking=%r model=%r url=%s/v1/chat/completions",
            self.id,
            payload.get("enable_thinking"),
            model,
            self.base_url,
        )
        headers = self._headers(accept_sse=True)
        # Большой RAG-контекст → первый токен может идти долго, read-timeout поднимаем.
        stream_timeout = httpx.Timeout(300.0, connect=10.0, read=300.0, write=10.0)
        accumulated = ""
        reasoning_accumulated = ""
        thinking_requested = bool(payload.get("enable_thinking"))
        logged_delta_shape = False
        logger.info("[%s] POST /v1/chat/completions stream=True model=%r", self.id, model)
        cef_rid = uuid.uuid4().hex
        log_cef_int003_llm_request(
            base_url=self.base_url,
            provider_id=self.id,
            model=model,
            request_uuid=cef_rid,
        )
        try:
            async with httpx.AsyncClient(timeout=stream_timeout, verify=self._http_verify()) as client:
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
                        if not logged_delta_shape:
                            logged_delta_shape = True
                            logger.info(
                                "[%s] first delta keys=%s has_reasoning_fields=%s has_content_fields=%s",
                                self.id,
                                sorted(list(delta.keys())),
                                any(k in delta for k in ("reasoning_content", "reasoning", "reasoning_text", "thinking", "thought")),
                                any(k in delta for k in ("content", "text", "output_text", "message")),
                            )
                        reasoning_source = delta.get("reasoning_content")
                        if reasoning_source is None:
                            reasoning_source = delta.get("reasoning")
                        if reasoning_source is None:
                            reasoning_source = delta.get("reasoning_text")
                        if reasoning_source is None:
                            reasoning_source = delta.get("thinking")
                        if reasoning_source is None:
                            reasoning_source = delta.get("thought")
                        reasoning_chunk = _normalize_reasoning_payload(reasoning_source)
                        if thinking_requested and reasoning_chunk:
                            reasoning_accumulated += reasoning_chunk
                            if _invoke_stream_callback(callback, reasoning_chunk, reasoning_accumulated, "reasoning") is False:
                                logger.info("[%s] поток прерван callback'ом (reasoning)", self.id)
                                return clean_llm_response(accumulated)
                        chunk = _normalize_content_payload(
                            delta.get("content")
                            or delta.get("text")
                            or delta.get("output_text")
                            or delta.get("message")
                        )
                        if not chunk:
                            continue
                        accumulated += chunk
                        # Если модель начала «галлюцинировать» служебные теги — останавливаемся.
                        if "<|im_start|>" in accumulated or "<|im_end|>" in accumulated:
                            logger.info("[%s] обнаружен chat-template tag, обрезаем поток", self.id)
                            break
                        if _invoke_stream_callback(callback, chunk, accumulated, "content") is False:
                            logger.info("[%s] поток прерван callback'ом", self.id)
                            return clean_llm_response(accumulated)
        except httpx.HTTPStatusError as e:
            logger.error("[%s] stream HTTP %s: %s", self.id, e.response.status_code, e)
            log_cef_int006_llm_api_failure(
                request_uuid=cef_rid,
                code_status=str(e.response.status_code),
                text_status=(e.response.text or "")[:512],
                service_name=f"openai-compat-{self.id}",
                status_code=e.response.status_code,
            )
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
            log_cef_int006_llm_api_failure(
                request_uuid=cef_rid,
                code_status="EXCEPTION",
                text_status=str(e)[:512],
                service_name=f"openai-compat-{self.id}",
                status_code=None,
            )
            return f"Ошибка потока: {e}"
        cleaned = clean_llm_response(accumulated)
        # Режим мышления: рассуждения уже ушли в chat_thinking — в финальную строку только ответ.
        if thinking_requested:
            return cleaned
        # Быстрый режим: если модель всё равно встроила <think> в content — убираем.
        if "<think>" in cleaned.lower():
            return _strip_think_tags(cleaned)
        if reasoning_accumulated.strip() and "<think>" not in cleaned:
            return f"<think>{reasoning_accumulated.strip()}</think>\n\n{cleaned}"
        return cleaned
