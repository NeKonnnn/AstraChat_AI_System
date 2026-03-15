import os
from typing import Optional, Callable, Tuple, List, Dict, Any
import logging
import traceback
import asyncio

# ПРОВЕРКА РЕЖИМА МИКРОСЕРВИСОВ
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

# Импортируем локальные транскрайберы только если НЕ используем сервисы 
if not USE_LLM_SVC:
    try:
        from backend.transcriber import Transcriber
        from backend.whisperx_transcriber import WhisperXTranscriber
        LOCAL_TRANSCRIBERS_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"Локальные транскрайберы недоступны: {e}")
        LOCAL_TRANSCRIBERS_AVAILABLE = False
        Transcriber = None
        WhisperXTranscriber = None
else:
    LOCAL_TRANSCRIBERS_AVAILABLE = False
    Transcriber = None
    WhisperXTranscriber = None
    logging.info("UniversalTranscriber: Режим микросервисов активен")

# Импортируем наши новые сетевые обертки
try:
    from backend.llm_client import (
        transcribe_audio_llm_svc, 
        transcribe_audio_whisperx_llm_svc, 
        transcribe_with_diarization_llm_svc
    )
except ImportError:
    transcribe_audio_llm_svc = None
    transcribe_audio_whisperx_llm_svc = None
    transcribe_with_diarization_llm_svc = None

