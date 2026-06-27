"""
Единая система логирования backend.

Матрица уровней — см. backend.settings.logging.matrix.LOG_MATRIX.
"""

from backend.settings.logging.errors import (
    guarded,
    logged_suppress,
    run_guarded,
    run_guarded_async,
)
from backend.settings.logging.matrix import LEVEL_BY_NAME, LOG_MATRIX
from backend.settings.logging.setup import (
    BACKEND_LOGGER_NAME,
    LOG_DATEFMT,
    LOG_FORMAT,
    configure_logging,
    configure_uvicorn_logging,
    get_logger,
    get_uvicorn_log_config,
    reconfigure_backend_handler_streams_utf8,
)

__all__ = [
    "BACKEND_LOGGER_NAME",
    "LOG_DATEFMT",
    "LOG_FORMAT",
    "LOG_MATRIX",
    "LEVEL_BY_NAME",
    "configure_logging",
    "configure_uvicorn_logging",
    "get_logger",
    "get_uvicorn_log_config",
    "reconfigure_backend_handler_streams_utf8",
    "guarded",
    "logged_suppress",
    "run_guarded",
    "run_guarded_async",
]
