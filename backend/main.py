"""
main.py - точка входа
Здесь только:
  - настройка кодировки / логирования
  - создание app и sio
  - монтирование роутеров
  - startup / shutdown хуки
Вся логика работы приложения - в backend/routes/*.py, backend/socket_handlers.py и т.д.
"""
# кодировка Windowsimport sys, os
import sys
import os
try:
    from utils.encoding_fix import fix_windows_encoding
    fix_windows_encoding()
except ImportError:
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        for _s in (sys.stdout, sys.stderr):
            if hasattr(_s, "reconfigure"):
                _s.reconfigure(encoding="utf-8")
# -- пути
_current_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_current_dir)
try:
    from dotenv import load_dotenv
    _env = os.path.join(_root_dir, ".env")
    if os.path.exists(_env):
        load_dotenv(_env)
        print(f".env загружен: {_env}")
except ImportError:
    pass
if _current_dir == "/app" and not os.path.exists("/app/backend"):
    os.system("ln -sf /app /app/backend")
sys.path.insert(0, _current_dir)
sys.path.insert(0, _root_dir)
# -- логирование
import logging
from backend.settings.cef_logger.cef_logger import log_cef_event

_BACKEND_LOG_FORMAT = "[%(asctime)s] %(levelname)s [Backend] %(message)s"
_BACKEND_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _configure_backend_logging() -> None:
    """INFO/WARNING backend.* в stdout при запуске через uvicorn (не python main.py).

    Uvicorn настраивает root до импорта app — basicConfig тогда не срабатывает,
    root handler часто на WARNING, и logger.info из backend.* не виден в kubectl logs.
    """
    level_name = (
        os.getenv("APP_LOG_LEVEL")
        or os.getenv("astrachat_LOG_LEVEL")
        or os.getenv("ASTRACHAT_LOG_LEVEL")
        or "INFO"
    ).upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(_BACKEND_LOG_FORMAT, datefmt=_BACKEND_LOG_DATEFMT)
    backend_logger = logging.getLogger("backend")
    backend_logger.setLevel(level)
    backend_logger.propagate = False
    if not backend_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        if hasattr(handler.stream, "reconfigure"):
            handler.stream.reconfigure(encoding="utf-8")
        backend_logger.addHandler(handler)


logging.basicConfig(
    level=logging.DEBUG,
    format=_BACKEND_LOG_FORMAT,
    datefmt=_BACKEND_LOG_DATEFMT,
    handlers=[logging.StreamHandler(sys.stdout)],
)
_configure_backend_logging()
# CEF: отдельный логгер «cef» — при старте через uvicorn root уже может быть настроен,
# и строки CEF теряются среди форматов вида «INFO:backend…». Пишем сырую строку CEF в stdout.
_cef_logger = logging.getLogger("cef")
_cef_logger.setLevel(logging.INFO)
_cef_logger.propagate = False
if not _cef_logger.handlers:
    _cef_handler = logging.StreamHandler(sys.stdout)
    _cef_handler.setLevel(logging.INFO)
    _cef_handler.setFormatter(logging.Formatter("%(message)s"))
    _cef_logger.addHandler(_cef_handler)
for _h in logging.root.handlers:
    if hasattr(_h, "stream") and hasattr(_h.stream, "reconfigure"):
        _h.stream.reconfigure(encoding="utf-8")
