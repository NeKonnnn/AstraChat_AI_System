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
            
            # Определяем устройство
            device = settings.diarization.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            logger.info(f"Используется устройство для диаризации: {device}")
            
            # Сначала пытаемся загрузить из локальной конфигурации
            logger.info("Попытка загрузки пайплайна из локальной конфигурации...")
            try:
                # Загружаем конфигурацию и исправляем пути
                with open(settings.diarization.config_path, 'r', encoding='utf-8') as f:
                    config_content = f.read()
                    config = yaml.safe_load(config_content)
                
                # Исправляем пути на пути внутри контейнера
                models_dir = settings.diarization.models_dir
                if 'pipeline' in config and 'params' in config['pipeline']:
                    params = config['pipeline']['params']
                    # Исправляем путь к embedding модели
                    if 'embedding' in params and isinstance(params['embedding'], str):
                        embedding_path = params['embedding']
                        # Если это абсолютный путь Windows или путь с диском - заменяем
                        if os.path.isabs(embedding_path) or ':' in embedding_path:
                            embedding_file = os.path.basename(embedding_path)
                            params['embedding'] = os.path.join(models_dir, "models", embedding_file)
                            logger.info(f"Исправлен путь embedding: {params['embedding']}")
                        # Если это относительный путь - делаем абсолютным относительно models_dir
                        elif not os.path.isabs(embedding_path):
                            params['embedding'] = os.path.join(models_dir, embedding_path)
                            logger.info(f"Преобразован относительный путь embedding: {params['embedding']}")
                    
                    # Исправляем путь к segmentation модели
                    if 'segmentation' in params and isinstance(params['segmentation'], str):
                        segmentation_path = params['segmentation']
                        # Если это абсолютный путь Windows или путь с диском - заменяем
                        if os.path.isabs(segmentation_path) or ':' in segmentation_path:
                            segmentation_file = os.path.basename(segmentation_path)
                            params['segmentation'] = os.path.join(models_dir, "models", segmentation_file)
                            logger.info(f"Исправлен путь segmentation: {params['segmentation']}")
                        # Если это относительный путь - делаем абсолютным относительно models_dir
                        elif not os.path.isabs(segmentation_path):
                            params['segmentation'] = os.path.join(models_dir, segmentation_path)
                            logger.info(f"Преобразован относительный путь segmentation: {params['segmentation']}")
                
                # Сохраняем исправленную конфигурацию во временный файл
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_config:
                    yaml.dump(config, temp_config, default_flow_style=False)
                    temp_config_path = temp_config.name
                
                # Загружаем пайплайн из исправленного конфига
                diarization_pipeline = Pipeline.from_pretrained(temp_config_path)
                
                # Удаляем временный файл
                try:
                    os.unlink(temp_config_path)
                except:
                    pass
                
                # Перемещаем на нужное устройство
                if device == "cuda" and torch.cuda.is_available():
                    diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
                
                logger.info("Пайплайн диаризации успешно загружен из локальной конфигурации")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки с локальной конфигурацией: {str(e)}")
                logger.info("Попытка загрузки из HuggingFace...")
                
                # Пытаемся загрузить из HuggingFace
                try:
                    # Получаем токен HuggingFace из переменных окружения
                    hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
                    
                    diarization_pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=hf_token if hf_token else None
                    )
                    
                    # Перемещаем на нужное устройство
                    if device == "cuda" and torch.cuda.is_available():
                        diarization_pipeline = diarization_pipeline.to(torch.device("cuda"))
                    
                    logger.info("Пайплайн диаризации успешно загружен из HuggingFace")
                    
                except Exception as e2:
                    logger.error(f"Ошибка загрузки из HuggingFace: {str(e2)}")
                    if not hf_token:
                        logger.error("Токен HuggingFace не найден. Установите HUGGINGFACE_TOKEN или HF_TOKEN")
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















