"""
Централизованная настройка логирования backend.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional
from urllib.parse import parse_qsl, urlencode

from backend.settings.logging.matrix import DEFAULT_LEVEL, LEVEL_BY_NAME
from backend.utils.safe_paths import resolve_log_file_path, sanitize_log_value

BACKEND_LOGGER_NAME = "backend"
LOG_FORMAT = (
    "%(asctime)s,%(msecs)03d: [%(thread)d] [astra-chat-backend]"
    "[%(threadName)s][%(levelname)s][%(name)s:%(funcName)s(%(lineno)d)]: %(message)s"
)
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

_NOISY_LOGGERS = (
    "pymongo",
    "pymongo.topology",
    "pymongo.connection",
    "pymongo.serverSelection",
)

_UVICORN_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
)

_NOISY_DEBUG_LOGS_HIDE_ENV = "NOISY_DEBUG_LOGS_HIDE"
_NOISY_INFO_LOGGERS = ("uvicorn.access", "uvicorn.error", "httpx", "httpcore")

_configured = False


class NoisyInfoToDebugFilter(logging.Filter):
    """Перевод шумных INFO логов в DEBUG с управлением через env-флаг."""

    def filter(self, record: logging.LogRecord) -> bool:
        name = str(record.name or "")
        is_noisy = any(name == logger_name or name.startswith(f"{logger_name}.") for logger_name in _NOISY_INFO_LOGGERS)
        if not is_noisy:
            return True
        if record.levelno != logging.INFO:
            return True
        if _hide_noisy_debug_logs():
            return False
        record.levelno = logging.DEBUG
        record.levelname = "DEBUG"
        return True


class UvicornAccessRedactionFilter(logging.Filter):
    """Маскирует чувствительные query-параметры в uvicorn.access."""

    _REQUEST_LINE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(\S+)\s+(HTTP/\d(?:\.\d+)?)")
    _JWTISH_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?$")
    _SENSITIVE_QUERY_KEYS = {
        "state",
        "code",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "assertion",
    }

    @staticmethod
    def _redact_query(value: str) -> str:
        if "?" not in value:
            return value
        path, _, query = value.partition("?")
        if not query:
            return value
        try:
            pairs = parse_qsl(query, keep_blank_values=True)
            redacted_pairs = []
            for key, raw_val in pairs:
                key_l = str(key).strip().lower()
                if key_l in UvicornAccessRedactionFilter._SENSITIVE_QUERY_KEYS:
                    redacted_pairs.append((key, "<redacted>"))
                elif UvicornAccessRedactionFilter._JWTISH_RE.match(raw_val or ""):
                    redacted_pairs.append((key, "<redacted>"))
                else:
                    redacted_pairs.append((key, raw_val))
            return f"{path}?{urlencode(redacted_pairs)}"
        except Exception:
            return f"{path}?<redacted>"

    def _sanitize_text(self, text: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            method = match.group(1)
            target = match.group(2)
            http_version = match.group(3)
            return f"{method} {self._redact_query(target)} {http_version}"

        return self._REQUEST_LINE_RE.sub(_replace, text)

    def filter(self, record: logging.LogRecord) -> bool:
        if str(record.name or "") != "uvicorn.access":
            return True
        try:
            if isinstance(record.args, tuple):
                redacted_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        redacted_args.append(self._sanitize_text(self._redact_query(arg)))
                    else:
                        redacted_args.append(arg)
                record.args = tuple(redacted_args)
            elif isinstance(record.msg, str):
                record.msg = self._sanitize_text(self._redact_query(record.msg))
        except Exception:
            return True
        return True


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _hide_noisy_debug_logs() -> bool:
    """Скрывает шумные auth/http/access-логи через env-флаг."""
    return _env_bool(_NOISY_DEBUG_LOGS_HIDE_ENV, True)


def _apply_debug_gate_to_level(level: int) -> int:
    """Глобально скрыть DEBUG при NOISY_DEBUG_LOGS_HIDE=true."""
    if _hide_noisy_debug_logs() and level <= logging.DEBUG:
        return logging.INFO
    return level


def _apply_debug_gate_to_level_name(level_name: str) -> str:
    normalized = str(level_name or "INFO").upper()
    if _hide_noisy_debug_logs() and normalized == "DEBUG":
        return "INFO"
    return normalized


def _resolve_level() -> int:
    level_name = (
        os.getenv("APP_LOG_LEVEL") or os.getenv("astrachat_LOG_LEVEL") or os.getenv("ASTRACHAT_LOG_LEVEL") or "INFO"
    ).upper()
    return LEVEL_BY_NAME.get(level_name, DEFAULT_LEVEL)


def _ensure_utf8_stream(stream) -> None:
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def reconfigure_backend_handler_streams_utf8() -> None:
    """Переключает stdout/stderr handlers backend-логгера на UTF-8 (Windows)."""
    for handler in logging.getLogger(BACKEND_LOGGER_NAME).handlers:
        if hasattr(handler, "stream"):
            _ensure_utf8_stream(handler.stream)


def _attach_backend_handler(
    logger: logging.Logger,
    formatter: logging.Formatter,
    level: int,
    *,
    clear_handlers: bool = False,
    add_noisy_filter: bool = False,
    add_uvicorn_access_redaction_filter: bool = False,
) -> None:
    if clear_handlers:
        logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        if add_noisy_filter:
            handler.addFilter(NoisyInfoToDebugFilter())
        if add_uvicorn_access_redaction_filter:
            handler.addFilter(UvicornAccessRedactionFilter())
        _ensure_utf8_stream(handler.stream)
        logger.addHandler(handler)


def configure_uvicorn_logging(*, force: bool = False) -> None:
    """Переводит uvicorn / uvicorn.access на формат backend."""
    level = _apply_debug_gate_to_level(_resolve_level())
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)
    for name in _UVICORN_LOGGERS:
        _attach_backend_handler(
            logging.getLogger(name),
            formatter,
            level,
            clear_handlers=force,
            add_noisy_filter=True,
            add_uvicorn_access_redaction_filter=name == "uvicorn.access",
        )


def get_uvicorn_log_config() -> dict:
    """dictConfig для uvicorn.run(log_config=...)."""
    level_name = (
        os.getenv("APP_LOG_LEVEL") or os.getenv("astrachat_LOG_LEVEL") or os.getenv("ASTRACHAT_LOG_LEVEL") or "INFO"
    ).upper()
    level_name = _apply_debug_gate_to_level_name(level_name)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "backend": {
                "format": LOG_FORMAT,
                "datefmt": LOG_DATEFMT,
            },
        },
        "filters": {
            "noisy_info_to_debug": {
                "()": "backend.settings.logging.setup.NoisyInfoToDebugFilter",
            },
            "uvicorn_access_redaction": {
                "()": "backend.settings.logging.setup.UvicornAccessRedactionFilter",
            },
        },
        "handlers": {
            "backend_stdout": {
                "class": "logging.StreamHandler",
                "formatter": "backend",
                "stream": "ext://sys.stdout",
                "filters": ["noisy_info_to_debug", "uvicorn_access_redaction"],
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["backend_stdout"], "level": level_name, "propagate": False},
            "uvicorn.error": {"handlers": ["backend_stdout"], "level": level_name, "propagate": False},
            "uvicorn.access": {"handlers": ["backend_stdout"], "level": level_name, "propagate": False},
            BACKEND_LOGGER_NAME: {"handlers": ["backend_stdout"], "level": level_name, "propagate": False},
        },
        "root": {"handlers": ["backend_stdout"], "level": level_name},
    }


def configure_logging(*, force: bool = False) -> None:
    """Инициализирует логирование backend (stdout + опционально файл)."""
    global _configured
    if _configured and not force:
        return

    level = _apply_debug_gate_to_level(_resolve_level())
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT)

    backend_logger = logging.getLogger(BACKEND_LOGGER_NAME)
    backend_logger.setLevel(level)
    backend_logger.propagate = False

    if force:
        backend_logger.handlers.clear()

    if not backend_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        _ensure_utf8_stream(console_handler.stream)
        backend_logger.addHandler(console_handler)

        raw_log_file = os.getenv("BACKEND_LOG_FILE")
        safe_log_file = resolve_log_file_path(raw_log_file)
        if raw_log_file and safe_log_file is None:
            backend_logger.warning(
                "BACKEND_LOG_FILE недоступен или отклонен: %s — используется только stdout",
                sanitize_log_value(raw_log_file),
            )
        if safe_log_file is not None:
            try:
                file_handler = RotatingFileHandler(
                    str(safe_log_file),
                    maxBytes=int(os.getenv("BACKEND_LOG_MAX_SIZE", "10485760")),
                    backupCount=int(os.getenv("BACKEND_LOG_BACKUP_COUNT", "5")),
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(logging.DEBUG)
                backend_logger.addHandler(file_handler)
            except OSError as exc:
                backend_logger.warning(
                    "Не удалось открыть BACKEND_LOG_FILE (%s): %s — используется только stdout",
                    sanitize_log_value(safe_log_file),
                    exc,
                )

    configure_uvicorn_logging(force=force)

    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    for handler in logging.root.handlers:
        if hasattr(handler, "stream"):
            _ensure_utf8_stream(handler.stream)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Возвращает логгер в иерархии backend.*.

    Использование: logger = get_logger(__name__)
    """
    if not _configured:
        configure_logging()

    if not name:
        return logging.getLogger(BACKEND_LOGGER_NAME)

    normalized = name.strip()
    if normalized in ("Backend", "backend"):
        normalized = BACKEND_LOGGER_NAME
    elif not normalized.startswith(f"{BACKEND_LOGGER_NAME}."):
        if normalized.startswith("backend"):
            pass
        else:
            normalized = f"{BACKEND_LOGGER_NAME}.{normalized.lstrip('.')}"

    return logging.getLogger(normalized)
