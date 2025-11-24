import os
import tempfile
import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from PIL import Image
from io import BytesIO
from app.dependencies.surya_handler import get_surya_handler
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ocr")
async def recognize_text_from_image(
    file: UploadFile = File(...),
    languages: str = Form("ru,en")  # Список языков через запятую
):
    """
    Распознавание текста с изображения с помощью Surya OCR
    
    - **file**: Изображение для распознавания
    - **languages**: Список языков через запятую (например, "ru,en")
    """
    try:
        # Проверяем, включен ли Surya OCR
        if not settings.surya.enabled:
            raise HTTPException(status_code=503, detail="Surya OCR отключен")
        
        # Проверяем размер файла
        if file.size and file.size > settings.surya.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"Файл слишком большой. Максимальный размер: {settings.surya.max_file_size} байт"
            )
        
        # Получаем handler Surya OCR
        surya = await get_surya_handler()
        if surya is None:
            raise HTTPException(status_code=503, detail="Surya OCR не загружен")
        
        # Читаем файл
        file_data = await file.read()
        
        # Проверяем, что это изображение
        try:
            image = Image.open(BytesIO(file_data))
            # Конвертируем в RGB, если необходимо
            if image.mode != "RGB":
                image = image.convert("RGB")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Не удалось открыть изображение: {str(e)}")
        
        # Парсим языки
        lang_list = [lang.strip() for lang in languages.split(",") if lang.strip()]
        if not lang_list:
            lang_list = ["ru", "en"]  # По умолчанию
        
        # Проверяем поддерживаемые языки
        valid_languages = [lang for lang in lang_list if lang in settings.surya.supported_languages]
        if not valid_languages:
            valid_languages = ["ru", "en"]  # Fallback
        
        logger.info(f"Распознавание текста с изображения. Языки: {valid_languages}")
        
        # Выполняем OCR
        try:
            run_ocr = surya["run_ocr"]
            detection_model = surya["detection_model"]
            detection_processor = surya["detection_processor"]
            recognition_model = surya["recognition_model"]
            recognition_processor = surya["recognition_processor"]
            
            # Запускаем OCR
            predictions = run_ocr(
                [image],
                [valid_languages],
                detection_model,
                detection_processor,
                recognition_model,
                recognition_processor
            )
            
            # Обрабатываем результаты
            if not predictions or len(predictions) == 0:
                return JSONResponse(content={
                    "success": True,
                    "text": "",
                    "languages": valid_languages,
                    "words": [],
                    "words_count": 0,
                    "confidence": 0.0
                })
            
            # Извлекаем текст и информацию о словах
            prediction = predictions[0]
            text_lines = []
            words_with_confidence = []
            total_confidence = 0.0
            word_count = 0
            
            for text_line in prediction.text_lines:
                line_text = text_line.text
                if line_text.strip():
                    text_lines.append(line_text)
                    
                    # Извлекаем слова из строки
                    for word in line_text.split():
                        word_confidence = getattr(text_line, 'confidence', 0.0)
                        if word_confidence == 0.0:
                            # Если нет уверенности на уровне строки, используем среднюю
                            word_confidence = 85.0  # Surya обычно дает хорошие результаты
                        
                        words_with_confidence.append({
                            "word": word,
                            "confidence": float(word_confidence)
                        })
                        total_confidence += word_confidence
                        word_count += 1
            
            # Объединяем строки
            full_text = "\n".join(text_lines)
            
            # Вычисляем среднюю уверенность
            avg_confidence = total_confidence / word_count if word_count > 0 else 0.0
            
            logger.info(f"OCR успешно выполнен. Извлечено {word_count} слов, средняя уверенность: {avg_confidence:.2f}%")
            
            return JSONResponse(content={
                "success": True,
                "text": full_text,
                "languages": valid_languages,
                "words": words_with_confidence,
                "words_count": word_count,
                "confidence": round(avg_confidence, 2)
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка при выполнении OCR: {error_msg}")
            import traceback
            full_traceback = traceback.format_exc()
            logger.error(f"Полный traceback:\n{full_traceback}")
            
            # Возвращаем более информативную ошибку
            error_detail = f"Ошибка при распознавании текста: {error_msg}"
            if "AttributeError" in error_msg or "text_lines" in error_msg:
                error_detail += ". Возможно, формат ответа от Surya OCR изменился."
            elif "CUDA" in error_msg or "device" in error_msg.lower():
                error_detail += ". Проблема с устройством (CPU/GPU)."
            elif "model" in error_msg.lower() or "load" in error_msg.lower():
                error_detail += ". Проблема с загрузкой моделей."
            
            raise HTTPException(status_code=500, detail=error_detail)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обработке OCR запроса: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке запроса: {str(e)}")


@router.get("/ocr/health")
async def ocr_health_check():
    """Проверка состояния сервиса OCR"""
    try:
        if not settings.surya.enabled:
            return JSONResponse(content={
                "status": "disabled",
                "service": "surya-ocr",
                "enabled": False
            })
        
        surya = await get_surya_handler()
        return JSONResponse(content={
            "status": "healthy" if surya else "unhealthy",
            "service": "surya-ocr",
            "enabled": True,
            "model_loaded": surya is not None,
            "models_dir": settings.surya.models_dir,
            "device": surya["device"] if surya else None
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "surya-ocr",
                "error": str(e)
            }
        )


@router.get("/ocr/info")
async def get_ocr_info():
    """Получение информации о сервисе OCR"""
    return JSONResponse(content={
        "service": "surya-ocr",
        "enabled": settings.surya.enabled,
        "supported_formats": ["jpg", "jpeg", "png", "webp", "bmp", "tiff"],
        "max_file_size": settings.surya.max_file_size,
        "supported_languages": settings.surya.supported_languages,
        "device": settings.surya.device,
        "models_dir": settings.surya.models_dir
    })

