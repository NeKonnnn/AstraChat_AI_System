"""Контекст инструментов (ContextVar + глобальный fallback) без зависимостей от агентов."""

import threading
from contextvars import ContextVar
from typing import Any, Dict, Optional

from backend.settings.logging import get_logger

logger = get_logger(__name__)

_tool_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar("tool_context")
_global_tool_context: Dict[str, Any] = {}
_global_context_lock = threading.Lock()


def set_tool_context(context: Dict[str, Any]) -> None:
    """Установка контекста для инструментов (вызывается из orchestrator)."""
    _tool_context.set(context)
    global _global_tool_context
    with _global_context_lock:
        _global_tool_context = context.copy()
    logger.info(
        "[set_tool_context] Установлен контекст (двойной): streaming=%s, has_callback=%s",
        context.get("streaming", False),
        context.get("stream_callback") is not None,
    )


def get_tool_context() -> Dict[str, Any]:
    """Получение контекста для инструментов."""
    result = _tool_context.get(None)
    if result is None:
        with _global_context_lock:
            result = _global_tool_context.copy() if _global_tool_context else {}
        logger.info(
            "[get_tool_context] Получен из глобальной переменной: streaming=%s",
            result.get("streaming", False),
        )
    else:
        logger.info(
            "[get_tool_context] Получен из ContextVar: streaming=%s",
            result.get("streaming", False),
        )
    return result
