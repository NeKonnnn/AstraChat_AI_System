"""
app_state.py - централизованное хранилище сервисов и глобальных переменных
Все роутеры делают:
    from backend.app_state import ask_agent, rag_client, ... и т.д.
"""
import os
import sys
import json
import threading
from backend.settings.logging import get_logger
logger = get_logger(__name__)
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
# -- Agent orchestrator (lazy import: см. ниже _ensure_orchestrator_loaded)
_orchestrator_load_attempted_ok = None  # None = не пробовали, True = ок, False = ошибка
_impl_initialize_agent_orchestrator = None
_impl_get_agent_orchestrator = None
async def initialize_agent_orchestrator():  # type: ignore[misc]
    """Прокси на backend.orchestrator — импорт откладывается до первого вызова (без circular import)."""
    if not _ensure_orchestrator_loaded():
        return False
    if _impl_initialize_agent_orchestrator is None:
        return False
    return await _impl_initialize_agent_orchestrator()
def get_agent_orchestrator():  # type: ignore[misc]
    """Прокси на backend.orchestrator — импорт откладывается до первого вызова (без circular import)."""
    if not _ensure_orchestrator_loaded():
        return None
    if _impl_get_agent_orchestrator is None:
        return None
    return _impl_get_agent_orchestrator()
def _ensure_orchestrator_loaded() -> bool:
    """Один успешный импорт модулей оркестратора; при ошибке — не повторять каждый раз."""
    global _orchestrator_load_attempted_ok, _impl_initialize_agent_orchestrator, _impl_get_agent_orchestrator
    if _orchestrator_load_attempted_ok is True:
        return True
    if _orchestrator_load_attempted_ok is False:
        return False
    try:
        import importlib
        _mod = importlib.import_module('backend.orchestrator')
        _init = getattr(_mod, 'initialize_agent_orchestrator', None)
        _get = getattr(_mod, 'get_agent_orchestrator', None)
        if _init is None or _get is None:
            raise ImportError(
                f"backend.orchestrator не содержит нужных символов: "
                f"initialize_agent_orchestrator={_init!r}, "
                f"get_agent_orchestrator={_get!r}"
            )
        _impl_initialize_agent_orchestrator = _init
        _impl_get_agent_orchestrator = _get
        _orchestrator_load_attempted_ok = True
        logger.info("Агентная архитектура импортирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка импорта агентной архитектуры: {e}")
        _orchestrator_load_attempted_ok = False
        _impl_initialize_agent_orchestrator = None
        _impl_get_agent_orchestrator = None
        return False
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

# -- MCP platform (lazy singleton для routes)
def get_mcp_platform_service():
    from backend.mcp.platform import get_mcp_platform
    return get_mcp_platform()

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
rag_chunking_strategy: str = "hierarchical"
rag_chunk_overlap: int = max(0, int(os.getenv("RAG_CHUNK_OVERLAP", "200") or 200))
try:
    _rst = float(os.getenv("RAG_MIN_SIMILARITY", "0"))
except ValueError:
    _rst = 0.0
rag_similarity_threshold: float = max(0.0, min(_rst, 1.0))
rag_reranking_enabled: bool = _env_rag_pipeline_bool("RAG_USE_RERANKING", False)
try:
    _rtn = int(os.getenv("RAG_RERANK_TOP_N", "5"))
except ValueError:
    _rtn = 5
rag_rerank_top_n: int = max(1, min(_rtn, 64))
rag_system_prompt: str = (
    'Используй только предоставленный контекст. Если ответа нет в тексте, скажи «Не знаю». Не придумывай факты.'
)
try:
    _rk = int(os.getenv("RAG_CHAT_TOP_K", "12"))
except ValueError:
    _rk = 12
