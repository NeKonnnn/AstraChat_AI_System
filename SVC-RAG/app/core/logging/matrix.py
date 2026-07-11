"""
Матрица уровней логирования SVC-RAG.
Уровень     | Назначение
------------|----------------------------------------------------------
DEBUG       | Шаг внутреннего алгоритма (детальная трассировка)
INFO        | Завершение значимой операции
WARNING     | Ожидаемый отказ (сервис продолжает работу)
ERROR       | Операция провалилась (требует внимания)
CRITICAL    | Без компонента «X» сервис не стартует
"""
from __future__ import annotations
import logging
from typing import Dict

LOG_MATRIX: Dict[str, str] = {
    "DEBUG": "Шаг внутреннего алгоритма",
    "INFO": "Завершение значимой операции",
    "WARNING": "Ожидаемый отказ",
    "ERROR": "Операция провалилась",
    "CRITICAL": "Без компонента сервис не стартует",
}
DEFAULT_LEVEL = logging.INFO
LEVEL_BY_NAME = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}