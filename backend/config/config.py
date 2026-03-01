import os
from pathlib import Path
from pydantic_settings import BaseSettings

# --- НОВЫЕ НАСТРОЙКИ (Для микросервисов) ---
class ServicesConfig(BaseSettings):
    """Конфигурация адресов микросервисов"""
    # Адреса по умолчанию для Docker сети
    # Можно переопределить через переменные окружения SVC_..._URL
    llm_url: str = os.getenv("SVC_LLM_URL", "http://llm-service:8000")
    stt_url: str = os.getenv("SVC_STT_URL", "http://stt-service:8000")
    tts_url: str = os.getenv("SVC_TTS_URL", "http://tts-service:8000")
    ocr_url: str = os.getenv("SVC_OCR_URL", "http://ocr-service:8000")
    diarization_url: str = os.getenv("SVC_DIARIZATION_URL", "http://diarization-service:8000")

# Глобальный объект настроек
services_settings = ServicesConfig()


# --- СТАРЫЕ КОНСТАНТЫ ---
# Получаем абсолютный путь к корневой директории проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Пути к папкам с моделями (Оставляем, чтобы код не падал при импорте, но использовать не будем)
WHISPERX_MODELS_DIR = str(PROJECT_ROOT / "whisperx_models")
DIARIZE_MODELS_DIR = str(PROJECT_ROOT / "diarize_models")

# Пути к конкретным моделям
WHISPERX_BASE_MODEL = "base"
WHISPERX_SMALL_MODEL = "small"
DIARIZE_MODEL = "pyannote/speaker-diarization-3.1"

# Пути для других модулей
MODEL_PATH = str(PROJECT_ROOT / "models")
MEMORY_PATH = str(PROJECT_ROOT / "memory")

# Проверки существования (Можно оставить False, так как локально моделей может и не быть)
WHISPERX_MODELS_EXIST = os.path.exists(WHISPERX_MODELS_DIR)
DIARIZE_MODELS_EXIST = os.path.exists(DIARIZE_MODELS_DIR)
MODEL_PATH_EXIST = os.path.exists(MODEL_PATH)
MEMORY_PATH_EXIST = os.path.exists(MEMORY_PATH)