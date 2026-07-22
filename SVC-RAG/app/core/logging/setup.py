"""
Централизованная настройка логирования SVC-RAG
Порт матрицы логов backend (backend.settings.logging) под SVC-RAG
"""

from __future__ import annotations
import logging
import logging.config
import os
import sys
from typing import Optional
from app.core.logging.matrix import DEFAULT_LEVEL, LEVEL_BY_NAME

# Корень иерархии логгеров сервиса (RAG-модули: logging.getLogger(__name__) -> "app.*").
APP_LOGGER_NAME = "app"
LOG_FORMAT = (
    "%(asctime)s,%(msecs)03d: [%(thread)d] [astra-chat-rag]"
    "[%(threadName)s][%(levelname)s][%(name)s:%(funcName)s(%(lineno)d)]: %(message)s"
)
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
_configured = False


def _level_name() -> str:
    return (
        os.getenv("APP_LOG_LEVEL") or os.getenv("SVC_RAG_LOG_LEVEL") or os.getenv("RAG_LOG_LEVEL") or "INFO"
    ).upper()


def _resolve_level() -> int:
    return LEVEL_BY_NAME.get(_level_name(), DEFAULT_LEVEL)


def get_uvicorn_log_config() -> dict:
    """
    dictConfig для единого формата логов.
    Тот же по смыслу конфиг, что backend отдаёт в uvicorn.run(log_config=...),
    но в RAG применяется через logging.config.dictConfig(...) при импорте main.py
    Покрывает: uvicorn / uvicorn.error / uvicorn.access (свои хендлеры),
    "app" (наши логгеры) и root (httpx и всё прочее, что пропагейтит в корень)
    """
    level_name = _level_name()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "svc_rag": {
                "format": LOG_FORMAT,
                "datefmt": LOG_DATEFMT,
            },
        },
        "handlers": {
            "svc_rag_stdout": {
                "class": "logging.StreamHandler",
                "formatter": "svc_rag",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["svc_rag_stdout"],
                "level": level_name,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["svc_rag_stdout"],
                "level": level_name,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["svc_rag_stdout"],
                "level": level_name,
                "propagate": False,
            },
            APP_LOGGER_NAME: {
                "handlers": ["svc_rag_stdout"],
                "level": level_name,
                "propagate": False,
            },
        },
        "root": {"handlers": ["svc_rag_stdout"], "level": level_name},
    }


def _ensure_stdout_utf8() -> None:
    """stdout → UTF-8, чтобы кириллица и символы [LLM→]/[LLM✗] не падали с UnicodeEncodeError"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def configure_logging(*, force: bool = False) -> None:
    """
    Инициализирует логирование SVC-RAG в едином формате.
    Идемпотентно: повторные вызовы (в т.ч. ленивые из get_logger) — no-op, пока не force.
    """
    global _configured
    if _configured and not force:
        return
    _ensure_stdout_utf8()
    logging.config.dictConfig(get_uvicorn_log_config())
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Возвращает логгер в иерархии app.*.
    Использование: logger = get_logger(__name__)
    """
    if not _configured:
        configure_logging()
    if not name:
        return logging.getLogger(APP_LOGGER_NAME)
    normalized = name.strip()
    if normalized in ("App", "app"):
        normalized = APP_LOGGER_NAME
    elif not normalized.startswith(f"{APP_LOGGER_NAME}."):
        normalized = f"{APP_LOGGER_NAME}.{normalized.lstrip('.')}"
    return logging.getLogger(normalized)
