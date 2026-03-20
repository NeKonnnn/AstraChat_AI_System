"""
routes/voice.py - синтез речи, распознавание, настройки транскрибации
"""

import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import backend.app_state as state
from backend.app_state import speak_text, recognize_speech_from_file, minio_client, save_app_settings
from backend.schemas import VoiceSettings, VoiceSynthesizeRequest, TranscriptionSettings

router = APIRouter(tags=["voice"])
logger = logging.getLogger(__name__)


@router.post("/api/voice/synthesize")
async def synthesize_speech(request: VoiceSynthesizeRequest):
    if not speak_text:
        raise HTTPException(status_code=503, detail="Модуль синтеза речи недоступен.")
    temp_dir = tempfile.gettempdir()
    audio_file = os.path.join(temp_dir, f"speech_{datetime.now().timestamp()}.wav")
    try:
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            lambda: speak_text(
                text=request.text, speaker=request.voice_speaker,
                voice_id=request.voice_id, speech_rate=request.speech_rate, save_to_file=audio_file,
            ),
        )
        if success and os.path.exists(audio_file):
            if minio_client:
                try:
                    with open(audio_file, "rb") as f:
                        minio_client.upload_file(
                            f.read(),
                            minio_client.generate_object_name(prefix="speech_", extension=".wav"),
                            content_type="audio/wav",
                        )
                except Exception as e:
                    logger.warning(f"MinIO upload failed: {e}")
            temp_copy = os.path.join(temp_dir, f"speech_copy_{datetime.now().timestamp()}.wav")
            shutil.copy2(audio_file, temp_copy)

            async def _cleanup():
                try:
                    if os.path.exists(temp_copy):
                        os.remove(temp_copy)
                except Exception:
                    pass

            return FileResponse(temp_copy, media_type="audio/wav", filename="speech.wav", background=_cleanup)
        raise HTTPException(status_code=500, detail="Не удалось создать аудиофайл")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception:
            pass


@router.post("/api/voice/recognize")
async def recognize_speech_api(audio_file: UploadFile = File(...)):
    if not recognize_speech_from_file:
        return {"text": "", "success": False, "error": "Модуль распознавания речи недоступен."}
    temp_dir = tempfile.gettempdir()
    file_path = None
    file_object_name = None
    try:
        content = await audio_file.read()
        if minio_client:
            try:
                file_object_name = minio_client.generate_object_name(prefix="audio_", extension=".wav")
                minio_client.upload_file(content, file_object_name, content_type="audio/wav")
                file_path = minio_client.get_file_path(file_object_name)
            except Exception as e:
                logger.warning(f"MinIO: {e}")
                file_path = os.path.join(temp_dir, f"audio_{datetime.now().timestamp()}.wav")
                with open(file_path, "wb") as f:
                    f.write(content)
        else:
            file_path = os.path.join(temp_dir, f"audio_{datetime.now().timestamp()}.wav")
            with open(file_path, "wb") as f:
                f.write(content)

        text = recognize_speech_from_file(file_path)
        return {"text": text, "success": True, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            if minio_client and file_object_name:
                try:
                    minio_client.delete_file(file_object_name)
                except Exception:
                    pass
        except Exception:
            pass


@router.get("/api/voice/settings")
async def get_voice_settings():
    return {"voice_id": "ru", "speech_rate": 1.0, "voice_speaker": "baya"}


@router.put("/api/voice/settings")
async def update_voice_settings(settings_data: VoiceSettings):
    return {"message": "Настройки обновлены", "success": True, "settings": settings_data.dict()}


@router.get("/api/transcription/settings")
async def get_transcription_settings():
    return {
        "engine": state.current_transcription_engine,
        "language": state.current_transcription_language,
        "auto_detect": True,
    }


@router.put("/api/transcription/settings")
async def update_transcription_settings(settings_data: TranscriptionSettings):
    try:
        if settings_data.engine:
            state.current_transcription_engine = settings_data.engine.lower()
            if state.transcriber and hasattr(state.transcriber, "switch_engine"):
                state.transcriber.switch_engine(state.current_transcription_engine)
        if settings_data.language:
            state.current_transcription_language = settings_data.language
            if state.transcriber and hasattr(state.transcriber, "set_language"):
                state.transcriber.set_language(state.current_transcription_language)
        save_app_settings({
            "transcription_engine": state.current_transcription_engine,
            "transcription_language": state.current_transcription_language,
        })
        return {"message": "Настройки обновлены", "success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
