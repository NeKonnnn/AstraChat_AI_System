"""
Провайдер LiteLLM Proxy.

LiteLLM — роутер, проксирующий запросы к любым backends (OpenAI, Anthropic,
Gemini, Cohere, vLLM, локальные Ollama и т.д.) через единый OpenAI-совместимый
API. С точки зрения нашего кода — это обычный openai-compat endpoint с:

- ``/v1/chat/completions`` (OpenAI format);
- ``/v1/models`` — список настроенных в LiteLLM моделей;
- ``/health`` (у более новых LiteLLM; у старых просто отвечает ``/v1/models``).

``ensure_model_loaded`` = no-op проверка, что имя есть в ``/v1/models``.
Никакого свапа не нужно: LiteLLM сам маршрутизирует на нужный upstream.
"""

from __future__ import annotations

from .base import ProviderCapabilities
from .openai_compat import OpenAICompatProvider


class LiteLLMProvider(OpenAICompatProvider):
    """Тонкая обёртка над OpenAICompatProvider для семантики LiteLLM."""

    #: У LiteLLM есть ``/health/liveliness`` и ``/health``. Берём ``/health``
    #: (200 в норме), fallback на ``/v1/models`` сохраняем на случай прокси
    #: без health.
    HEALTH_PATH: str = "/health"
    HEALTH_FALLBACK_TO_MODELS: bool = True

    _capabilities = ProviderCapabilities(
        hot_swap=False,
        multi_loaded=True,
        native_chat_api=True,
        streaming=True,
        vision=True,
    )
