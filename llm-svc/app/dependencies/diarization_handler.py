import os
import logging
import torch
import yaml
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальные переменные для хранения моделей диаризации
diarization_pipeline: Optional[Any] = None


async def get_diarization_handler() -> Optional[Any]:
    """Получение экземпляра пайплайна диаризации"""
    global diarization_pipeline
    
    if not settings.diarization.enabled:
        logger.info("Диаризация отключена в конфигурации")
        return None
    
    if diarization_pipeline is None:
        try:
            logger.info(f"Загрузка пайплайна диаризации из {settings.diarization.config_path}")
            
            # Проверяем доступность pyannote
            try:
                from pyannote.audio import Pipeline
            except ImportError:
                logger.error("pyannote.audio не установлен. Установите: pip install pyannote.audio")
                return None
            
            # Проверяем существование конфигурации
            if not os.path.exists(settings.diarization.config_path):
                logger.error(f"Файл конфигурации диаризации не найден: {settings.diarization.config_path}")
                return None
            
            # Загружаем конфигурацию
            with open(settings.diarization.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Определяем устройство
            device = settings.diarization.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            logger.info(f"Используется устройство для диаризации: {device}")
            
            # Создаем пайплайн диаризации
            try:
                diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=True  # Может потребоваться токен HuggingFace
                )
                
                # Перемещаем на нужное устройство
                if device == "cuda" and torch.cuda.is_available():
                    diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
                
                logger.info("Пайплайн диаризации успешно загружен")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки пайплайна диаризации: {str(e)}")
                logger.info("Попытка загрузки с локальной конфигурацией...")
                
                # Пытаемся загрузить с локальной конфигурацией
                try:
                    diarization_pipeline = Pipeline.from_pretrained(
                        settings.diarization.config_path
                    )
                    
                    if device == "cuda" and torch.cuda.is_available():
                        diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
                    
                    logger.info("Пайплайн диаризации загружен с локальной конфигурацией")
                    
                except Exception as e2:
                    logger.error(f"Ошибка загрузки с локальной конфигурацией: {str(e2)}")
                    return None
            
        except Exception as e:
            logger.error(f"Ошибка инициализации пайплайна диаризации: {str(e)}")
    
    return diarization_pipeline


async def cleanup_diarization_handler():
    """Очистка ресурсов пайплайна диаризации"""
    global diarization_pipeline
    
    if diarization_pipeline is not None:
        logger.info("Освобождение ресурсов пайплайна диаризации")
        del diarization_pipeline
        diarization_pipeline = None
        
        # Очищаем кэш CUDA если используется
        if torch.cuda.is_available():
            torch.cuda.empty_cache()














