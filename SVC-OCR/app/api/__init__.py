"""
API endpoints module [OCR Service Version].
"""

from fastapi import APIRouter
# Импортируем только эндпоинт OCR
from .endpoints import ocr

# Создаем основной роутер API
router = APIRouter()

# Включаем роутер только для распознавания текста (Surya)
router.include_router(ocr.router, tags=["OCR (Surya)"])