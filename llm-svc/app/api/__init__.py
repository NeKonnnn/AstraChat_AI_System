"""
API endpoints module.
"""

from fastapi import APIRouter
from .endpoints import chat, health, models, transcription, tts, whisperx, diarization

# Создаем основной роутер API
router = APIRouter()

# Включаем все эндпоинты из модулей
router.include_router(health.router, tags=["Health"])
router.include_router(models.router, tags=["Models"])
router.include_router(chat.router, tags=["Chat"])
router.include_router(transcription.router, tags=["Transcription (Vosk)"])
router.include_router(tts.router, tags=["Text-to-Speech (Silero)"])
router.include_router(whisperx.router, tags=["Transcription (WhisperX)"])
router.include_router(diarization.router, tags=["Speaker Diarization"])