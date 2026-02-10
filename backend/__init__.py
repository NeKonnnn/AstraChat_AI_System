# Backend package for astrachat

# Экспорт основных классов для упрощения импорта
try:
    from backend.universal_transcriber import UniversalTranscriber
except ImportError:
    UniversalTranscriber = None

try:
    from backend.whisperx_transcriber import WhisperXTranscriber
except ImportError:
    WhisperXTranscriber = None

try:
    from backend.transcriber import Transcriber
except ImportError:
    Transcriber = None

try:
    from backend.document_processor import DocumentProcessor
except ImportError:
    DocumentProcessor = None

try:
    from backend.voice import *
except ImportError:
    pass

try:
    from backend.agent_llm_svc import *
except ImportError:
    pass

try:
    from backend.capture_remote_audio import *
except ImportError:
    pass

__all__ = [
    'UniversalTranscriber',
    'WhisperXTranscriber', 
    'Transcriber',
    'DocumentProcessor'
]
