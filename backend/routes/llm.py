"""
Статус подключения к LLM-провайдерам — для UI без знания URL на фронте.
После перехода на ProviderRegistry эндпоинт показывает агрегированный статус
ВСЕХ зарегистрированных провайдеров (llm-svc / vLLM / Ollama / OpenAI / ...).
"""

import logging

from fastapi import APIRouter

from backend.llm_providers import get_registry

router = APIRouter(prefix="/api/llm", tags=["llm"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def llm_connection_status():
    """
    Состояние всех настроенных LLM-провайдеров. Фронт использует только этот
    эндпоинт (и ``/api/models``), не URL конкретного сервиса.

    Формат ответа (важно для фронта):

    ::

        {
          "connected": bool,           # хотя бы один провайдер healthy
          "default_provider_id": str,  # id провайдера по умолчанию
          "providers": [
            {
              "id": str,
              "kind": "llm-svc" | "vllm" | "ollama" | ...,
              "base_url": str,
              "healthy": bool,
              "loaded_models": [str, ...],
              "capabilities": {...},
              "api_key_set": bool,
              "error": str | None,
            },
            ...
          ],

          # LEGACY-поля — для старых фронтов, выпиливаются в шаге 6:
          "use_llm_svc": bool,
          "hosts": [{"id": str, "healthy": bool, "error": str|None}, ...],
          "default_host_id": str,
          "message": str | None,
        }
    """
    try:
        registry = await get_registry()
    except Exception as e:
        logger.exception("llm status: registry error: %s", e)
        return {
            "connected": False,
            "default_provider_id": None,
            "providers": [],
            # legacy
            "use_llm_svc": False,
            "hosts": [],
            "default_host_id": None,
            "message": f"Ошибка инициализации LLM-провайдеров: {e}",
        }

    providers_out = []
    hosts_out = []  # legacy
    any_healthy = False
    has_llmsvc = False
    for provider in registry.all():
        try:
            health = await provider.health()
        except Exception as e:
            logger.warning("health(%s) error: %s", provider.id, e)
            health_healthy, err, loaded = False, str(e), []
        else:
            health_healthy = health.healthy
            err = health.error
            loaded = list(health.loaded_models)
        if health_healthy:
            any_healthy = True
        if provider.kind == "llm-svc":
            has_llmsvc = True
        providers_out.append({
            "id": provider.id,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "healthy": health_healthy,
            "loaded_models": loaded,
            "capabilities": {
                "hot_swap": provider.capabilities.hot_swap,
                "multi_loaded": provider.capabilities.multi_loaded,
                "streaming": provider.capabilities.streaming,
                "vision": provider.capabilities.vision,
            },
            **provider.secret_status(),
            "error": None if health_healthy else (err or "unhealthy"),
        })
        hosts_out.append({
            "id": provider.id,
            "healthy": health_healthy,
            "error": None if health_healthy else (err or "unhealthy"),
        })

    message = None
    if not any_healthy:
        message = (
            "Подключиться к LLM не удалось. Проверьте, что сервис(ы) моделей "
            "запущены и настройки провайдеров (backend/config/config.yml / "
            "ENV-переменные для API-ключей) указаны верно."
        )

    return {
        "connected": any_healthy,
        "default_provider_id": registry.default_id,
        "providers": providers_out,
        # legacy-поля (старые фронты)
        "use_llm_svc": has_llmsvc,
        "default_host_id": registry.default_id,
        "hosts": hosts_out,
        "message": message,
    }
