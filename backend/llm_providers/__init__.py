"""
Унифицированная абстракция LLM-провайдеров.

Позволяет работать с разными REST-бэкендами (llm-svc, vLLM, Ollama, LiteLLM,
OpenAI/Anthropic/OpenRouter) через единый интерфейс. Логика смены модели,
health-проверок и multi-LLM сравнения опирается только на capabilities
конкретного провайдера, а не на захардкоженные знания о llm-svc.

Точка входа:
    from backend.llm_providers import get_registry
    registry = await get_registry()
    provider = registry.get("local-llmsvc")
    await provider.ensure_model_loaded("qwen-coder-30b")
    text = await provider.chat([{"role": "user", "content": "hi"}], model="qwen-coder-30b")
"""

from .base import (
    LLMProvider,
    LLMProviderConfig,
    ModelInfo,
    ProviderCapabilities,
    ProviderHealth,
    ProviderKind,
    join_model_path,
    split_model_path,
)
from .anthropic import AnthropicProvider
from .litellm import LiteLLMProvider
from .llm_svc import LlmSvcProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider
from .openai_native import OpenAIProvider, OpenRouterProvider
from .registry import (
    ProviderRegistry,
    get_registry,
    get_registry_sync_or_none,
    reload_registry,
)
from .secrets import (
    default_env_name_for_provider,
    describe_secret_status,
    mask_api_key,
    read_api_key,
)
from .vllm import VLLMProvider

__all__ = [
    "LLMProvider",
    "LLMProviderConfig",
    "ModelInfo",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderKind",
    "join_model_path",
    "split_model_path",
    "LlmSvcProvider",
    "VLLMProvider",
    "OllamaProvider",
    "LiteLLMProvider",
    "OpenAICompatProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "AnthropicProvider",
    "ProviderRegistry",
    "get_registry",
    "get_registry_sync_or_none",
    "reload_registry",
    "default_env_name_for_provider",
    "describe_secret_status",
    "mask_api_key",
    "read_api_key",
]
