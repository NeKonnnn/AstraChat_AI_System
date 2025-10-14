import os
from typing import Optional, Callable, Tuple
import logging
import traceback
from backend.transcriber import Transcriber
from backend.whisperx_transcriber import WhisperXTranscriber

class UniversalTranscriber:
    """
    Универсальный транскрайбер, который может переключаться между Vosk и WhisperX
    """
    
    def __init__(self, engine: str = "vosk", hf_token: Optional[str] = None):
        """
        Инициализация транскрайбера
        
        Args:
            engine: Движок транскрипции ("vosk" или "whisperx")
            hf_token: Токен Hugging Face для WhisperX диаризации
        """
        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.UniversalTranscriber")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s [Universal] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("=== Инициализация UniversalTranscriber ===")
        
        self.engine = engine.lower()
        self.logger.info(f"Выбран движок транскрипции: {self.engine}")
        
        self.vosk_transcriber = None
        self.whisperx_transcriber = None
        self.current_transcriber = None
        self.hf_token = hf_token
        
        # Инициализируем выбранный движок
        try:
            self.logger.info("Инициализация выбранного движка...")
            self._initialize_engine()
            self.logger.info("UniversalTranscriber успешно инициализирован")
        except Exception as e:
            self.logger.error(f"Ошибка при инициализации UniversalTranscriber: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _initialize_engine(self):
        """Инициализирует выбранный движок транскрипции"""
        try:
            if self.engine == "whisperx":
                self.logger.info("Инициализация WhisperX...")
                try:
                    self.whisperx_transcriber = WhisperXTranscriber()
                    self.current_transcriber = self.whisperx_transcriber
                    self.logger.info("WhisperX инициализирован успешно")
                except Exception as whisper_error:
                    self.logger.error(f"Ошибка инициализации WhisperX: {whisper_error}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    # Не делаем fallback на Vosk - WhisperX нужен для диаризации
                    raise Exception(f"WhisperX необходим для диаризации по ролям. Ошибка: {whisper_error}")
            else:
                self.logger.info("Инициализация Vosk...")
                try:
                    self.vosk_transcriber = Transcriber()
                    self.current_transcriber = self.vosk_transcriber
                    self.logger.info("Vosk инициализирован успешно")
                except Exception as vosk_error:
                    self.logger.error(f"Ошибка инициализации Vosk: {vosk_error}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
        except Exception as e:
            self.logger.error(f"Ошибка инициализации {self.engine}: {e}")
            # Убираем fallback логику - если WhisperX не работает, транскрайбер не будет работать
            raise
    
    def switch_engine(self, engine: str) -> bool:
        """
        Переключает движок транскрипции
        
        Args:
            engine: Новый движок ("vosk" или "whisperx")
            
        Returns:
            True если переключение прошло успешно
        """
        if engine.lower() == self.engine:
            self.logger.debug(f"Движок {engine} уже активен")
            return True
        
        # Предупреждение о потере диаризации при переключении на Vosk
        if engine.lower() == "vosk":
            self.logger.warning("⚠️ Внимание: Vosk не поддерживает диаризацию по ролям!")
            self.logger.warning("Для диаризации рекомендуется использовать WhisperX")
        
        self.logger.info(f"Переключение движка с {self.engine} на {engine.lower()}")
        
        try:
            if engine.lower() == "whisperx":
                if self.whisperx_transcriber is None:
                    self.logger.info("Создание нового экземпляра WhisperX...")
                    self.whisperx_transcriber = WhisperXTranscriber()
                self.current_transcriber = self.whisperx_transcriber
                self.engine = "whisperx"
                self.logger.info("Переключено на WhisperX")
                return True
            elif engine.lower() == "vosk":
                if self.vosk_transcriber is None:
                    self.logger.info("Создание нового экземпляра Vosk...")
                    self.vosk_transcriber = Transcriber()
                self.current_transcriber = self.vosk_transcriber
                self.engine = "vosk"
                self.logger.info("Переключено на Vosk")
                return True
            else:
                self.logger.error(f"Неизвестный движок: {engine}")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка переключения на {engine}: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_current_engine(self) -> str:
        """Возвращает текущий движок"""
        return self.engine
    
    def get_available_engines(self) -> list:
        """Возвращает список доступных движков"""
        engines = ["vosk"]
        
        # Проверяем доступность WhisperX
        try:
            import whisperx
            import torch
            engines.append("whisperx")
        except ImportError:
            pass
        
        return engines
    
    def set_progress_callback(self, callback: Optional[Callable[[int], None]]):
        """Устанавливает callback для обновления прогресса"""
        if self.current_transcriber:
            self.current_transcriber.set_progress_callback(callback)
    
    def set_model_size(self, size: str):
        """Устанавливает размер модели (только для WhisperX)"""
        if self.engine == "whisperx" and self.whisperx_transcriber:
            self.whisperx_transcriber.set_model_size(size)
        elif self.engine == "vosk" and self.vosk_transcriber:
            # Для Vosk размер модели не применим
            print("Размер модели не применим для Vosk")
    
    def set_language(self, lang: str):
        """Устанавливает язык для транскрипции"""
        if self.current_transcriber:
            self.current_transcriber.set_language(lang)
    
    def set_compute_type(self, compute_type: str):
        """Устанавливает тип вычислений (только для WhisperX)"""
        if self.engine == "whisperx" and self.whisperx_transcriber:
            self.whisperx_transcriber.set_compute_type(compute_type)
        elif self.engine == "vosk":
            print("Тип вычислений не применим для Vosk")
    
    def transcribe_audio_file(self, audio_path: str) -> Tuple[bool, str]:
        """Транскрибирует аудио файл"""
        self.logger.info(f"Начало транскрибации аудио файла: {audio_path}")
        self.logger.debug(f"Используется движок: {self.engine}")
        
        # Приоритет диаризации: всегда используем WhisperX если он доступен
        if self.whisperx_transcriber:
            self.logger.info("Используем WhisperX для диаризации по ролям...")
            try:
                result = self.whisperx_transcriber.transcribe_audio_file(audio_path)
                if result[0]:
                    self.logger.info("Транскрибация с диаризацией завершена успешно")
                else:
                    self.logger.error(f"Ошибка транскрибации с диаризацией: {result[1]}")
                return result
            except Exception as e:
                self.logger.error(f"Ошибка WhisperX транскрибации: {e}")
                # Fallback на текущий движок только если WhisperX полностью не работает
                self.logger.warning("Fallback на текущий движок...")
        
        # Fallback на текущий движок
        if self.current_transcriber:
            try:
                # Вызываем правильный метод в зависимости от движка
                if self.engine == "whisperx" and self.whisperx_transcriber:
                    result = self.whisperx_transcriber.transcribe_audio_file(audio_path)
                elif self.engine == "vosk" and self.vosk_transcriber:
                    result = self.vosk_transcriber.transcribe_audio(audio_path)
                else:
                    # Fallback на текущий транскрайбер
                    if hasattr(self.current_transcriber, 'transcribe_audio_file'):
                        result = self.current_transcriber.transcribe_audio_file(audio_path)
                    elif hasattr(self.current_transcriber, 'transcribe_audio'):
                        result = self.current_transcriber.transcribe_audio(audio_path)
                    else:
                        return False, f"Транскрайбер {self.engine} не поддерживает транскрибацию файлов"
                
                if result[0]:
                    self.logger.info("Транскрибация аудио файла завершена успешно")
                else:
                    self.logger.error(f"Ошибка транскрибации: {result[1]}")
                return result
            except Exception as e:
                self.logger.error(f"Исключение при транскрибации аудио файла: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                return False, f"Ошибка транскрибации: {e}"
        else:
            self.logger.error("Транскрайбер не инициализирован")
            return False, "Транскрайбер не инициализирован"
    
    def transcribe_youtube(self, url: str) -> Tuple[bool, str]:
        """Транскрибирует аудио с YouTube"""
        self.logger.info(f"Начало транскрибации YouTube видео: {url}")
        self.logger.debug(f"Используется движок: {self.engine}")
        
        if self.current_transcriber:
            try:
                # Вызываем правильный метод в зависимости от движка
                if self.engine == "whisperx" and self.whisperx_transcriber:
                    result = self.whisperx_transcriber.transcribe_youtube(url)
                elif self.engine == "vosk" and self.vosk_transcriber:
                    result = self.vosk_transcriber.transcribe_youtube(url)
                else:
                    # Fallback на текущий транскрайбер
                    if hasattr(self.current_transcriber, 'transcribe_youtube'):
                        result = self.current_transcriber.transcribe_youtube(url)
                    else:
                        return False, f"Транскрайбер {self.engine} не поддерживает YouTube транскрибацию"
                
                if result[0]:
                    self.logger.info("Транскрибация YouTube видео завершена успешно")
                else:
                    self.logger.error(f"Ошибка транскрибации YouTube: {result[1]}")
                return result
            except Exception as e:
                self.logger.error(f"Исключение при транскрибации YouTube: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                return False, f"Ошибка транскрибации YouTube: {e}"
        else:
            self.logger.error("Транскрайбер не инициализирован")
            return False, "Транскрайбер не инициализирован"
    
    def transcribe_with_diarization(self, audio_path: str) -> Tuple[bool, str]:
        """
        Принудительно транскрибирует аудио файл с диаризацией используя WhisperX
        
        Args:
            audio_path: Путь к аудио файлу
            
        Returns:
            Tuple[bool, str]: (успех, результат или ошибка)
        """
        self.logger.info(f"Принудительная транскрибация с диаризацией: {audio_path}")
        
        if not self.whisperx_transcriber:
            self.logger.error("WhisperX недоступен для диаризации")
            return False, "WhisperX недоступен для диаризации по ролям"
        
        try:
            self.logger.info("Используем WhisperX для диаризации по ролям...")
            result = self.whisperx_transcriber.transcribe_audio_file(audio_path)
            
            if result[0]:
                self.logger.info("Диаризация с WhisperX завершена успешно")
            else:
                self.logger.error(f"Ошибка диаризации с WhisperX: {result[1]}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка диаризации с WhisperX: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"Ошибка диаризации: {e}"
    
    def get_engine_info(self) -> dict:
        """Возвращает информацию о текущем движке"""
        info = {
            "current_engine": self.engine,
            "available_engines": self.get_available_engines(),
            "features": {}
        }
        
        if self.engine == "whisperx":
            info["features"] = {
                "diarization": True,
                "high_accuracy": True,
                "multiple_languages": True,
                "gpu_support": True,
                "model_sizes": ["tiny", "base", "small", "medium", "large", "large-v2"]
            }
        elif self.engine == "vosk":
            info["features"] = {
                "diarization": False,
                "high_accuracy": False,
                "multiple_languages": True,
                "gpu_support": False,
                "model_sizes": ["small", "medium", "large"]
            }
        
        return info
    
    def set_hf_token(self, token: str):
        """Устанавливает токен Hugging Face для WhisperX"""
        self.hf_token = token
        self.logger.info("Токен Hugging Face обновлен")
        
        # Обновляем токен в WhisperX транскрайбере если он инициализирован
        if self.whisperx_transcriber:
            self.whisperx_transcriber.set_hf_token(token)
    
    def get_hf_token(self) -> Optional[str]:
        """Возвращает текущий токен Hugging Face"""
        return self.hf_token
    
    def cleanup(self):
        """Очищает ресурсы"""
        if self.vosk_transcriber:
            self.vosk_transcriber.cleanup()
        if self.whisperx_transcriber:
            self.whisperx_transcriber.cleanup()
    
    def __del__(self):
        """Деструктор"""
        self.cleanup()

