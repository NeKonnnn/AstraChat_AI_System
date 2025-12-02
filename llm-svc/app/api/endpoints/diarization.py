import os
import tempfile
import wave
import json
import subprocess
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from app.dependencies.diarization_handler import get_diarization_handler
from app.dependencies.whisperx_handler import get_whisperx_handler
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_audio_to_wav(input_file_path: str, output_file_path: str) -> bool:
    """Конвертирует аудио файл в WAV формат для диаризации"""
    try:
        # Используем ffmpeg для конвертации
        command = [
            "ffmpeg", 
            "-y",  # Перезаписывать существующие файлы
            "-i", input_file_path,  # Входной файл
            "-ar", "16000",  # Частота дискретизации 16 кГц
            "-ac", "1",      # Моно
            "-f", "wav",     # Формат WAV
            output_file_path  # Выходной файл
        ]
        
        logger.info(f"Выполняем команду: {' '.join(command)}")
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Проверяем, создан ли файл
        if not os.path.exists(output_file_path):
            stderr = result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"Не удалось конвертировать аудио. FFmpeg ошибка: {stderr}")
            return False
        
        return True
        
    except FileNotFoundError:
        logger.error("FFmpeg не найден. Пожалуйста, установите FFmpeg и добавьте его в PATH.")
        return False
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode('utf-8', errors='ignore')
        logger.error(f"Ошибка FFmpeg: {stderr}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при конвертации аудио: {str(e)}")
        return False


