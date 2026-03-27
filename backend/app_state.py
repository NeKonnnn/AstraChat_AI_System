"""
app_state.py - централизованное хранилище сервисов и глобальных переменных

Все роутеры делают:
    from backend.app_state import ask_agent, rag_client, ... и т.д.
"""

import os
import sys
import json
import logging
import threading

logger = logging.getLogger(__name__)

# -- сервисы агента
try:
    from backend.agent_llm_svc import (
        ask_agent,
        model_settings,
        update_model_settings,
        reload_model_by_path,
        get_model_info,
        initialize_model,
    )
    from backend.context_prompts import context_prompt_manager
    logger.info("agent_llm_svc импортирован успешно")
except Exception as e:
    logger.error(f"Ошибка импорта agent_llm_svc: {e}")
    ask_agent = None
    model_settings = None
    update_model_settings = None
    reload_model_by_path = None
    get_model_info = None
    initialize_model = None
    context_prompt_manager = None

# -- memory / MongoDB
try:
    from backend.database.memory_service import (
        save_dialog_entry,
        load_dialog_history,
        clear_dialog_history,
        get_recent_dialog_history,
        reset_conversation,
        get_or_create_conversation_id,
        remove_last_user_message,
    )
    logger.info("memory_service импортирован успешно")
except Exception as e:
    logger.error(f"Ошибка импорта memory_service: {e}")
    save_dialog_entry = None
    load_dialog_history = None
    clear_dialog_history = None
    get_recent_dialog_history = None
    reset_conversation = None
    get_or_create_conversation_id = None
    remove_last_user_message = None

# -- voice
try:
    from backend.transcription.voice import speak_text, recognize_speech, recognize_speech_from_file, check_stt_available
    logger.info("voice импортирован успешно")
except Exception as e:
    logger.error(f"Ошибка импорта voice: {e}")
    speak_text = None
    recognize_speech = None
    recognize_speech_from_file = None
    check_stt_available = None

# -- MinIO
try:
    from backend.database.minio import get_minio_client
    minio_client = get_minio_client()
    logger.info("MinIO клиент инициализирован" if minio_client else "MinIO недоступен")
except Exception as e:
    logger.warning(f"MinIO недоступен: {e}")
    minio_client = None

# -- RAG client (SVC-RAG)
try:
    from backend.settings.rag_client import get_rag_client
    rag_client = get_rag_client()
    logger.info(f"RagClient инициализирован, base_url={rag_client.base_url}")
except Exception as e:
    logger.warning(f"RagClient недоступен: {e}")
    rag_client = None

# -- Transcriber
try:
    from backend.transcription.universal_transcriber import UniversalTranscriber
    transcriber = UniversalTranscriber(engine="whisperx")
    logger.info("UniversalTranscriber инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации UniversalTranscriber: {e}")
    UniversalTranscriber = None
    transcriber = None

# -- Agent orchestrator
try:
    from backend.orchestrator import initialize_agent_orchestrator, get_agent_orchestrator
    logger.info("Агентная архитектура импортирована")
except Exception as e:
    logger.error(f"Ошибка импорта агентной архитектуры: {e}")
    initialize_agent_orchestrator = None
    get_agent_orchestrator = None

# -- Database
try:
    from backend.database.init_db import (
        init_databases,
        close_databases,
        get_conversation_repository,
        get_document_repository,
        get_vector_repository,
    )
    database_available = True
    logger.info("Database модуль импортирован")
except Exception as e:
    logger.warning(f"Database модуль недоступен: {e}")
    init_databases = None
    close_databases = None
    get_conversation_repository = None
    get_document_repository = None
    get_vector_repository = None
    database_available = False

# -- settings
from backend.settings import get_settings

settings = get_settings()

# -- глобальный lock для загрузки моделей (multi-llm)
model_load_lock = threading.Lock()

# -- флаги
stop_generation_flags: dict = {}
stop_transcription_flags: dict = {}
voice_chat_stop_flag: bool = False

# -- настройки приложения (мутируемые)
current_transcription_engine: str = "whisperx"
current_transcription_language: str = "ru"
current_rag_strategy: str = "auto"
memory_max_messages: int = 20
memory_include_system_prompts: bool = True
memory_clear_on_restart: bool = False

# -- путь к файлу настроек
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(_THIS_DIR, "..", "settings.json")


# -- helpers

def load_app_settings() -> dict:
    """Загрузить настройки приложения из файла"""
    global current_transcription_engine, current_transcription_language
    global memory_max_messages, memory_include_system_prompts, memory_clear_on_restart
    global current_rag_strategy

    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _eng = data.get("transcription_engine", "whisperx")
            current_transcription_engine = "whisperx" if _eng == "vosk" else _eng
            current_transcription_language = data.get("transcription_language", "ru")
            memory_max_messages = data.get("memory_max_messages", 20)
            memory_include_system_prompts = data.get("memory_include_system_prompts", True)
            memory_clear_on_restart = data.get("memory_clear_on_restart", False)
            current_rag_strategy = data.get("rag_strategy", "auto")
            logger.info(f"Настройки загружены из {SETTINGS_FILE}")
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек: {e}")

    return {
        "transcription_engine": current_transcription_engine,
        "transcription_language": current_transcription_language,
        "memory_max_messages": memory_max_messages,
        "memory_include_system_prompts": memory_include_system_prompts,
        "memory_clear_on_restart": memory_clear_on_restart,
        "rag_strategy": current_rag_strategy,
        "current_model_path": None,
    }


def save_app_settings(updates: dict) -> bool:
    """Сохранить/обновить настройки приложения"""
    try:
        existing: dict = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(updates)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"Настройки сохранены: {updates}")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False


def get_current_model_path() -> str | None:
    """Получить путь к текущей загруженной модели"""
    try:
        if get_model_info:
            result = get_model_info()
            if result and "path" in result:
                return result["path"]
        return load_app_settings().get("current_model_path")
    except Exception as e:
        logger.error(f"Ошибка получения пути модели: {e}")
        return None


# -- загрузка сохраненных настроек при импорте модуля
load_app_settings()
