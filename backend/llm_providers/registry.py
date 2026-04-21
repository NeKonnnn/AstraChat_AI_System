"""
Реестр LLM-провайдеров.

Читает конфиг из ``settings.llm_providers`` (новая секция) и/или
производит автомиграцию из legacy ``settings.llm_service.hosts``
(каждый host превращается в провайдера kind="llm-svc").

Использование::

    registry = await get_registry()
    provider = registry.get("local-llmsvc")
    provider_for_path = registry.resolve("local-llmsvc/qwen-coder-30b")  # -> (provider, "qwen-coder-30b")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from .anthropic import AnthropicProvider
from .base import LLMProvider, LLMProviderConfig, ModelInfo, split_model_path
from .litellm import LiteLLMProvider
from .llm_svc import LlmSvcProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider
from .openai_native import OpenAIProvider, OpenRouterProvider
from .vllm import VLLMProvider

logger = logging.getLogger(__name__)


# =============================================================================
# Factory: kind -> class
# =============================================================================


def _build_provider(config: LLMProviderConfig) -> LLMProvider:
    """Инстанцирует провайдера по ``kind``."""
    kind = config.kind
    if kind == "llm-svc":
        return LlmSvcProvider(config)
    if kind == "vllm":
        return VLLMProvider(config)
    if kind == "ollama":
        return OllamaProvider(config)
    if kind == "litellm":
        return LiteLLMProvider(config)
    if kind == "openai":
        return OpenAIProvider(config)
    if kind == "openrouter":
        return OpenRouterProvider(config)
    if kind == "anthropic":
        return AnthropicProvider(config)
    if kind == "openai-compat":
        return OpenAICompatProvider(config)
    logger.warning("kind=%r неизвестен, используется OpenAICompatProvider", kind)
    return OpenAICompatProvider(config)


# =============================================================================
# Registry
# =============================================================================


class ProviderRegistry:
    """Контейнер всех провайдеров с методами lookup/resolve."""

    def __init__(
        self,
        providers: Dict[str, LLMProvider],
        default_provider_id: str,
    ) -> None:
        self._providers = providers
        self._default_id = default_provider_id

    # ---- accessors --------------------------------------------------------

    @property
    def default_id(self) -> str:
        return self._default_id

    def get(self, provider_id: Optional[str]) -> LLMProvider:
        """
        Возвращает провайдера по id. Если id не указан или не найден —
        возвращает default-провайдер.
        """
        pid = (provider_id or "").strip()
        if pid and pid in self._providers:
            return self._providers[pid]
        if not pid:
            return self._providers[self._default_id]
        logger.warning(
            "Провайдер %r не найден, используется default %r", pid, self._default_id,
        )
        return self._providers[self._default_id]

    def contains(self, provider_id: Optional[str]) -> bool:
        pid = (provider_id or "").strip()
        return bool(pid) and pid in self._providers

    def all(self, *, include_disabled: bool = False) -> List[LLMProvider]:
        if include_disabled:
            return list(self._providers.values())
        return [p for p in self._providers.values() if p.enabled]

    def ids(self, *, include_disabled: bool = False) -> List[str]:
        return [p.id for p in self.all(include_disabled=include_disabled)]

    # ---- resolving --------------------------------------------------------

    def resolve(self, path: Optional[str]) -> Tuple[LLMProvider, str]:
        """
        ``<provider_id>/<model_id>`` → (provider, model_id).

        Legacy ``llm-svc://host/model`` тоже поддерживаем — ``host`` считаем
        id провайдера (auto-migration оставляет те же id). ``llm-svc://model``
        без host → default-провайдер.

        Плоский ``model_id`` без ``/`` → default-провайдер.

        Пустой path → (default_provider, "") — вызывающая сторона сама решит,
        что делать с пустой моделью (обычно: использовать default-модель
        провайдера).
        """
        head, tail = split_model_path(path or "")
        if head and self.contains(head):
            return self._providers[head], tail
        # Нет head, или head не существует → default-провайдер.
        # При этом tail уже содержит «хвост» без провайдера.
        if head and not self.contains(head):
            logger.warning(
                "resolve(%r): провайдер %r не зарегистрирован, используется default %r",
                path, head, self._default_id,
            )
            # Склеиваем head обратно в model_id — это может быть «OpenRouter-style»
            # путь вида ``openrouter/anthropic/claude`` у default-провайдера.
            combined = f"{head}/{tail}" if tail else head
            return self._providers[self._default_id], combined
        return self._providers[self._default_id], tail

    # ---- lifecycle --------------------------------------------------------

    async def initialize(self) -> None:
        """Инициализация всех провайдеров (health probe, sync model_name и т.д.)."""
        for p in self._providers.values():
            try:
                await p.initialize()
            except Exception as e:
                logger.error("Provider %s initialize() error: %s", p.id, e)

    async def close(self) -> None:
        for p in self._providers.values():
            try:
                await p.close()
            except Exception as e:
                logger.warning("Provider %s close() error: %s", p.id, e)

    # ---- aggregated views -------------------------------------------------

    async def list_all_models(self) -> List[ModelInfo]:
        """Объединённый список моделей всех enabled-провайдеров."""
        results: List[ModelInfo] = []
        for p in self.all():
            try:
                models = await p.list_models()
                results.extend(models)
            except Exception as e:
                logger.error("list_models(%s) error: %s", p.id, e)
        return results


# =============================================================================
# Загрузка конфигурации + auto-migration
# =============================================================================


def _parse_configs_from_settings(settings: Any) -> Tuple[List[LLMProviderConfig], Optional[str]]:
    """
    Достаёт список конфигов провайдеров из объекта Settings.

    Приоритет:
      1. ``settings.llm_providers`` — новая секция, как есть.
      2. ``settings.llm_service.hosts`` — автомиграция: каждый host становится
         llm-svc-провайдером с id = host.id, base_url = host.base_url.
      3. Единственный URL ``settings.llm_service.base_url`` → один llm-svc
         с id="local-llmsvc".

    Возвращает (configs, default_provider_id_or_None).
    """
    configs: List[LLMProviderConfig] = []
    default_id: Optional[str] = None

    # 1. Новая секция llm_providers (будет добавлена в Settings на этом шаге).
    new_section = getattr(settings, "llm_providers", None)
    if new_section:
        items = list(new_section) if isinstance(new_section, list) else []
        for item in items:
            try:
                if isinstance(item, LLMProviderConfig):
                    configs.append(item)
                elif isinstance(item, dict):
                    configs.append(LLMProviderConfig(**item))
                elif hasattr(item, "model_dump"):
                    configs.append(LLMProviderConfig(**item.model_dump()))
            except Exception as e:
                logger.error("Некорректная запись llm_providers: %s (%s)", item, e)
        default_id = getattr(settings, "default_llm_provider", None) or None

    # 2. Автомиграция из llm_service.hosts.
    if not configs:
        llm_service = getattr(settings, "llm_service", None)
        if llm_service is not None:
            hosts = getattr(llm_service, "hosts", None) or []
            default_host_id = (getattr(llm_service, "default_host_id", None) or "").strip() or None
            timeout = float(getattr(llm_service, "timeout", 120.0) or 120.0)
            for h in hosts:
                hid, burl = _host_entry_to_tuple(h)
                if not hid or not burl:
                    continue
                try:
                    configs.append(
                        LLMProviderConfig(
                            id=hid, kind="llm-svc", base_url=burl,
                            timeout=timeout, enabled=True,
                        )
                    )
                except Exception as e:
                    logger.error("Автомиграция host=%r base_url=%r: %s", hid, burl, e)
            if default_host_id and default_host_id in {c.id for c in configs}:
                default_id = default_host_id
            elif configs:
                default_id = configs[0].id

            # 3. Fallback на одиночный base_url.
            if not configs:
                burl = (getattr(llm_service, "base_url", "") or "").strip()
                if burl:
                    try:
                        configs.append(
                            LLMProviderConfig(
                                id="local-llmsvc", kind="llm-svc", base_url=burl,
                                timeout=timeout, enabled=True,
                            )
                        )
                        default_id = "local-llmsvc"
                    except Exception as e:
                        logger.error("Автомиграция single base_url=%r: %s", burl, e)

    # Уникальность id
    seen: Dict[str, LLMProviderConfig] = {}
    for c in configs:
        if c.id in seen:
            logger.warning("Дубликат provider id=%r, оставляем первый", c.id)
            continue
        seen[c.id] = c
    configs = list(seen.values())

    if configs and (not default_id or default_id not in seen):
        default_id = configs[0].id

    return configs, default_id


def _host_entry_to_tuple(entry: Any) -> Tuple[Optional[str], Optional[str]]:
    if entry is None:
        return None, None
    if hasattr(entry, "id") and hasattr(entry, "base_url"):
        return (getattr(entry, "id", None) or None), (getattr(entry, "base_url", None) or None)
    if isinstance(entry, dict):
        return entry.get("id"), entry.get("base_url")
    return None, None


# =============================================================================
# Глобальный singleton (для совместимости со старым ``get_llm_service()``)
# =============================================================================


_registry: Optional[ProviderRegistry] = None
_registry_lock: asyncio.Lock = asyncio.Lock()


async def get_registry() -> ProviderRegistry:
    """
    Ленивая инициализация реестра. Повторные вызовы возвращают тот же
    экземпляр. Thread-safe в пределах одного event loop.
    """
    global _registry
    if _registry is not None:
        return _registry
    async with _registry_lock:
        if _registry is not None:
            return _registry
        _registry = await _build_from_settings()
    return _registry


async def _build_from_settings() -> ProviderRegistry:
    # Импорт тут, чтобы избежать циклов при старте
    try:
        from backend.settings import get_settings  # type: ignore
    except Exception:
        from settings import get_settings  # type: ignore
    settings = get_settings()
    configs, default_id = _parse_configs_from_settings(settings)
    if not configs:
        raise RuntimeError(
            "Нет настроенных LLM-провайдеров. Заполните секцию llm_providers: "
            "в backend/config/config.yml или microservices.llm.hosts."
        )
    providers: Dict[str, LLMProvider] = {}
    for c in configs:
        try:
            providers[c.id] = _build_provider(c)
            logger.info(
                "Provider registered: id=%s kind=%s base_url=%s enabled=%s",
                c.id, c.kind, c.base_url, c.enabled,
            )
        except Exception as e:
            logger.error("Provider %s build error: %s", c.id, e)
    if not providers:
        raise RuntimeError("Ни один провайдер не инициализирован.")
    if not default_id or default_id not in providers:
        default_id = next(iter(providers.keys()))
    registry = ProviderRegistry(providers, default_id)
    await registry.initialize()
    logger.info(
        "ProviderRegistry готов: %d провайдеров, default=%s", len(providers), default_id,
    )
    return registry


def get_registry_sync_or_none() -> Optional[ProviderRegistry]:
    """Без инициализации: если реестра нет — возвращает None (для diag-эндпоинтов)."""
    return _registry


async def reload_registry() -> ProviderRegistry:
    """Переинициализация (для hot-reload конфига, сейчас не используется)."""
    global _registry
    async with _registry_lock:
        old = _registry
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass
        _registry = None
    return await get_registry()
