import os
import tempfile
import wave
import json
import subprocess
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from vosk import KaldiRecognizer
from app.dependencies.vosk_handler import get_vosk_handler
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_audio_to_wav(input_file_path: str, output_file_path: str) -> bool:
    """Конвертирует аудио файл в WAV формат 16kHz моно"""
    try:
        # Используем ffmpeg для конвертации
        command = [
            "ffmpeg", 
            "-y",  # Перезаписывать существующие файлы
            "-i", input_file_path,  # Входной файл
            "-ar", str(settings.vosk.sample_rate),  # Частота дискретизации
            "-ac", "1",      # Моно
            "-bits_per_raw_sample", "16",  # 16 бит
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


def is_wav_16khz_mono(file_path: str) -> bool:
    """Проверяет, соответствует ли WAV файл требованиям 16кГц, моно"""
    try:
        if not file_path.lower().endswith('.wav'):
            return False
            
        with wave.open(file_path, 'rb') as wf:
            is_valid = (wf.getnchannels() == 1 and wf.getframerate() == settings.vosk.sample_rate)
            return is_valid
    except:
        return False


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("ru")
):
    """
    Транскрибация аудио файла
    
    - **file**: Аудио файл для транскрибации
    - **language**: Язык для распознавания (ru, en)
    """
    try:
        # Проверяем, включен ли Vosk
        if not settings.vosk.enabled:
            raise HTTPException(status_code=503, detail="Vosk транскрипция отключена")
        
        # Проверяем размер файла
        if file.size > settings.vosk.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"Файл слишком большой. Максимальный размер: {settings.vosk.max_file_size} байт"
            )
        
        # Получаем модель Vosk
        model = await get_vosk_handler()
        if model is None:
            raise HTTPException(status_code=503, detail="Модель Vosk не загружена")
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_file_path = temp_file.name
            
            # Сохраняем загруженный файл
            content = await file.read()
            temp_file.write(content)
        
        try:
            # Конвертируем в WAV если нужно
            wav_file_path = temp_file_path
            if not is_wav_16khz_mono(temp_file_path):
                wav_file_path = temp_file_path + ".wav"
                if not convert_audio_to_wav(temp_file_path, wav_file_path):
                    raise HTTPException(status_code=400, detail="Не удалось конвертировать аудио файл")
            
            # Открываем WAV файл
            with wave.open(wav_file_path, "rb") as wf:
                # Проверяем параметры аудио
                channels = wf.getnchannels()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                
                logger.info(f"Параметры WAV файла: каналы={channels}, частота={framerate}, "
                          f"сэмплов={nframes}, длительность={nframes/framerate:.2f} сек")
                
                # Создаем распознаватель
                rec = KaldiRecognizer(model, framerate)
                
                # Собираем результаты транскрибации
                result_text = []
                
                # Читаем аудио по частям и распознаем
                buffer_size = 40000  # Увеличиваем размер буфера для ускорения
                total_frames = nframes
                processed_frames = 0
                
                while True:
                    data = wf.readframes(buffer_size)
                    if len(data) == 0:
                        break
                    
                    processed_frames += buffer_size
                    
                    # Отправляем данные в распознаватель
                    if rec.AcceptWaveform(data):
                        part_result = json.loads(rec.Result())
                        if 'text' in part_result and part_result['text'].strip():
                            result_text.append(part_result['text'])
                
                # Получаем финальный результат
                part_result = json.loads(rec.FinalResult())
                if 'text' in part_result and part_result['text'].strip():
                    result_text.append(part_result['text'])
                
                # Объединяем результаты
                full_text = " ".join(result_text).strip()
                
                if not full_text:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": "Не удалось распознать текст в аудио (пустой результат)"
                        }
                    )
                
                return JSONResponse(content={
                    "success": True,
                    "text": full_text,
                    "language": language,
                    "duration": nframes / framerate,
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
        logger.error(f"Ошибка при транскрибации: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при транскрибации: {str(e)}")


@router.get("/transcription/health")
async def transcription_health_check():
    """Проверка состояния сервиса транскрипции"""
    try:
        if not settings.vosk.enabled:
            return JSONResponse(content={
                "status": "disabled",
                "service": "vosk-transcription",
                "enabled": False
            })
        
        model = await get_vosk_handler()
        return JSONResponse(content={
            "status": "healthy" if model else "unhealthy",
            "service": "vosk-transcription",
            "enabled": True,
            "model_loaded": model is not None
        })
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "vosk-transcription",
                "error": str(e)
            }
        )


@router.get("/transcription/info")
async def get_transcription_info():
    """Получение информации о сервисе транскрипции"""
    return JSONResponse(content={
        "service": "vosk-transcription",
        "enabled": settings.vosk.enabled,
        "supported_formats": ["wav", "mp3", "mp4", "avi", "mov", "mkv", "webm"],
        "sample_rate": settings.vosk.sample_rate,
        "max_file_size": settings.vosk.max_file_size,
        "supported_languages": settings.vosk.supported_languages
    })






