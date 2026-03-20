"""
routes/transcription.py - транскрибация файлов и YouTube
"""

import asyncio
import concurrent.futures
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

import backend.app_state as state
from backend.app_state import minio_client
from backend.schemas import YouTubeTranscribeRequest

router = APIRouter(prefix="/api/transcribe", tags=["transcription"])
logger = logging.getLogger(__name__)


@router.post("/upload")
async def transcribe_file(file: UploadFile = File(...), request_id: Optional[str] = Form(None)):
    import uuid
    tid = request_id or str(uuid.uuid4())

    if not state.transcriber:
        raise HTTPException(status_code=503, detail="Transcriber не доступен")

    state.stop_transcription_flags[tid] = False
    temp_dir = tempfile.gettempdir()
    file_path = None
    file_object_name = None

    try:
        content = await file.read()
        if minio_client:
            try:
                ext = os.path.splitext(file.filename)[1] if file.filename else ""
                file_object_name = minio_client.generate_object_name(prefix="media_", extension=ext)
                minio_client.upload_file(content, file_object_name, content_type="application/octet-stream")
                file_path = minio_client.get_file_path(file_object_name)
            except Exception as e:
                logger.warning(f"MinIO: {e}")
                file_path = os.path.join(temp_dir, f"media_{datetime.now().timestamp()}_{file.filename}")
                with open(file_path, "wb") as f:
                    f.write(content)
        else:
            file_path = os.path.join(temp_dir, f"media_{datetime.now().timestamp()}_{file.filename}")
            with open(file_path, "wb") as f:
                f.write(content)

        if state.stop_transcription_flags.get(tid, False):
            raise HTTPException(status_code=499, detail="Транскрибация остановлена")

        loop = asyncio.get_event_loop()

        def _transcribe():
            if state.stop_transcription_flags.get(tid, False):
                return False, "Транскрибация была остановлена"
            try:
                if hasattr(state.transcriber, "transcribe_with_diarization"):
                    return state.transcriber.transcribe_with_diarization(file_path)
                return state.transcriber.transcribe_audio_file(file_path)
            except Exception as e:
                return False, str(e)

        with concurrent.futures.ThreadPoolExecutor() as ex:
            success, result = await loop.run_in_executor(ex, _transcribe)

        state.stop_transcription_flags.pop(tid, None)

        if success:
            return {"transcription": result, "filename": file.filename, "success": True,
                    "timestamp": datetime.now().isoformat(), "diarization": True, "transcription_id": tid}
        else:
            if "остановлена" in str(result).lower():
                raise HTTPException(status_code=499, detail=result)
            raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
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


@router.post("/stop")
async def stop_transcription(request: dict):
    tid = request.get("transcription_id")
    if not tid:
        raise HTTPException(status_code=400, detail="transcription_id обязателен")
    state.stop_transcription_flags[tid] = True
    return {"success": True, "message": "Команда остановки отправлена", "transcription_id": tid}


@router.post("/upload/diarization")
async def transcribe_with_diarization(file: UploadFile = File(...)):
    if not state.transcriber:
        raise HTTPException(status_code=503, detail="Transcriber не доступен")
    temp_dir = tempfile.gettempdir()
    file_path = None
    file_object_name = None
    try:
        content = await file.read()
        if minio_client:
            try:
                ext = os.path.splitext(file.filename)[1] if file.filename else ""
                file_object_name = minio_client.generate_object_name(prefix="media_diarization_", extension=ext)
                minio_client.upload_file(content, file_object_name, content_type="application/octet-stream")
                file_path = minio_client.get_file_path(file_object_name)
            except Exception as e:
                logger.warning(f"MinIO: {e}")
                file_path = os.path.join(temp_dir, f"media_diar_{datetime.now().timestamp()}_{file.filename}")
                with open(file_path, "wb") as f:
                    f.write(content)
        else:
            file_path = os.path.join(temp_dir, f"media_diar_{datetime.now().timestamp()}_{file.filename}")
            with open(file_path, "wb") as f:
                f.write(content)

        loop = asyncio.get_event_loop()

        def _tr():
            if hasattr(state.transcriber, "transcribe_with_diarization"):
                return state.transcriber.transcribe_with_diarization(file_path)
            return state.transcriber.transcribe_audio_file(file_path)

        with concurrent.futures.ThreadPoolExecutor() as ex:
            success, result = await loop.run_in_executor(ex, _tr)

        if success:
            return {"transcription": result, "filename": file.filename, "success": True, "diarization": True}
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
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


@router.post("/youtube")
async def transcribe_youtube(request: YouTubeTranscribeRequest):
    if not state.transcriber:
        raise HTTPException(status_code=503, detail="Transcriber не доступен")
    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as ex:
            success, result = await loop.run_in_executor(ex, state.transcriber.transcribe_youtube, request.url)
        if success:
            return {"transcription": result, "url": request.url, "success": True,
                    "timestamp": datetime.now().isoformat(), "diarization": True}
        raise HTTPException(status_code=400, detail=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
