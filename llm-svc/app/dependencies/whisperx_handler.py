import os
import logging
import torch
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальные переменные для хранения моделей WhisperX
whisperx_models: Dict[str, Any] = {}


async def get_whisperx_handler() -> Dict[str, Any]:
    """Получение экземпляров моделей WhisperX"""
    global whisperx_models
    
    if not settings.whisperx.enabled:
        logger.info("WhisperX отключен в конфигурации")
        return {}
    
    if not whisperx_models:
        try:
            logger.info(f"Загрузка моделей WhisperX из {settings.whisperx.models_dir}")
            
            # Проверяем доступность WhisperX
            try:
                import whisperx
            except ImportError:
                logger.error("WhisperX не установлен. Установите: pip install whisperx")
                return {}
            
            # Создаем директорию для моделей если не существует
            os.makedirs(settings.whisperx.models_dir, exist_ok=True)
            
            # Определяем устройство
            device = settings.whisperx.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            logger.info(f"Используется устройство: {device}")
            
            # Загружаем модели для каждого поддерживаемого языка
            for lang in settings.whisperx.supported_languages:
                if lang == "auto":
                    continue
                    
                try:
                    # Загружаем модель WhisperX
                    model = whisperx.load_model(
                        "large-v3",  # Используем большую модель для лучшего качества
                        device=device,
                        compute_type=settings.whisperx.compute_type,
                        language=lang
                    )
                    
                    whisperx_models[lang] = {
                        "model": model,
                        "device": device,
                        "compute_type": settings.whisperx.compute_type
                    }
                    
                    logger.info(f"Модель WhisperX {lang} успешно загружена")
                    
                except Exception as e:
                    logger.error(f"Ошибка загрузки модели WhisperX {lang}: {str(e)}")
                    continue
            
            if not whisperx_models:
                logger.warning("Не удалось загрузить ни одной модели WhisperX")
            
            logger.info(f"Загружено {len(whisperx_models)} моделей WhisperX")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации моделей WhisperX: {str(e)}")
    
    return whisperx_models


async def cleanup_whisperx_handler():
    """Очистка ресурсов моделей WhisperX"""
    global whisperx_models
    
    if whisperx_models:
        logger.info("Освобождение ресурсов моделей WhisperX")
        for lang, model_info in whisperx_models.items():
            if "model" in model_info:
                del model_info["model"]
        whisperx_models.clear()
        
        # Очищаем кэш CUDA если используется
        if torch.cuda.is_available():
            torch.cuda.empty_cache()















