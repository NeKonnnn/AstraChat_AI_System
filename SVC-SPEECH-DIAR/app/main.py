import json
import os
import time
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging.config

from app.core.config import settings
from app.api import router as api_router
# Оставляем только хендлер диаризации
from app.dependencies.diarization_handler import get_diarization_handler, cleanup_diarization_handler
from app.services.nexus_client import download_model_from_nexus_if_needed

from fastapi import Request

# Настройка логирования из конфига (ОРИГИНАЛ БЕЗ ИЗМЕНЕНИЙ)
logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': settings.logging.format
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': settings.logging.level
        }
    },
    'root': {
        'handlers': ['console'],
        'level': settings.logging.level
    }
})

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация при запуске
    try:
        # Проверяем Nexus (ОРИГИНАЛЬНАЯ ЛОГИКА)
        if settings.nexus.enabled:
            if not download_model_from_nexus_if_needed():
                logger.error("Failed to download model from Nexus")
                raise RuntimeError("Failed to download model from Nexus")
        
        # Инициализируем обработчик диаризации (если включен)
        logger.info("diarization.enabled=%s, config_path=%s", settings.diarization.enabled, getattr(settings.diarization, "config_path", "?"))
        if settings.diarization.enabled:
            print("\n" + "=" * 80)
            print("👥 STARTING DIARIZATION SERVICE")
            print("=" * 80 + "\n")
            pipeline_result = await get_diarization_handler()
            if pipeline_result is None:
                logger.error("❌ FAILED TO INITIALIZE DIARIZATION PIPELINE")
                print("\n" + "=" * 80)
                print("❌ FAILED TO INITIALIZE DIARIZATION PIPELINE")
                print("=" * 80 + "\n")
            else:
                logger.info("Diarization handler initialized")
                print("\n" + "=" * 80)
                print("✅ DIARIZATION SERVICE READY")
                print("=" * 80 + "\n")
        else:
            logger.warning("Diarization is DISABLED in config!")
        
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

    yield

    # Очистка при завершении
    await cleanup_diarization_handler()
    logger.info("Application shut down gracefully")


def create_application() -> FastAPI:
    """Создание и настройка FastAPI приложения"""

    application = FastAPI(
        title=settings.app.title + " [Diarization Service]",
        description=settings.app.description,
        version=settings.app.version,
        lifespan=lifespan,
        docs_url=settings.server.docs_url,
        redoc_url=settings.server.redoc_url,
    )

    # Настройка CORS (ОРИГИНАЛ БЕЗ ИЗМЕНЕНИЙ)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
    )

    # Подключение роутеров
    application.include_router(api_router, prefix="/v1")

    return application


app = create_application()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования (ОРИГИНАЛ БЕЗ ИЗМЕНЕНИЙ)"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(f"Request {request_id}: {request.method} {request.url}")

    if request.method == "POST":
        content_type = request.headers.get("content-type", "").lower()
        if "multipart/form-data" in content_type:
            content_length = request.headers.get("content-length", "unknown")
            logger.info(f"Request {request_id}: Body: <multipart/form-data, size: {content_length} bytes>")
        else:
            try:
                body = await request.body()
                if body:
                    try:
                        body_json = json.loads(body.decode())
                        logger.info(f"Request {request_id}: Body: {json.dumps(body_json, ensure_ascii=False)}")
                    except json.JSONDecodeError:
                        logger.info(f"Request {request_id}: Body: <non-json data>")
            except Exception as e:
                logger.error(f"Request {request_id}: Error reading body: {str(e)}")

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(f"Request {request_id}: Response status: {response.status_code}")
    logger.info(f"Request {request_id}: Process time: {process_time:.2f}s")

    return response

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_level=settings.server.log_level.lower(),
    )