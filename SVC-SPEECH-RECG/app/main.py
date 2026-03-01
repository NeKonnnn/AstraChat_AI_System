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
# Оставляем только хендлеры распознавания речи
from app.dependencies.vosk_handler import get_vosk_handler, cleanup_vosk_handler
from app.dependencies.whisperx_handler import get_whisperx_handler, cleanup_whisperx_handler

from fastapi import Request

# Настройка логирования (ОРИГИНАЛ БЕЗ ИЗМЕНЕНИЙ)
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
        # Инициализируем обработчик Vosk (если включен)
        if settings.vosk.enabled:
            print("\n" + "=" * 80)
            print("🎙️ STARTING VOSK HANDLER")
            await get_vosk_handler()
            logger.info("Vosk handler initialized")
        
        # Инициализируем обработчик WhisperX (если включен)
        if settings.whisperx.enabled:
            print("🚀 STARTING WHISPERX HANDLER")
            try:
                models = await get_whisperx_handler()
                if models:
                    logger.info(f"WhisperX handler initialized with {len(models)} models")
                else:
                    logger.warning("WhisperX handler initialized but no models were loaded")
            except Exception as e:
                logger.error(f"Failed to initialize WhisperX handler: {str(e)}", exc_info=True)
        
        print("=" * 80 + "\n")
        logger.info("Speech Recognition Service started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

    yield

    # Очистка при завершении
    await cleanup_vosk_handler()
    await cleanup_whisperx_handler()
    logger.info("Application shut down gracefully")


def create_application() -> FastAPI:
    """Создание и настройка FastAPI приложения"""

    application = FastAPI(
        title=settings.app.title + " [STT Service]",
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
                    except:
                        try:
                            logger.info(f"Request {request_id}: Body: {body.decode()}")
                        except:
                            logger.info(f"Request {request_id}: Body: <binary data>")
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