import os
import logging
from typing import Optional
from vosk import Model
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения модели Vosk
vosk_model: Optional[Model] = None


async def get_vosk_handler() -> Optional[Model]:
    """Получение экземпляра модели Vosk"""
    global vosk_model
    
    if not settings.vosk.enabled:
        logger.info("Vosk отключен в конфигурации")
        return None
    
    if vosk_model is None:
        try:
            logger.info(f"Загрузка модели Vosk из {settings.vosk.model_path}")
            
            # Проверяем существование модели
            if not os.path.exists(settings.vosk.model_path):
                logger.warning(f"Модель Vosk не найдена в {settings.vosk.model_path}")
                return None
            
            # Загружаем модель
            vosk_model = Model(settings.vosk.model_path)
            logger.info("Модель Vosk успешно загружена")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели Vosk: {str(e)}")
            return None
    
    return vosk_model


async def cleanup_vosk_handler():
    """Очистка ресурсов модели Vosk"""
    global vosk_model
    
    if vosk_model is not None:
        logger.info("Освобождение ресурсов модели Vosk")
        vosk_model = None
