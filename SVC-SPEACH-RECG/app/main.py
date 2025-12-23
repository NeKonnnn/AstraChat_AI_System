import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import transcription, whisperx
from app.dependencies.vosk_handler import get_vosk_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GPB Speech Recognition Service",
    description="Микросервис для распознавания речи (STT: Vosk + WhisperX)",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vosk доступен по /api/transcribe
app.include_router(transcription.router, prefix="/api", tags=["vosk"])
# WhisperX доступен по /api/whisperx/...
app.include_router(whisperx.router, prefix="/api", tags=["whisperx"])

@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервера"""
    logger.info("Запуск сервиса Speech Recognition...")
    # Предзагружаем легкую модель Vosk 
    await get_vosk_handler()
    logger.info("Сервис готов к работе!")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "GPB-CORSUR-SVC-SPEACH-RECG"}