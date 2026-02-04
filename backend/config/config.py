"""
Конфигурация путей к локальным моделям WhisperX и диаризации для backend
"""

import os
from pathlib import Path

# Получаем абсолютный путь к корневой директории проекта (на уровень выше backend)
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Пути к папкам с моделями (относительно корня проекта)
WHISPERX_MODELS_DIR = str(PROJECT_ROOT / "whisperx_models")
DIARIZE_MODELS_DIR = str(PROJECT_ROOT / "diarize_models")

# Пути к конкретным моделям
WHISPERX_BASE_MODEL = "base"  # WhisperX сам найдет в папке
WHISPERX_SMALL_MODEL = "small"
DIARIZE_MODEL = "pyannote/speaker-diarization-3.1"

# Пути для других модулей
MODEL_PATH = str(PROJECT_ROOT / "models")  # Путь к конкретной модели LLM
MEMORY_PATH = str(PROJECT_ROOT / "memory")  # Путь к папке с памятью диалогов

# Проверяем существование папок
WHISPERX_MODELS_EXIST = os.path.exists(WHISPERX_MODELS_DIR)
DIARIZE_MODELS_EXIST = os.path.exists(DIARIZE_MODELS_DIR)
MODEL_PATH_EXIST = os.path.exists(MODEL_PATH)
MEMORY_PATH_EXIST = os.path.exists(MEMORY_PATH)
