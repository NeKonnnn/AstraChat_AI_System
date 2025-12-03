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
    from backend.system_audio import SystemAudioRecorder
except ImportError:
    SystemAudioRecorder = None

try:
    from backend.system_audio_capture import WasapiLoopbackCapture
except ImportError:
    WasapiLoopbackCapture = None

try:
    from backend.voice import *
except ImportError:
    pass

try:
    from backend.agent import *
except ImportError:
    pass

try:
    from backend.online_transcription import OnlineTranscriber
except ImportError:
    OnlineTranscriber = None

try:
    from backend.capture_remote_audio import *
except ImportError:
    pass

try:
    from backend.memory import *
except ImportError:
    pass

__all__ = [
    'UniversalTranscriber',
    'WhisperXTranscriber', 
    'Transcriber',
    'DocumentProcessor',
    'SystemAudioRecorder',
    'WasapiLoopbackCapture',
    'OnlineTranscriber'
]
