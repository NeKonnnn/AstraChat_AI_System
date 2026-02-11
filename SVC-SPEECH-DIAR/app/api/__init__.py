"""
API endpoints module [Diarization Service Version].
"""

from fastapi import APIRouter
# Импортируем только эндпоинт диаризации
from .endpoints import diarization

# Создаем основной роутер API
router = APIRouter()

# Включаем роутер только для разделения спикеров
router.include_router(diarization.router, tags=["Speaker Diarization"])