@router.post("/diarize")
async def diarize_audio(
    file: UploadFile = File(...),
    min_speakers: int = Form(1),
    max_speakers: int = Form(10),
    min_duration: float = Form(1.0)
):
    """
    Диаризация аудио файла (разделение по спикерам)
    
    - **file**: Аудио файл для диаризации
    - **min_speakers**: Минимальное количество спикеров
    - **max_speakers**: Максимальное количество спикеров
    - **min_duration**: Минимальная длительность сегмента (секунды)
    """
    try:
        # Проверяем, включена ли диаризация
        if not settings.diarization.enabled:
            raise HTTPException(status_code=503, detail="Диаризация отключена")
        
        # Проверяем размер файла
        if file.size > settings.diarization.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"Файл слишком большой. Максимальный размер: {settings.diarization.max_file_size} байт"
            )
        
        # Валидация параметров
        if min_speakers < 1:
            raise HTTPException(status_code=400, detail="min_speakers должен быть >= 1")
        if max_speakers < min_speakers:
            raise HTTPException(status_code=400, detail="max_speakers должен быть >= min_speakers")
        if min_duration < 0:
            raise HTTPException(status_code=400, detail="min_duration должен быть >= 0")
        
        # Получаем пайплайн диаризации
        pipeline = await get_diarization_handler()
        if pipeline is None:
            raise HTTPException(status_code=503, detail="Пайплайн диаризации не загружен")
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_file_path = temp_file.name
            
            # Сохраняем загруженный файл
            content = await file.read()
            temp_file.write(content)
        
        try:
            # Конвертируем в WAV если нужно
            wav_file_path = temp_file_path
            if not temp_file_path.lower().endswith('.wav'):
                wav_file_path = temp_file_path + ".wav"
                if not convert_audio_to_wav(temp_file_path, wav_file_path):
                    raise HTTPException(status_code=400, detail="Не удалось конвертировать аудио файл")
            
            # Выполняем диаризацию
            logger.info(f"Начинаем диаризацию файла: {file.filename}")
            diarization = pipeline(
                wav_file_path,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                min_duration=min_duration
            )
            
            # Обрабатываем результаты
            speakers = []
            speaker_segments = {}
            
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                start_time = turn.start
                end_time = turn.end
                duration = end_time - start_time
                
                # Пропускаем слишком короткие сегменты
                if duration < min_duration:
                    continue
                
                speaker_id = f"SPEAKER_{speaker:02d}"
                
                # Добавляем сегмент
                segment = {
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "duration": round(duration, 2),
                    "speaker": speaker_id
                }
                
                speakers.append(segment)
                
                # Группируем по спикерам
                if speaker_id not in speaker_segments:
                    speaker_segments[speaker_id] = []
                speaker_segments[speaker_id].append(segment)
            
            # Статистика
            unique_speakers = len(speaker_segments)
            total_duration = sum(seg["duration"] for seg in speakers)
            
            # Сортируем сегменты по времени
            speakers.sort(key=lambda x: x["start"])
            
            return JSONResponse(content={
                "success": True,
                "speakers_count": unique_speakers,
                "segments_count": len(speakers),
                "total_duration": round(total_duration, 2),
                "segments": speakers,
                "speaker_segments": speaker_segments,
                "parameters": {
                    "min_speakers": min_speakers,
                    "max_speakers": max_speakers,
                    "min_duration": min_duration
                }
            })
                
        finally:
            # Очищаем временные файлы
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                if os.path.exists(wav_file_path) and wav_file_path != temp_file_path:
                    os.unlink(wav_file_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временные файлы: {e}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при диаризации: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при диаризации: {str(e)}")


@router.post("/transcribe_with_diarization")
async def transcribe_with_diarization(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    min_speakers: int = Form(1),
    max_speakers: int = Form(10),
    min_duration: float = Form(1.0)
):
    """
    Комбинированная транскрибация с диаризацией
    
    - **file**: Аудио файл для обработки
    - **language**: Язык для распознавания (ru, en, auto)
    - **min_speakers**: Минимальное количество спикеров
    - **max_speakers**: Максимальное количество спикеров
    - **min_duration**: Минимальная длительность сегмента (секунды)
    """
    try:
        # Проверяем доступность сервисов
        if not settings.whisperx.enabled:
            raise HTTPException(status_code=503, detail="WhisperX отключен")
        if not settings.diarization.enabled:
            raise HTTPException(status_code=503, detail="Диаризация отключена")
        
        # Получаем модели
        whisperx_models = await get_whisperx_handler()
        diarization_pipeline = await get_diarization_handler()
        
        logger.info(f"Модели WhisperX загружены: {list(whisperx_models.keys()) if whisperx_models else 'None'}")
        logger.info(f"Пайплайн диаризации загружен: {diarization_pipeline is not None}")
        
        if not whisperx_models:
            logger.error("Модели WhisperX не загружены при запросе транскрибации")
            raise HTTPException(status_code=503, detail="Модели WhisperX не загружены")
        if diarization_pipeline is None:
            logger.error("Пайплайн диаризации не загружен при запросе транскрибации")
            raise HTTPException(status_code=503, detail="Пайплайн диаризации не загружен")
        
        # Определяем язык
        if language == "auto":
            language = "ru"
        
        logger.info(f"Используемый язык: {language}, доступные языки: {list(whisperx_models.keys())}")
        
        if language not in whisperx_models:
            logger.error(f"Язык {language} не найден в загруженных моделях: {list(whisperx_models.keys())}")
            raise HTTPException(
                status_code=400, 
                detail=f"Неподдерживаемый язык: {language}. Доступные: {list(whisperx_models.keys())}"
            )
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_file_path = temp_file.name
            
            # Сохраняем загруженный файл
            content = await file.read()
            temp_file.write(content)
        
        try:
            # Конвертируем в WAV
            wav_file_path = temp_file_path
            if not temp_file_path.lower().endswith('.wav'):
                wav_file_path = temp_file_path + ".wav"
                if not convert_audio_to_wav(temp_file_path, wav_file_path):
                    raise HTTPException(status_code=400, detail="Не удалось конвертировать аудио файл")
            
            # Импортируем whisperx
            import whisperx
            
            # Загружаем аудио
            audio = whisperx.load_audio(wav_file_path)
            
            # Транскрибируем
            model_info = whisperx_models[language]
            result = model_info["model"].transcribe(audio, language=language)
            
            # Диаризация
            diarization = diarization_pipeline(
                wav_file_path,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                min_duration=min_duration
            )
            
            # Объединяем результаты
            segments = []
            if "segments" in result:
                for segment in result["segments"]:
                    start_time = segment.get("start", 0)
                    end_time = segment.get("end", 0)
                    text = segment.get("text", "").strip()
                    
                    # Находим соответствующий спикер
                    speaker = "UNKNOWN"
                    for turn, _, speaker_id in diarization.itertracks(yield_label=True):
                        if turn.start <= start_time <= turn.end:
                            speaker = f"SPEAKER_{speaker_id:02d}"
                            break
                    
                    segments.append({
                        "start": round(start_time, 2),
                        "end": round(end_time, 2),
                        "duration": round(end_time - start_time, 2),
                        "speaker": speaker,
                        "text": text
                    })
            
            # Полный текст
            full_text = result.get("text", "").strip()
            
            return JSONResponse(content={
                "success": True,
                "text": full_text,
                "language": language,
                "segments": segments,
                "speakers_count": len(set(seg["speaker"] for seg in segments)),
                "total_duration": len(audio) / 16000,
                "words_count": len(full_text.split())
            })
                
        finally:
            # Очищаем временные файлы
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                if os.path.exists(wav_file_path) and wav_file_path != temp_file_path:
                    os.unlink(wav_file_path)
            except Exception as e:
                logger.warning(f"Не удалось удалить временные файлы: {e}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при комбинированной обработке: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке: {str(e)}")


@router.get("/diarization/health")
async def diarization_health_check():
    """Проверка состояния сервиса диаризации"""
    try:
        if not settings.diarization.enabled:
            return JSONResponse(content={
                "status": "disabled",
                "service": "diarization",
                "enabled": False
            })
        
        pipeline = await get_diarization_handler()
        return JSONResponse(content={
            "status": "healthy" if pipeline else "unhealthy",
            "service": "diarization",
            "enabled": True,
            "pipeline_loaded": pipeline is not None
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "diarization",
                "error": str(e)
            }
        )


@router.get("/diarization/info")
async def get_diarization_info():
    """Получение информации о сервисе диаризации"""
    return JSONResponse(content={
        "service": "diarization",
        "enabled": settings.diarization.enabled,
        "device": settings.diarization.device,
        "max_file_size": settings.diarization.max_file_size,
        "min_speakers": settings.diarization.min_speakers,
        "max_speakers": settings.diarization.max_speakers,
        "min_duration": settings.diarization.min_duration
    })















