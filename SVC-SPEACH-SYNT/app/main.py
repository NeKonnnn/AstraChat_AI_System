import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import tts
from app.dependencies.silero_handler import get_silero_handler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GPB Silero TTS Service",
    description="Микросервис для синтеза речи (Text-to-Speech)",
    version="1.0.0"
)

# Настройка CORS (разрешаем запросы с любых адресов, чтобы фронт и другие сервисы могли стучаться)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутер с нашими эндпоинтами (prefix="/api" означает, что ручки будут доступны по адресу /api/synthesize)
app.include_router(tts.router, prefix="/api", tags=["tts"])

@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервера"""
    logger.info("Запуск сервиса Silero TTS...")
    # Предзагрузка моделей при старте, чтобы первый запрос не тупил
    await get_silero_handler()
    logger.info("Сервис готов к работе!")

@app.get("/health")
async def health_check():
    """Простой healthcheck для Kubernetes/Docker"""
    return {"status": "ok", "service": "GPB-CORSUR-SVC-SPEACH-SYNT"}