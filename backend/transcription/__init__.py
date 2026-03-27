"""
backend/transcription/ — подсистема транскрипции речи и голоса

Структура:
    whisperx_transcriber.py   — WhisperXTranscriber
    universal_transcriber.py  — UniversalTranscriber (фасад)
    voice.py                  — speak_text, recognize_speech и вспомогательные функции
"""

from backend.transcription.universal_transcriber import UniversalTranscriber
from backend.transcription.whisperx_transcriber import WhisperXTranscriber

__all__ = ["UniversalTranscriber", "WhisperXTranscriber"]
