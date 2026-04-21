"""
Провайдер OpenAI (api.openai.com).

OpenAI-совместимый провайдер + несколько особенностей:

- API-ключ обязателен (ENV ``LLM_PROVIDER_<ID>_API_KEY`` или явный
  ``api_key_env``);
- ``/health`` нет — используем ``/v1/models`` как health-probe;
- ``ensure_model_loaded`` — no-op проверка по ``/v1/models`` (все модели
  виртуально «загружены», сервер Amazon-style обслуживает их все сразу);
- capability ``vision=True``, streaming поддерживается (SSE).
"""

from __future__ import annotations

from .base import ProviderCapabilities
from .openai_compat import OpenAICompatProvider


class OpenAIProvider(OpenAICompatProvider):
    """api.openai.com (или совместимый aggregator с тем же REST)."""

    #: У OpenAI нет /v1/health. Сразу fallback на /v1/models.
    HEALTH_PATH: str = "/v1/models"
    HEALTH_FALLBACK_TO_MODELS: bool = True

    _capabilities = ProviderCapabilities(
        hot_swap=False,
        multi_loaded=True,
        native_chat_api=True,
        streaming=True,
        vision=True,
    )


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter — агрегатор, полностью OpenAI-совместимый REST.

    Единственное отличие: рекомендуется добавлять ``HTTP-Referer`` и
    ``X-Title`` заголовки. Но это не обязательно — работает без них.
    """

    def _headers(self, *, accept_sse: bool = False):
        headers = super()._headers(accept_sse=accept_sse)
        referer = (self._config.extra or {}).get("http_referer")
        if referer:
            headers["HTTP-Referer"] = str(referer)
        title = (self._config.extra or {}).get("x_title")
        if title:
            headers["X-Title"] = str(title)
        return headers
