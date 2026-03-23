"""
backend/transcription/ — подсистема транскрипции речи и голоса

Структура:
    transcriber.py            — Vosk-based Transcriber
    whisperx_transcriber.py   — WhisperX-based WhisperXTranscriber
    universal_transcriber.py  — UniversalTranscriber (фасад, выбирает движок)
    voice.py                  — speak_text, recognize_speech и вспомогательные функции
"""

from backend.transcription.universal_transcriber import UniversalTranscriber
from backend.transcription.transcriber import Transcriber
from backend.transcription.whisperx_transcriber import WhisperXTranscriber

__all__ = ["UniversalTranscriber", "Transcriber", "WhisperXTranscriber"]
