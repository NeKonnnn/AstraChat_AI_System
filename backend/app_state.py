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

# Глобальный lock model_load_lock удалён: после перевода multi-LLM на
# ProviderRegistry свап модели в llm-svc сериализуется внутренним
# LlmSvcProvider._switch_lock, не блокируя параллельные слоты.

# -- флаги
stop_generation_flags: dict = {}
stop_transcription_flags: dict = {}
voice_chat_stop_flag: bool = False

# -- настройки приложения (мутируемые)
current_transcription_engine: str = "whisperx"
current_transcription_language: str = "ru"
current_rag_strategy: str = "auto"
agentic_rag_enabled: bool = True
agentic_max_iterations: int = 2
memory_max_messages: int = 20
memory_include_system_prompts: bool = True
memory_clear_on_restart: bool = False


def _env_rag_pipeline_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v not in ("0", "false", "no", "off")


# Препроцесс RAG-запроса (см. Настройки → RAG); до записи в settings.json — из ENV
rag_query_fix_typos: bool = _env_rag_pipeline_bool("RAG_QUERY_FIX_TYPOS", False)
rag_multi_query_enabled: bool = _env_rag_pipeline_bool("RAG_MULTI_QUERY_ENABLED", False)
rag_hyde_enabled: bool = _env_rag_pipeline_bool("RAG_HYDE_ENABLED", False)

try:
    _rk = int(os.getenv("RAG_CHAT_TOP_K", "12"))
except ValueError:
    _rk = 12
rag_chat_top_k: int = max(1, min(_rk, 64))


def get_rag_chat_top_k() -> int:
    """Сколько чанков запрашивать у SVC-RAG (чат, агент, API с документами).

    Дефолт 12 (а не 8): на слабых мультиязычных эмбеддингах (MiniLM-L12) top-8
    слишком часто не захватывает нужный чанк, особенно на именах собственных и
    коротких факт-запросах. 12–16 — sweet-spot; выше — начинает раздувать
    контекст и разбавлять внимание LLM.
    """
    try:
        v = int(rag_chat_top_k)
    except (TypeError, ValueError):
        v = 12
    return max(1, min(v, 64))

# -- путь к файлу настроек
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(_THIS_DIR, "..", "settings.json")


# -- helpers

def load_app_settings() -> dict:
    """Загрузить настройки приложения из файла"""
    global current_transcription_engine, current_transcription_language
    global memory_max_messages, memory_include_system_prompts, memory_clear_on_restart
    global current_rag_strategy, agentic_rag_enabled, agentic_max_iterations
    global rag_query_fix_typos, rag_multi_query_enabled, rag_hyde_enabled, rag_chat_top_k

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
            # Режим «reranking» убран из UI; старые сохранения → гибрид (реранк по конфигу SVC-RAG).
            if current_rag_strategy == "reranking":
                current_rag_strategy = "hybrid"
                data["rag_strategy"] = "hybrid"
                save_app_settings({"rag_strategy": "hybrid"})
            if "agentic_rag_enabled" in data:
                agentic_rag_enabled = bool(data["agentic_rag_enabled"])
            try:
                ami = int(data.get("agentic_max_iterations", 2))
                agentic_max_iterations = max(1, min(ami, 5))
            except (TypeError, ValueError):
                agentic_max_iterations = 2
            if "rag_query_fix_typos" in data:
                rag_query_fix_typos = bool(data["rag_query_fix_typos"])
            if "rag_multi_query_enabled" in data:
                rag_multi_query_enabled = bool(data["rag_multi_query_enabled"])
            if "rag_hyde_enabled" in data:
                rag_hyde_enabled = bool(data["rag_hyde_enabled"])
            if "rag_chat_top_k" in data:
                try:
                    rag_chat_top_k = max(1, min(int(data["rag_chat_top_k"]), 64))
                except (TypeError, ValueError):
                    pass
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
        "agentic_rag_enabled": agentic_rag_enabled,
        "agentic_max_iterations": agentic_max_iterations,
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