class UniversalTranscriber:
    """
    Универсальный транскрайбер
    """
    
    def __init__(self, engine: str = "vosk", hf_token: Optional[str] = None):
        # Настройка логирования 
        self.logger = logging.getLogger(f"{__name__}.UniversalTranscriber")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s [Universal] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("=== Инициализация UniversalTranscriber ===")
        
        self.engine = engine.lower()
        self.vosk_transcriber = None
        self.whisperx_transcriber = None
        self.current_transcriber = None
        self.hf_token = hf_token
        
        try:
            self._initialize_engine()
            self.logger.info(f"UniversalTranscriber инициализирован (движок: {self.engine})")
        except Exception as e:
            self.logger.error(f"Критическая ошибка инициализации: {e}")
            raise
    
    def _initialize_engine(self):
        """Инициализирует выбранный движок """
        
        if USE_LLM_SVC:
            self.logger.info(f"[SVC] Работаем через микросервисы (выбран {self.engine})")
            self.current_transcriber = "llm-svc"
            return
        
        if not LOCAL_TRANSCRIBERS_AVAILABLE:
            raise Exception("Локальные модели отсутствуют. Проверьте папки или включите USE_LLM_SVC=true")
        
        if self.engine == "whisperx":
            self.whisperx_transcriber = WhisperXTranscriber()
            self.current_transcriber = self.whisperx_transcriber
        else:
            self.vosk_transcriber = Transcriber()
            self.current_transcriber = self.vosk_transcriber

    def switch_engine(self, engine: str) -> bool:
        """Переключение движка на лету"""
        if engine.lower() == self.engine:
            return True
        
        self.logger.info(f"Переключение движка: {self.engine} -> {engine.lower()}")
        
        if USE_LLM_SVC:
            self.engine = engine.lower()
            return True

        try:
            if engine.lower() == "whisperx":
                if not self.whisperx_transcriber:
                    self.whisperx_transcriber = WhisperXTranscriber()
                self.current_transcriber = self.whisperx_transcriber
            else:
                if not self.vosk_transcriber:
                    self.vosk_transcriber = Transcriber()
                self.current_transcriber = self.vosk_transcriber
            
            self.engine = engine.lower()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка переключения: {e}")
            return False

    def get_current_engine(self) -> str: return self.engine

    def get_available_engines(self) -> list:
        engines = ["vosk"]
        # Если есть whisperx в системе или мы в режиме сервисов
        if USE_LLM_SVC: engines.append("whisperx")
        else:
            try: import whisperx; engines.append("whisperx")
            except: pass
        return engines
    def set_progress_callback(self, callback: Optional[Callable[[int], None]]):
        """Устанавливает callback для обновления прогресса"""
        if USE_LLM_SVC: return # Сервис не поддерживает колбэки прогресса
        if self.current_transcriber and hasattr(self.current_transcriber, 'set_progress_callback'):
            self.current_transcriber.set_progress_callback(callback)
    
    def set_model_size(self, size: str):
        """Устанавливает размер модели"""
        if self.engine == "whisperx" and self.whisperx_transcriber:
            self.whisperx_transcriber.set_model_size(size)

    def set_language(self, lang: str):
        """Устанавливает язык"""
        if self.current_transcriber and hasattr(self.current_transcriber, 'set_language'):
            self.current_transcriber.set_language(lang)
    
    def set_compute_type(self, compute_type: str):
        """Устанавливает тип вычислений"""
        if self.engine == "whisperx" and self.whisperx_transcriber:
            self.whisperx_transcriber.set_compute_type(compute_type)

    def transcribe_audio_file(self, audio_path: str) -> Tuple[bool, str]:
        """Транскрибирует аудио файл"""
        self.logger.info(f"Начало транскрибации: {audio_path}")
        
        # --- РЕЖИМ МИКРОСЕРВИСОВ ---
        if USE_LLM_SVC:
            try:
                self.logger.info(f"[SVC] Запрос к STT-сервису (движок: {self.engine})")
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()
                
                # Используем наши новые синхронные обертки из llm_client
                if self.engine == "whisperx":
                    text = transcribe_audio_whisperx_llm_svc(
                        audio_data, 
                        filename=os.path.basename(audio_path),
                        language="auto"
                    )
                else:
                    text = transcribe_audio_llm_svc(
                        audio_data, 
                        filename=os.path.basename(audio_path),
                        language="ru"
                    )
                
                if text:
                    return True, text
                return False, "Сервис вернул пустой текст"
            except Exception as e:
                self.logger.error(f"[SVC] Ошибка: {e}")
                return False, f"Ошибка микросервиса: {str(e)}"
        
        # --- ЛОКАЛЬНЫЙ РЕЖИМ ---
        if self.whisperx_transcriber:
            try:
                return self.whisperx_transcriber.transcribe_audio_file(audio_path)
            except Exception as e:
                self.logger.error(f"Ошибка WhisperX: {e}")
        
        if self.current_transcriber:
            try:
                if self.engine == "vosk" and self.vosk_transcriber:
                    return self.vosk_transcriber.transcribe_audio(audio_path)
                return self.current_transcriber.transcribe_audio_file(audio_path)
            except Exception as e:
                return False, str(e)
        
        return False, "Транскрайбер не инициализирован"
    
    def transcribe_youtube(self, url: str) -> Tuple[bool, str]:
        """Транскрибирует YouTube"""
        self.logger.info(f"Транскрибация YouTube: {url}")
        
        if USE_LLM_SVC:
            # Для YouTube в режиме SVC мы сначала качаем аудио локально на бэкенд, 
            # а потом шлем файл в сервис.
            self.logger.info("[SVC] YouTube: сначала загружаем аудио локально...")
            # Создаем временный экземпляр для загрузки (или используем старый)
            try:
                from backend.whisperx_transcriber import WhisperXTranscriber as Loader
                loader = Loader()
                audio_path = loader._download_youtube_audio(url)
                if audio_path:
                    res = self.transcribe_audio_file(audio_path)
                    loader.cleanup()
                    return res
                return False, "Не удалось скачать аудио с YouTube"
            except Exception as e:
                return False, f"Ошибка YouTube-SVC: {e}"

        if self.current_transcriber and hasattr(self.current_transcriber, 'transcribe_youtube'):
            return self.current_transcriber.transcribe_youtube(url)
        
        return False, "YouTube транскрибация не поддерживается текущим движком"
    
    def transcribe_with_diarization(self, audio_path: str) -> Tuple[bool, str]:
        """Принудительная диаризация"""
        self.logger.info(f"Запрос диаризации: {audio_path}")
        
        if USE_LLM_SVC:
            try:
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()
                # Используем обертку из llm_client
                result = transcribe_with_diarization_llm_svc(
                    audio_data, 
                    filename=os.path.basename(audio_path),
                    language="auto",
                    engine=self.engine
                )
                if result.get("success"):
                    # Сегменты содержат speaker, назначенный оркестратором.
                    # Смежные сегменты одного спикера объединяем в один блок.
                    segments = sorted(result.get("segments", []), key=lambda s: s.get("start", 0))
                    if segments:
                        lines = []  # [(speaker, text)]
                        for seg in segments:
                            speaker = seg.get("speaker", "SPEAKER_?")
                            seg_text = (seg.get("text") or "").strip()
                            if not seg_text:
                                continue
                            if lines and lines[-1][0] == speaker:
                                lines[-1] = (speaker, lines[-1][1] + " " + seg_text)
                            else:
                                lines.append((speaker, seg_text))
                        if lines:
                            return True, "\n".join(f"{spk}: {txt}" for spk, txt in lines)
                    return False, "Сервис вернул пустые сегменты"
                return False, result.get("error", "Unknown error")
            except Exception as e:
                return False, str(e)

        if self.whisperx_transcriber:
            return self.whisperx_transcriber.transcribe_audio_file(audio_path)
        
        return False, "Диаризация доступна только через WhisperX или микросервис"
    
    def get_engine_info(self) -> dict:
        """Информация о движке"""
        info = {"current_engine": self.engine, "available_engines": self.get_available_engines(), "features": {}}
        if self.engine == "whisperx":
            info["features"] = {"diarization": True, "gpu_support": True}
        elif self.engine == "vosk":
            info["features"] = {"diarization": False, "gpu_support": False}
        return info
    
    def set_hf_token(self, token: str):
        self.hf_token = token
        if self.whisperx_transcriber: self.whisperx_transcriber.set_hf_token(token)
    
    def get_hf_token(self) -> Optional[str]: return self.hf_token
    
    def cleanup(self):
        if self.vosk_transcriber: self.vosk_transcriber.cleanup()
        if self.whisperx_transcriber: self.whisperx_transcriber.cleanup()
    
    def __del__(self): self.cleanup()