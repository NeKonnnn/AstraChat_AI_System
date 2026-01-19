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
from app.llm_dependencies import get_llama_handler, cleanup_llama_handler
from app.dependencies.vosk_handler import get_vosk_handler, cleanup_vosk_handler
from app.dependencies.silero_handler import get_silero_handler, cleanup_silero_handler
from app.dependencies.whisperx_handler import get_whisperx_handler, cleanup_whisperx_handler
from app.dependencies.diarization_handler import get_diarization_handler, cleanup_diarization_handler
from app.dependencies.surya_handler import get_surya_handler, cleanup_surya_handler
from app.services.nexus_client import download_model_from_nexus_if_needed

from fastapi import Request

# Настройка логирования из конфига
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
        # Проверяем, нужно ли загружать модель из Nexus
        if settings.nexus.enabled:
            # Если Nexus включен, пытаемся загрузить модель
            if not download_model_from_nexus_if_needed():
                logger.error("Failed to download model from Nexus")
                raise RuntimeError("Failed to download model from Nexus")
        
        # Проверяем существование модели перед инициализацией
        model_path = settings.model.path
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found at {model_path}. Application will continue, but LLM features may not work.")
        
        # Инициализируем обработчик LLM
        print("\n" + "=" * 80)
        print("🎯 STARTING LLM SERVICE INITIALIZATION")
        print("=" * 80 + "\n")
        await get_llama_handler()
        print("\n" + "=" * 80)
        print("✅ LLM SERVICE READY")
        print("=" * 80 + "\n")
        logger.info("LLM handler initialized")
        
        # Инициализируем обработчик Vosk (если включен)
        if settings.vosk.enabled:
            await get_vosk_handler()
            logger.info("Vosk handler initialized")
        
        # Инициализируем обработчик Silero (если включен)
        if settings.silero.enabled:
            await get_silero_handler()
            logger.info("Silero handler initialized")
        
        # Инициализируем обработчик WhisperX (если включен)
        if settings.whisperx.enabled:
            try:
                models = await get_whisperx_handler()
                if models:
                    logger.info(f"WhisperX handler initialized with {len(models)} models: {list(models.keys())}")
                else:
                    logger.warning("WhisperX handler initialized but no models were loaded. Use /v1/whisperx/reload to retry loading.")
            except Exception as e:
                logger.error(f"Failed to initialize WhisperX handler: {str(e)}", exc_info=True)
                logger.warning("Application will continue, but WhisperX features may not work. Use /v1/whisperx/reload to retry loading.")
        
        # Инициализируем обработчик диаризации (если включен)
        if settings.diarization.enabled:
            await get_diarization_handler()
            logger.info("Diarization handler initialized")
        
        # Инициализируем обработчик Surya OCR (если включен)
        if settings.surya.enabled:
            await get_surya_handler()
            logger.info("Surya OCR handler initialized")
        
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

    yield

    # Очистка при завершении
    await cleanup_llama_handler()
    await cleanup_vosk_handler()
    await cleanup_silero_handler()
    await cleanup_whisperx_handler()
    await cleanup_diarization_handler()
    await cleanup_surya_handler()
    logger.info("Application shut down gracefully")


def create_application() -> FastAPI:
    """Создание и настройка FastAPI приложения"""


    application = FastAPI(
        title=settings.app.title,
        description=settings.app.description,
        version=settings.app.version,
        lifespan=lifespan,
        docs_url=settings.server.docs_url,
        redoc_url=settings.server.redoc_url,
    )

    # Настройка CORS
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
    """Middleware для логирования всех запросов и ответов"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Логирование входящего запроса
    logger.info(f"Request {request_id}: {request.method} {request.url}")
    logger.info(f"Request {request_id}: Headers: {dict(request.headers)}")

    # Логирование тела запроса для POST запросов (только для не-multipart)
    if request.method == "POST":
        content_type = request.headers.get("content-type", "").lower()
        # Пропускаем чтение тела для multipart/form-data (бинарные файлы)
        # чтобы не мешать обработке файлов в эндпоинтах
        if "multipart/form-data" in content_type:
            # Для multipart запросов логируем только размер из заголовка
            # Не читаем тело, чтобы оно осталось доступным для эндпоинта
            content_length = request.headers.get("content-length", "unknown")
            logger.info(f"Request {request_id}: Body: <multipart/form-data, size: {content_length} bytes>")
        else:
            # Для остальных POST запросов пытаемся прочитать тело
            try:
                body = await request.body()
                if body:
                    try:
                        body_json = json.loads(body.decode())
                        logger.info(f"Request {request_id}: Body: {json.dumps(body_json, ensure_ascii=False)}")
                    except json.JSONDecodeError:
                        try:
                            logger.info(f"Request {request_id}: Body: {body.decode()}")
                        except UnicodeDecodeError:
                            logger.info(f"Request {request_id}: Body: <binary data, size: {len(body)} bytes>")
            except Exception as e:
                logger.error(f"Request {request_id}: Error reading body: {str(e)}")

    # Обработка запроса
    response = await call_next(request)

    # Логирование ответа
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
