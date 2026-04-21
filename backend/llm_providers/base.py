"""
Базовые типы и протокол LLM-провайдера.

Провайдер — это одна точка подключения к LLM-бэкенду. Каждый провайдер
имеет уникальный id (например ``local-llmsvc`` или ``vllm-qwen-72b``),
собственный ``base_url`` и набор capabilities, по которым оркестратор
решает, как работать со сменой модели и пулом.

Формат ссылки на модель во фронте и настройках: ``<provider_id>/<model_id>``.
Всё после первого ``/`` считается model_id (может содержать слэши, как у
OpenRouter: ``openrouter/anthropic/claude-3.5-sonnet``).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ProviderKind = Literal[
    "llm-svc",
    "openai-compat",
    "vllm",
    "ollama",
    "litellm",
    "openai",
    "anthropic",
    "openrouter",
]


@dataclass(frozen=True)
class ProviderCapabilities:
    """
    Способности провайдера. На основе этих флагов multi-LLM и оркестратор
    принимают решение, нужно ли грузить модель / держать switch-lock.
    """
    #: Может ли эндпоинт переключать загруженную модель по запросу
    #: (``POST /v1/models/load`` в llm-svc). False для vLLM / обычных
    #: OpenAI-совместимых серверов, где модель фиксирована процессом.
    hot_swap: bool = False

    #: Может ли эндпоинт держать несколько моделей активными одновременно
    #: (llm-svc pool, OpenAI/OpenRouter — «виртуально» держат, так как все
    #: модели доступны сразу через поле JSON ``model``).
    multi_loaded: bool = False

    #: Поддерживает ли нативно OpenAI ``/v1/chat/completions``. False для
    #: Anthropic — у них свой REST.
    native_chat_api: bool = True

    #: Поддерживает ли SSE streaming.
    streaming: bool = True

    #: Поддерживает ли ``images`` в user-сообщениях как ``content=[{type:image_url},...]``.
    vision: bool = False


@dataclass(frozen=True)
class ModelInfo:
    """Описание модели, доступной через провайдера."""
    provider_id: str
    model_id: str
    #: Человекочитаемое имя для UI. По умолчанию = model_id.
    display_name: str = ""
    #: Окно контекста (None = неизвестно).
    context_size: Optional[int] = None
    #: Дополнительные поля от провайдера (размер, архитектура, etc.)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> str:
        """Полный path в формате ``<provider_id>/<model_id>`` для фронта."""
        return f"{self.provider_id}/{self.model_id}"


@dataclass(frozen=True)
class ProviderHealth:
    """Статус провайдера на момент проверки."""
    healthy: bool
    #: Модели, реально находящиеся в RAM/GPU в данный момент (для llm-svc
    #: это содержимое пула; для vLLM это ``[static_model]``; для OpenAI —
    #: пустой список, т.к. нет понятия «загруженная модель»).
    loaded_models: List[str] = field(default_factory=list)
    #: Текстовое описание ошибки, если ``healthy == False``.
    error: Optional[str] = None
    #: Сырой ответ эндпоинта, может пригодиться для диагностики.
    raw: Dict[str, Any] = field(default_factory=dict)


#: Дефолтные base_url для external-провайдеров (если пользователь не указал).
_DEFAULT_BASE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com",
    "openrouter": "https://openrouter.ai/api",
    "anthropic": "https://api.anthropic.com",
}


class LLMProviderConfig(BaseModel):
    """
    Конфигурация одного провайдера из секции ``llm_providers:`` в YAML
    или синтезированная автомиграцией из legacy ``microservices.llm.hosts``.
    """
    id: str = Field(..., description="Уникальный идентификатор провайдера")
    kind: ProviderKind = Field(..., description="Тип провайдера")
    #: Для external-провайдеров (openai/openrouter/anthropic) может быть пустым —
    #: подставим дефолт из _DEFAULT_BASE_URLS. Для локальных (llm-svc/vllm/ollama/
    #: litellm/openai-compat) base_url обязателен.
    base_url: str = Field(default="", description="HTTP base URL без завершающего /")
    #: ENV с API-ключом. Чтение строго из os.environ, никакого диска.
    api_key_env: Optional[str] = None
    #: Для провайдеров без свапа (vLLM): имя единственной обслуживаемой модели.
    #: Если задано — провайдер будет считать пул пустым, кроме этой модели.
    static_model: Optional[str] = None
    #: Таймаут HTTP-запроса к этому провайдеру в секундах.
    timeout: float = 120.0
    #: Если False, провайдер регистрируется, но скрыт из /api/models и multi-LLM.
    enabled: bool = True
    #: Произвольные дополнительные поля (для kind-specific настроек).
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"

    def model_post_init(self, __context: Any) -> None:  # type: ignore[override]
        # Подставляем дефолтный base_url для external-провайдеров.
        if not (self.base_url or "").strip():
            default = _DEFAULT_BASE_URLS.get(self.kind)
            if default:
                object.__setattr__(self, "base_url", default)
        # Валидация: локальные провайдеры должны иметь base_url.
        if not (self.base_url or "").strip():
            raise ValueError(
                f"LLMProviderConfig(id={self.id!r}, kind={self.kind!r}): "
                "base_url обязателен для этого kind."
            )


StreamCallback = Callable[[str, str], bool]
"""
Коллбэк потоковой генерации: ``cb(chunk, accumulated) -> continue``.
Возврат ``False`` прерывает стрим (используется кнопкой «стоп» на фронте).
"""


class LLMProvider(abc.ABC):
    """
    Абстрактный LLM-провайдер. Конкретные реализации — ``LlmSvcProvider``,
    ``VLLMProvider``, ``OllamaProvider`` и т.д.
    """

    def __init__(self, config: LLMProviderConfig) -> None:
        self._config = config

    # ---- public props -----------------------------------------------------

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def kind(self) -> ProviderKind:
        return self._config.kind

    @property
    def base_url(self) -> str:
        return self._config.base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    @abc.abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @property
    def config(self) -> LLMProviderConfig:
        return self._config

    # ---- credentials ------------------------------------------------------

    def get_api_key(self) -> Optional[str]:
        """Читает API-ключ строго из ENV. Имя env берётся из конфига или
        выводится из kind/id для external-провайдеров (см. secrets.py)."""
        from .secrets import read_api_key
        return read_api_key(
            api_key_env=self._config.api_key_env,
            provider_id=self._config.id,
            provider_kind=self._config.kind,
        )

    def has_api_key(self) -> bool:
        return bool(self.get_api_key())

    def secret_status(self) -> Dict[str, Any]:
        """Диагностика для UI: ожидаемая ENV, выставлена ли, preview."""
        from .secrets import describe_secret_status
        return describe_secret_status(
            api_key_env=self._config.api_key_env,
            provider_id=self._config.id,
            provider_kind=self._config.kind,
        )

    # ---- lifecycle --------------------------------------------------------

    async def initialize(self) -> None:
        """
        Опциональная инициализация (например, синхронизация имени загруженной
        модели у llm-svc). По умолчанию — no-op.
        """
        return None

    async def close(self) -> None:
        """Закрытие HTTP-клиентов и т.п. По умолчанию — no-op."""
        return None

    # ---- public API -------------------------------------------------------

    @abc.abstractmethod
    async def health(self) -> ProviderHealth:
        """Проверка доступности эндпоинта."""

    @abc.abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """Список моделей, доступных через этого провайдера."""

    @abc.abstractmethod
    async def ensure_model_loaded(self, model_id: str) -> bool:
        """
        Гарантирует, что ``model_id`` готова к inference.

        - llm-svc: POST /v1/models/load при необходимости;
        - vLLM/Ollama/OpenAI: проверка наличия в ``list_models``/``static_model``
          без сетевых побочных эффектов.
        """

    @abc.abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Синхронная (non-streaming) генерация. Возвращает текст ответа."""

    @abc.abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        callback: StreamCallback,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Потоковая генерация. ``callback(chunk, accumulated) -> bool``
        вызывается на каждом токене; возврат ``False`` = прервать поток.
        Возвращает накопленный текст.
        """

    # ---- helpers ----------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        """
        Описание провайдера для ``GET /api/llm-providers`` (без секретов).
        """
        return {
            "id": self.id,
            "kind": self.kind,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "static_model": self._config.static_model,
            **self.secret_status(),
            "capabilities": {
                "hot_swap": self.capabilities.hot_swap,
                "multi_loaded": self.capabilities.multi_loaded,
                "native_chat_api": self.capabilities.native_chat_api,
                "streaming": self.capabilities.streaming,
                "vision": self.capabilities.vision,
            },
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} base_url={self.base_url!r}>"


# =============================================================================
# УТИЛИТЫ ДЛЯ ПАРСИНГА PATH
# =============================================================================


def split_model_path(path: str) -> "tuple[Optional[str], str]":
    """
    Разбирает строку path в пару ``(provider_id, model_id)``.

    Поддерживает:

    - новый формат ``<provider_id>/<model_id>`` (всё после первого ``/`` =
      model_id, слэши внутри model_id разрешены: ``openrouter/anthropic/claude``);
    - legacy ``llm-svc://host_id/model_id`` → ``(host_id, model_id)``;
    - legacy ``llm-svc://model_id`` → ``(None, model_id)`` — вызывающая сторона
      должна подставить default-провайдер вида ``llm-svc``.
    - плоское ``model_id`` без ``/`` → ``(None, model_id)``.

    Если path пуст — возвращает ``(None, "")``.
    """
    if not path:
        return None, ""
    s = str(path).strip()
    if not s:
        return None, ""

    # Типографские опечатки из старого кода
    low = s.lower()
    if low.startswith("1lm-svc://") or low.startswith("11m-svc://"):
        s = "llm-svc://" + s[10:]
        low = s.lower()

    # Legacy llm-svc://...
    if low.startswith("llm-svc://"):
        rest = s[len("llm-svc://"):].strip().lstrip("/")
        if not rest:
            return None, ""
        if "/" in rest:
            head, tail = rest.split("/", 1)
            return head or None, tail
        return None, rest

    # Новый формат: provider_id/model_id
    if "/" in s:
        head, tail = s.split("/", 1)
        if head and tail:
            return head, tail

    # Плоский model_id
    return None, s


def join_model_path(provider_id: str, model_id: str) -> str:
    """Собирает path из ``provider_id`` и ``model_id`` для фронта."""
    pid = (provider_id or "").strip().strip("/")
    mid = (model_id or "").strip()
    if not pid or not mid:
        return mid or ""
    return f"{pid}/{mid}"
