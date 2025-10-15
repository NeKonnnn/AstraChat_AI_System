import os
import logging
import torch
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальные переменные для хранения моделей Silero
silero_models: Dict[str, torch.nn.Module] = {}


async def get_silero_handler() -> Dict[str, torch.nn.Module]:
    """Получение экземпляров моделей Silero"""
    global silero_models
    
    if not settings.silero.enabled:
        logger.info("Silero отключен в конфигурации")
        return {}
    
    if not silero_models:
        try:
            logger.info(f"Загрузка моделей Silero из {settings.silero.models_dir}")
            
            # Создаем директорию для моделей если не существует
            os.makedirs(settings.silero.models_dir, exist_ok=True)
            
            # Загружаем модели для каждого поддерживаемого языка
            for lang in settings.silero.supported_languages:
                model_path = os.path.join(settings.silero.models_dir, lang, "model.pt")
                
                # Скачиваем модель если не существует
                if not os.path.exists(model_path):
                    await download_model(lang, model_path)
                
                # Загружаем модель
                if os.path.exists(model_path):
                    try:
                        model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
                        model.to('cpu')
                        silero_models[lang] = model
                        logger.info(f"Модель Silero {lang} успешно загружена")
                    except Exception as e:
                        logger.error(f"Ошибка загрузки модели Silero {lang}: {str(e)}")
                        # Пытаемся скачать заново
                        await download_model(lang, model_path)
                        try:
                            model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
                            model.to('cpu')
                            silero_models[lang] = model
                            logger.info(f"Модель Silero {lang} успешно загружена после повторной загрузки")
                        except Exception as e2:
                            logger.error(f"Не удалось загрузить модель Silero {lang} даже после повторной загрузки: {str(e2)}")
                else:
                    logger.error(f"Файл модели Silero {lang} не найден: {model_path}")
            
            if not silero_models:
                logger.warning("Не удалось загрузить ни одной модели Silero")
            
            logger.info(f"Загружено {len(silero_models)} моделей Silero")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации моделей Silero: {str(e)}")
    
    return silero_models


async def download_model(lang: str, model_path: str):
    """Скачивание модели Silero"""
    try:
        # Создаем директорию для модели
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # URL для скачивания модели
        model_urls = {
            'ru': 'https://models.silero.ai/models/tts/ru/v3_1_ru.pt',
            'en': 'https://models.silero.ai/models/tts/en/v3_en.pt'
        }
        
        if lang not in model_urls:
            raise ValueError(f"Неподдерживаемый язык: {lang}")
        
        logger.info(f"Скачивание модели Silero {lang} из {model_urls[lang]}")
        torch.hub.download_url_to_file(model_urls[lang], model_path)
        logger.info(f"Модель Silero {lang} успешно скачана")
        
    except Exception as e:
        logger.error(f"Ошибка скачивания модели Silero {lang}: {str(e)}")
        raise


async def cleanup_silero_handler():
    """Очистка ресурсов моделей Silero"""
    global silero_models
    
    if silero_models:
        logger.info("Освобождение ресурсов моделей Silero")
        silero_models.clear()
