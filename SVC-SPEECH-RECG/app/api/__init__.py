# SVC-SPEECH-RECG/app/api/__init__.py
from fastapi import APIRouter
from .endpoints import transcription, whisperx

router = APIRouter()

# Vosk будет доступен по /v1/transcribe
router.include_router(transcription.router) 

# WhisperX будет доступен по /v1/whisperx/transcribe
# ВАЖНО: здесь добавляем префикс /whisperx
router.include_router(whisperx.router, prefix="/whisperx")