for _noisy in ("pymongo", "pymongo.topology", "pymongo.connection", "pymongo.serverSelection"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.info("Логирование настроено")
# -- импорт app_state (загружает все сервисы)
import backend.app_state as state
from backend.app_state import (
    settings, load_app_settings, save_app_settings,
    init_databases, close_databases, database_available,
    initialize_agent_orchestrator, clear_dialog_history,
    memory_clear_on_restart, minio_client,
)
# -- FastAPI
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
_app_cfg = settings.app
app = FastAPI(
    title=_app_cfg.name,
    description=_app_cfg.description,
    version=_app_cfg.version,
    debug=_app_cfg.debug,
)
_cors_origins = [o for o in settings.cors.allowed_origins if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)
from backend.settings.cef_logger.cef_audit_middleware import CefAuditMiddleware

app.add_middleware(CefAuditMiddleware)
# -- Socket.IO
from backend.realtime import sio, socket_app
from backend.realtime import register_handlers
register_handlers(sio)
app.mount("/socket.io", socket_app)
# -- роутеры
from backend.routes.system import router as system_router
from backend.routes.chat import router as chat_router
from backend.routes.models import router as models_router
from backend.routes.llm import router as llm_router
from backend.routes.llm_providers import router as llm_providers_router
from backend.routes.memory import router as memory_router
from backend.routes.voice import router as voice_router
from backend.routes.documents import router as documents_router
from backend.routes.transcription import router as transcription_router
from backend.routes.rag import router as rag_router
from backend.routes.agents import router as agents_router
from backend.routes.context_prompts import router as context_prompts_router
from backend.routes.project_rag import router as project_rag_router
from backend.routes.model_comparison import router as model_comparison_router
from backend.routes.mcp import router as mcp_router
from backend.routes.image_generation import router as image_generation_router
for _r in (
    system_router, chat_router, models_router, llm_router, llm_providers_router,
    memory_router, voice_router, documents_router, transcription_router,
    rag_router, agents_router, context_prompts_router,
    project_rag_router, model_comparison_router,
    mcp_router, image_generation_router,
):
    app.include_router(_r)
try:
    from backend.routes.mcp_atlassian import router as mcp_atlassian_router

    app.include_router(mcp_atlassian_router)
    logger.info("mcp_atlassian router подключен")
except Exception as _e:
    logger.warning("mcp_atlassian router недоступен: %s", _e)
# -- внешние роутеры (auth, prompts gallery, agents gallery, share)
for _name, _import_path in [
    ("auth",    "backend.auth.routes"),
    ("prompts", "backend.api_prompts"),
    ("agents",  "backend.api_agents"),
    ("share",   "backend.routes.share"),
]:
    try:
        import importlib
        _mod = importlib.import_module(_import_path)
        app.include_router(_mod.router)
        logger.info(f"{_name} router подключен")
    except Exception as _e:
        logger.warning(f"{_name} router недоступен: {_e}")
# -- startup / shutdown
@app.on_event("startup")
async def startup_event():
    logger.info("Запуск приложения...")
    for _k in ("MONGODB_HOST", "MONGODB_PORT", "MONGODB_USER"):
        logger.info(f"{_k}: {os.getenv(_k, '')!r}")
    _pw = os.getenv("MONGODB_PASSWORD", "")
    logger.info(f"MONGODB_PASSWORD: {'*' * len(_pw)} (len={len(_pw)})")
    if init_databases and database_available:
        try:
            if await init_databases():
                logger.info("Базы данных инициализированы")
                try:
                    from backend.database.init_db import postgresql_connection
                    if postgresql_connection:
                        await postgresql_connection.ensure_pool()
                except Exception as e:
                    logger.warning(f"PostgreSQL pool: {e}")
                if minio_client:
                    logger.info(f"MinIO готов: {minio_client.endpoint}")
            else:
                logger.warning("Часть БД не инициализирована - файловый режим")
        except Exception as e:
            logger.error(f"Ошибка init_databases: {e}\n{traceback.format_exc()}")
    if initialize_agent_orchestrator:
        try:
            if await initialize_agent_orchestrator():
                logger.info("Агентная архитектура инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации оркестратора: {e}")
    if getattr(settings, "mcp", None) and settings.mcp.enabled:
        try:
            from backend.mcp.platform import get_mcp_platform
            await get_mcp_platform().initialize()
            logger.info("MCP platform инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации MCP platform: {e}")
    # очистка памяти при рестарте
    if state.memory_clear_on_restart and clear_dialog_history:
        try:
            await clear_dialog_history()
            logger.info("Память очищена при перезапуске")
        except Exception as e:
            logger.warning(f"Не удалось очистить память: {e}")
    logger.info("Приложение запущено")
    log_cef_event("SYS001")
@app.on_event("shutdown")
async def shutdown_event():
    log_cef_event("SYS002")
    logger.info("Остановка приложения...")
    try:
        from backend.mcp.platform import get_mcp_platform
        platform = get_mcp_platform()
        if platform.initialized:
            await platform.shutdown()
    except Exception as e:
        logger.warning(f"MCP platform shutdown: {e}")
    if close_databases and database_available:
        try:
            await close_databases()
            logger.info("БД закрыты")
        except Exception as e:
            logger.error(f"Ошибка закрытия БД: {e}")
    logger.info("Приложение остановлено")
# -- статика 
_is_docker = os.getenv("DOCKER_ENV", "").lower() == "true"
if not _is_docker and os.path.exists("../frontend/build"):
    app.mount("/static", StaticFiles(directory="../frontend/build/static"), name="static")
    @app.get("/{path:path}")
    async def serve_react(path: str):
        idx = "../frontend/build/index.html"
        return FileResponse(idx) if os.path.exists(idx) else {"message": "Frontend not built"}
# -- точка запуска
if __name__ == "__main__":
    import uvicorn
    from backend.app_state import get_current_model_path, reload_model_by_path
    _urls_cfg = settings.urls
    print(f"API docs: {_urls_cfg.backend_port}/docs")
    # восстанавливаем сохраненную модель
    try:
        _saved = load_app_settings().get("current_model_path")
        if _saved and reload_model_by_path:
            if _saved.startswith("llm-svc://"):
                logger.info(f"Модель llm-svc уже доступна: {_saved}")
            elif os.path.exists(_saved) and not os.path.isdir(_saved):
                if reload_model_by_path(_saved):
                    logger.info(f"Модель восстановлена: {_saved}")
                else:
                    logger.warning(f"Не удалось восстановить: {_saved}")
    except Exception as e:
        logger.error(f"Ошибка восстановления модели: {e}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info", log_config=None)