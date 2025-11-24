"""
API endpoints module.
"""

from fastapi import APIRouter
from .endpoints import chat, health, models, transcription, tts, whisperx, diarization, ocr

# Создаем основной роутер API
router = APIRouter()

# Включаем все эндпоинты из модулей
router.include_router(health.router, tags=["Health"])
router.include_router(models.router, tags=["Models"])
router.include_router(chat.router, tags=["Chat"])
# vLLM endpoint больше не нужен - выбор handler происходит автоматически в chat endpoint
router.include_router(transcription.router, tags=["Transcription (Vosk)"])
router.include_router(tts.router, tags=["Text-to-Speech (Silero)"])
router.include_router(whisperx.router, tags=["Transcription (WhisperX)"])
router.include_router(diarization.router, tags=["Speaker Diarization"])
router.include_router(ocr.router, tags=["OCR (Surya)"])