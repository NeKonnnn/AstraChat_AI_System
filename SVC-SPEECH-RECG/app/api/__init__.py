# SVC-SPEECH-RECG/app/api/__init__.py
from fastapi import APIRouter
from .endpoints import whisperx

router = APIRouter()

# WhisperX: /v1/whisperx/transcribe
router.include_router(whisperx.router, prefix="/whisperx")