rag_chat_top_k: int = max(1, min(_rk, 64))
# -- model comparison (independent from orchestrator/agents)
_model_comparison_models: list[str] = []
_model_comparison_models_lock = threading.Lock()
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
def set_model_comparison_models(models: list[str]) -> list[str]:
    """Сохраняет список моделей для сравнения (глобально для backend процесса)."""
    normalized = []
    seen = set()
    for raw in models or []:
        name = str(raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    with _model_comparison_models_lock:
        _model_comparison_models.clear()
        _model_comparison_models.extend(normalized)
        return list(_model_comparison_models)
def get_model_comparison_models() -> list[str]:
    """Возвращает сохранённый список моделей для сравнения."""
    with _model_comparison_models_lock:
        return list(_model_comparison_models)
# -- путь к файлу настроек
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
def _resolve_settings_file() -> str:
    """
    Выбирает writable-путь для settings.json без привязки к '..' от __file__.
    Порядок: APP_SETTINGS_PATH -> /app/settings.json -> рядом с модулем -> cwd/settings.json.
    """
    candidates: list[str] = []
    env_path = os.getenv("APP_SETTINGS_PATH", "").strip()
    if env_path:
        candidates.append(env_path)
    candidates.extend(
        [
            "/app/settings.json",
            os.path.join(_THIS_DIR, "settings.json"),
            os.path.join(os.getcwd(), "settings.json"),
        ]
    )
    for path in candidates:
        abs_path = os.path.abspath(path)
        parent = os.path.dirname(abs_path) or "."
        if os.path.exists(abs_path):
            if os.access(abs_path, os.W_OK):
                return abs_path
            continue
        if os.path.isdir(parent) and os.access(parent, os.W_OK):
            return abs_path
    return os.path.abspath(os.path.join(os.getcwd(), "settings.json"))
def _settings_file_fallbacks(primary_path: str) -> list[str]:
    cands = [os.path.abspath(primary_path)]
    for p in (
        "/tmp/astrachat-settings.json",
        os.path.join(os.getcwd(), "settings.json"),
    ):
        ap = os.path.abspath(p)
        if ap not in cands:
            cands.append(ap)
    return cands
SETTINGS_FILE = _resolve_settings_file()
# -- helpers
def load_app_settings() -> dict:
    """Загрузить настройки приложения из файла"""
    global current_transcription_engine, current_transcription_language
    global memory_max_messages, memory_include_system_prompts, memory_clear_on_restart
    global current_rag_strategy, agentic_rag_enabled, agentic_max_iterations
    global rag_query_fix_typos, rag_multi_query_enabled, rag_hyde_enabled, rag_chat_top_k
    global rag_chunking_strategy, rag_chunk_overlap, rag_similarity_threshold
    global rag_reranking_enabled, rag_rerank_top_n, rag_system_prompt
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
            if "rag_chunking_strategy" in data:
                v = str(data.get("rag_chunking_strategy") or "").strip().lower()
                if v in {"hierarchical", "fixed", "markdown", "separators", "semantic"}:
                    rag_chunking_strategy = v
            if "rag_chunk_overlap" in data:
                try:
                    rag_chunk_overlap = max(0, min(int(data["rag_chunk_overlap"]), 2000))
                except (TypeError, ValueError):
                    pass
            if "rag_similarity_threshold" in data:
                try:
                    rag_similarity_threshold = max(0.0, min(float(data["rag_similarity_threshold"]), 1.0))
                except (TypeError, ValueError):
                    pass
            if "rag_reranking_enabled" in data:
                rag_reranking_enabled = bool(data["rag_reranking_enabled"])
            if "rag_rerank_top_n" in data:
                try:
                    rag_rerank_top_n = max(1, min(int(data["rag_rerank_top_n"]), 64))
                except (TypeError, ValueError):
                    pass
            if "rag_system_prompt" in data:
                prompt = str(data.get("rag_system_prompt") or "").strip()
                if prompt:
                    rag_system_prompt = prompt
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
        "rag_chunking_strategy": rag_chunking_strategy,
        "rag_chunk_overlap": rag_chunk_overlap,
        "rag_similarity_threshold": rag_similarity_threshold,
        "rag_reranking_enabled": rag_reranking_enabled,
        "rag_rerank_top_n": rag_rerank_top_n,
        "rag_system_prompt": rag_system_prompt,
        "current_model_path": None,
    }
def save_app_settings(updates: dict) -> bool:
    """Сохранить/обновить настройки приложения"""
    global SETTINGS_FILE
    try:
        existing: dict = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(updates)
        for target in _settings_file_fallbacks(SETTINGS_FILE):
            try:
                parent = os.path.dirname(target) or "."
                os.makedirs(parent, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                if target != SETTINGS_FILE:
                    logger.warning(f"Переключение settings.json на fallback путь: {target}")
                    SETTINGS_FILE = target
                logger.info(f"Настройки сохранены: {updates}")
                return True
            except Exception:
                continue
        raise OSError(f"Не удалось сохранить settings ни в один путь: {_settings_file_fallbacks(SETTINGS_FILE)}")
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False
def get_current_model_path() -> str | None:
    """Получить путь к текущей загруженной модели"""
    try:
        default_provider = str(getattr(settings, "default_llm_provider", "") or "").strip()
        default_model = str(getattr(getattr(settings, "llm_service", None), "default_model", "") or "").strip()
        def _normalize_model_path(path_value: str | None) -> str | None:
            raw = str(path_value or "").strip()
            if not raw:
                return None
            if raw.lower() in {"llm-svc", "llm-svc://", "local", "default"}:
                if default_provider and default_model:
                    return f"{default_provider}/{default_model}"
                return None
            return raw
        if get_model_info:
            result = get_model_info()
            if result and "path" in result:
                return _normalize_model_path(result["path"])
        return _normalize_model_path(load_app_settings().get("current_model_path"))
    except Exception as e:
        logger.error(f"Ошибка получения пути модели: {e}")
        return None
# -- загрузка сохраненных настроек при импорте модуля
load_app_settings()