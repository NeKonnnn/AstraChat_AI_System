"""
Единая система логирования SVC-RAG (порт матрицы логов backend)
Матрица уровней — см. app.core.logging.matrix.LOG_MATRIX
Единый формат и uvicorn-конфиг — см. app.core.logging.setup
Пример:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Операция завершена")
"""

from app.core.logging.matrix import LEVEL_BY_NAME, LOG_MATRIX
from app.core.logging.errors import (
    guarded,
    logged_suppress,
    run_guarded,
    run_guarded_async,
)
from app.core.logging.setup import (
    APP_LOGGER_NAME,
    LOG_DATEFMT,
    LOG_FORMAT,
    configure_logging,
    get_logger,
    get_uvicorn_log_config,
)
from app.core.logging.llm_trace import (
    log_llm_config,
    log_llm_failure,
    log_llm_request,
    log_llm_response,
    new_request_id,
)

__all__ = [
    "APP_LOGGER_NAME",
    "LOG_DATEFMT",
    "LOG_FORMAT",
    "LOG_MATRIX",
    "LEVEL_BY_NAME",
    "configure_logging",
    "get_logger",
    "get_uvicorn_log_config",
    "guarded",
    "logged_suppress",
    "run_guarded",
    "run_guarded_async",
    "log_llm_config",
    "log_llm_failure",
    "log_llm_request",
    "log_llm_response",
    "new_request_id",
]
