import os
import logging
from typing import Optional, Dict
import torch
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения моделей Silero TTS
silero_models: Optional[Dict[str, any]] = None


async def get_silero_handler() -> Optional[Dict[str, any]]:
    """Получение экземпляров моделей Silero TTS"""
    global silero_models
    
    if not settings.silero.enabled:
        logger.info("Silero TTS отключен в конфигурации")
        return None
    
    if silero_models is None:
        try:
            models_dir = settings.silero.models_dir
            logger.info(f"Загрузка моделей Silero TTS из {models_dir}")
            
            # Проверяем существование директории с моделями
            if not os.path.exists(models_dir):
                logger.warning(f"Директория с моделями Silero TTS не найдена в {models_dir}")
                return None
            
            # Инициализируем словарь для моделей
            silero_models = {}
            
            # Загружаем модели для русского и английского языков
            try:
                # Загрузка модели для русского языка
                ru_model_path = os.path.join(models_dir, "ru", "model.pt")
                if os.path.exists(ru_model_path):
                    silero_models['ru'] = torch.jit.load(ru_model_path, map_location='cpu')
                    logger.info("Модель Silero TTS (ru) успешно загружена")
                
                # Загрузка модели для английского языка
                en_model_path = os.path.join(models_dir, "en", "model.pt")
                if os.path.exists(en_model_path):
                    silero_models['en'] = torch.jit.load(en_model_path, map_location='cpu')
                    logger.info("Модель Silero TTS (en) успешно загружена")
                    
            except Exception as e:
                logger.error(f"Ошибка загрузки моделей Silero TTS: {str(e)}")
                return None
            
            logger.info("Модели Silero TTS успешно загружены")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации моделей Silero TTS: {str(e)}")
            return None
    
    return silero_models


async def cleanup_silero_handler():
    """Очистка ресурсов моделей Silero TTS"""
    global silero_models
    
    if silero_models is not None:
        logger.info("Освобождение ресурсов моделей Silero TTS")
        silero_models = None


