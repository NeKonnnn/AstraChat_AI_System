"""
API endpoints module [STT Service Version].
"""

from fastapi import APIRouter
# Импортируем только те эндпоинты, которые мы скопировали в этот проект
from .endpoints import transcription, whisperx

# Создаем основной роутер API
router = APIRouter()

# Включаем роутеры только для распознавания речи
# Vosk
router.include_router(transcription.router, tags=["Transcription (Vosk)"])
# WhisperX
router.include_router(whisperx.router, tags=["Transcription (WhisperX)"])