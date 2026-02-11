"""
API endpoints module [TTS Service Version].
"""

from fastapi import APIRouter
from .endpoints import tts

# Создаем основной роутер API
router = APIRouter()

# Включаем ТОЛЬКО эндпоинт синтеза речи
router.include_router(tts.router, tags=["Text-to-Speech (Silero)"])