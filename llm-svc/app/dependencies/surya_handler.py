import os
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения инициализированного surya OCR
surya_ocr = None


async def get_surya_handler():
    """Получение экземпляра Surya OCR"""
    global surya_ocr
    
    if not settings.surya.enabled:
        logger.info("Surya OCR отключен в конфигурации")
        return None
    
    if surya_ocr is None:
        try:
            logger.info(f"Инициализация Surya OCR с моделями из {settings.surya.models_dir}")
            
            # Проверяем существование директории с моделями
            if not os.path.exists(settings.surya.models_dir):
                logger.warning(f"Директория с моделями Surya не найдена в {settings.surya.models_dir}")
                return None
            
            # Импортируем surya OCR
            try:
                from surya.ocr import run_ocr
                from surya.model.detection.model import load_model as load_detection_model
                from surya.model.detection.processor import load_processor as load_detection_processor
                from surya.model.recognition.model import load_model as load_recognition_model
                from surya.model.recognition.processor import load_processor as load_recognition_processor
            except ImportError:
                # Пробуем альтернативные пути импорта
                try:
                    from surya.ocr import run_ocr
                    from surya.model.detection import load_model as load_detection_model, load_processor as load_detection_processor
                    from surya.model.recognition import load_model as load_recognition_model, load_processor as load_recognition_processor
                except ImportError as e:
                    logger.error(f"Surya OCR не установлен. Установите: pip install surya-ocr. Ошибка: {e}")
                    return None
            
            # Определяем устройство
            device = settings.surya.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            
            logger.info(f"Используется устройство: {device}")
            
            # Загружаем модели
            # Surya OCR автоматически загружает модели из кэша или из указанной директории
            # Структура должна быть: models_dir/text_detection/... и models_dir/text_recognition/...
            # Если models_dir указан и содержит правильную структуру, модели будут загружены оттуда
            # Иначе surya-ocr использует кэш ~/.cache/datalab
            
            # Проверяем наличие правильной структуры
            text_detection_path = os.path.join(settings.surya.models_dir, "text_detection")
            text_recognition_path = os.path.join(settings.surya.models_dir, "text_recognition")
            
            has_local_models = os.path.exists(text_detection_path) and os.path.exists(text_recognition_path)
            
            if has_local_models:
                logger.info(f"Найдены локальные модели в {settings.surya.models_dir}")
                logger.info(f"  Detection: {text_detection_path}")
                logger.info(f"  Recognition: {text_recognition_path}")
                # Устанавливаем переменную окружения для указания пути к моделям
                # Surya OCR использует DATALAB_CACHE_DIR для поиска моделей
                os.environ["DATALAB_CACHE_DIR"] = settings.surya.models_dir
            
            try:
                # Пробуем загрузить модели (surya-ocr сам найдет их в указанной директории или кэше)
                detection_model = load_detection_model(device=device)
                detection_processor = load_detection_processor()
                recognition_model = load_recognition_model(device=device)
                recognition_processor = load_recognition_processor()
                logger.info("✓ Модели Surya OCR успешно загружены")
            except Exception as e:
                logger.error(f"Ошибка загрузки моделей Surya OCR: {e}")
                logger.info("Попробуем загрузить с явным указанием директории...")
                # Попробуем загрузить с указанием директории (если API поддерживает)
                try:
                    # Некоторые версии surya-ocr могут поддерживать model_dir параметр
                    detection_model = load_detection_model(device=device, model_dir=settings.surya.models_dir)
                    detection_processor = load_detection_processor(model_dir=settings.surya.models_dir)
                    recognition_model = load_recognition_model(device=device, model_dir=settings.surya.models_dir)
                    recognition_processor = load_recognition_processor(model_dir=settings.surya.models_dir)
                    logger.info("✓ Модели Surya OCR загружены с указанием директории")
                except Exception as e2:
                    logger.error(f"Ошибка загрузки моделей Surya OCR из {settings.surya.models_dir}: {e2}")
                    logger.info("Surya OCR будет использовать модели из кэша ~/.cache/datalab")
                    # Пробуем загрузить из кэша (без указания директории)
                    try:
                        detection_model = load_detection_model(device=device)
                        detection_processor = load_detection_processor()
                        recognition_model = load_recognition_model(device=device)
                        recognition_processor = load_recognition_processor()
                        logger.info("✓ Модели Surya OCR загружены из кэша")
                    except Exception as e3:
                        logger.error(f"Не удалось загрузить модели ни из локальной директории, ни из кэша: {e3}")
                        return None
            
            # Сохраняем в глобальной переменной
            surya_ocr = {
                "detection_model": detection_model,
                "detection_processor": detection_processor,
                "recognition_model": recognition_model,
                "recognition_processor": recognition_processor,
                "device": device,
                "run_ocr": run_ocr
            }
            
            logger.info("Surya OCR успешно инициализирован")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации Surya OCR: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    return surya_ocr


async def cleanup_surya_handler():
    """Очистка ресурсов Surya OCR"""
    global surya_ocr
    
    if surya_ocr is not None:
        logger.info("Освобождение ресурсов Surya OCR")
        # Очищаем модели из памяти
        if "detection_model" in surya_ocr:
            del surya_ocr["detection_model"]
        if "recognition_model" in surya_ocr:
            del surya_ocr["recognition_model"]
        surya_ocr = None

