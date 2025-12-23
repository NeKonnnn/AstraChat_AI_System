import os
import tempfile
import subprocess
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from app.dependencies.diarization_handler import get_diarization_handler
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# ВОТ ОНА - ПЕРЕМЕННАЯ, КОТОРУЮ НЕ МОЖЕТ НАЙТИ MAIN.PY
router = APIRouter()

def convert_audio_to_wav(input_file_path: str, output_file_path: str) -> bool:
    """Конвертирует аудио/видео файл в WAV 16kHz mono"""
    try:
        command = [
            "ffmpeg", "-y",
            "-i", input_file_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            output_file_path
        ]
        
        # Если файл видео - убираем картинку
        video_ext = ('.mp4', '.avi', '.mov', '.mkv', '.webm')
        if input_file_path.lower().endswith(video_ext):
            command.insert(3, "-vn")

        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return os.path.exists(output_file_path)
    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        return False

@router.post("/diarize")
async def diarize_audio(
    file: UploadFile = File(...),
    min_speakers: int = Form(1),
    max_speakers: int = Form(10),
    min_duration: float = Form(0.5)
):
    try:
        if not settings.diarization.enabled:
            raise HTTPException(status_code=503, detail="Service disabled")

        pipeline = await get_diarization_handler()
        if pipeline is None:
            raise HTTPException(status_code=503, detail="Pipeline not loaded")

        # Сохраняем входящий файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_path = temp_file.name
            temp_file.write(await file.read())
        
        wav_path = temp_path + ".wav"
        
        try:
            # Конвертация
            if not convert_audio_to_wav(temp_path, wav_path):
                raise HTTPException(status_code=400, detail="Conversion failed")

            # ЗАПУСК МОДЕЛИ
            logger.info(f"Start diarization: {file.filename}")
            diarization = pipeline(
                wav_path,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

            # Формируем ответ
            segments = []
            speaker_segments = {}

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                duration = turn.end - turn.start
                if duration < min_duration:
                    continue
                
                speaker_id = f"SPEAKER_{speaker}"
                seg_data = {
                    "start": round(turn.start, 2),
                    "end": round(turn.end, 2),
                    "duration": round(duration, 2),
                    "speaker": speaker_id
                }
                
                segments.append(seg_data)
                
                if speaker_id not in speaker_segments:
                    speaker_segments[speaker_id] = []
                speaker_segments[speaker_id].append(seg_data)

            segments.sort(key=lambda x: x["start"])
            
            return JSONResponse({
                "success": True,
                "segments": segments,
                "speaker_segments": speaker_segments,
                "total_segments": len(segments)
            })

        finally:
            # Чистим мусор
            for p in [temp_path, wav_path]:
                if os.path.exists(p):
                    try: os.unlink(p)
                    except: pass

    except Exception as e:
        logger.error(f"Diarization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diarization/health")
async def diarization_health_check():
    pipeline = await get_diarization_handler()
    return {"status": "healthy" if pipeline else "unhealthy"}

@router.get("/diarization/info")
async def get_diarization_info():
    return {"status": "ok", "service": "diarization"}