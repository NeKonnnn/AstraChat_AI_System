import os
import tempfile
import subprocess
import wave
import json
import pytubefix
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    VideoFileClip = None
    MOVIEPY_AVAILABLE = False
import numpy as np
import sounddevice as sd
import soundfile as sf
import time
import requests
import zipfile
import shutil
from tqdm import tqdm
import re
import sys
import torch
from typing import Optional, Callable, Tuple, List, Dict
import gc
import logging
import traceback
import warnings

# Проверяем, нужно ли использовать llm-svc
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

# Импортируем WhisperX только если НЕ используем llm-svc
if not USE_LLM_SVC:
    try:
        import whisperx
        WHISPERX_AVAILABLE = True
    except ImportError:
        print("WhisperX не доступен локально, требуется llm-svc")
        whisperx = None
        WHISPERX_AVAILABLE = False
else:
    whisperx = None
    WHISPERX_AVAILABLE = False
    print("Используется llm-svc для WhisperX транскрипции")

# Настройка предупреждений и совместимости
warnings.filterwarnings("ignore", category=UserWarning, module="pytorch_lightning")
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

# Попытка исправить проблему с cudnn
try:
    if torch.cuda.is_available():
        # Включаем TF32 для совместимости
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        print("TF32 включен для совместимости с новыми версиями torch")
except Exception as e:
    print(f"Предупреждение при настройке TF32: {e}")

# Локальный пайплайн диаризации
LOCAL_DIARIZATION_AVAILABLE = True

# Импортируем пути к локальным моделям
try:
    from .config.config import WHISPERX_MODELS_DIR, DIARIZE_MODELS_DIR, WHISPERX_BASE_MODEL, DIARIZE_MODEL
    LOCAL_MODELS_AVAILABLE = True
except ImportError:
    # Если файл с путями не найден, используем дефолтные
    WHISPERX_MODELS_DIR = "whisperx_models"
    DIARIZE_MODELS_DIR = "diarize_models"
    WHISPERX_BASE_MODEL = "medium"
    DIARIZE_MODEL = "pyannote/speaker-diarization-3.1"
    LOCAL_MODELS_AVAILABLE = False

class WhisperXTranscriber:
    def __init__(self):
        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.WhisperXTranscriber")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s [WhisperX] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("=== Инициализация WhisperXTranscriber ===")
        
        # Если используем llm-svc, не инициализируем локальную модель
        if USE_LLM_SVC:
            self.logger.info("[LLM-SVC] Используется llm-svc, локальная модель WhisperX не загружается")
            self.model = None
            self.diarize_model = None
            self.temp_dir = tempfile.mkdtemp()
            self.language = "ru"
            return
        
        # Проверяем доступность WhisperX
        if not WHISPERX_AVAILABLE:
            self.logger.error("WhisperX не установлен или недоступен")
            raise ImportError("WhisperX не установлен. Используйте: pip install whisperx или установите USE_LLM_SVC=true")
        
        # Получаем абсолютный путь к корневой директории проекта (на уровень выше backend)
        self.project_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logger.debug(f"Директория проекта: {self.project_dir}")
        
        self.model = None
        self.temp_dir = tempfile.mkdtemp()
        self.logger.debug(f"Временная директория: {self.temp_dir}")
        
        self.language = "ru"  # По умолчанию используем русский
        self.logger.debug(f"Установлен язык: {self.language}")
        
        # Пути к моделям WhisperX
        self.whisper_model_path = os.path.join(self.project_dir, WHISPERX_MODELS_DIR)
        self.diarize_model_path = os.path.join(self.project_dir, DIARIZE_MODELS_DIR)
        self.logger.debug(f"Путь к моделям WhisperX: {self.whisper_model_path}")
        self.logger.debug(f"Путь к моделям диаризации: {self.diarize_model_path}")
        
        if LOCAL_MODELS_AVAILABLE:
            self.logger.info("Локальные модели доступны")
        else:
            self.logger.warning("Локальные модели не найдены, будут использоваться дефолтные пути")
        
        # Проверяем доступность локальной диаризации
        if LOCAL_DIARIZATION_AVAILABLE:
            self.logger.info("Локальный пайплайн диаризации доступен")
        else:
            self.logger.warning("Локальный пайплайн диаризации не найден")
        
        # Параметры для аудио
        self.sample_rate = 16000  # 16кГц
        self.logger.debug(f"Частота дискретизации: {self.sample_rate}")
        
        self.use_ffmpeg = self._check_ffmpeg_availability()
        self.logger.debug(f"FFmpeg доступен: {self.use_ffmpeg}")
        
        # Обратный вызов для обновления прогресса
        self.progress_callback = None
        
        # Настройки WhisperX
        self.model_size = WHISPERX_BASE_MODEL
        self.logger.debug(f"Размер модели WhisperX: {self.model_size}")
        
        # Определяем устройство и тип вычислений
        if torch.cuda.is_available():
            try:
                # Проверяем доступность CUDA и cudnn
                torch.cuda.empty_cache()
                test_tensor = torch.randn(1, 1).cuda()
                
                # Тестируем операции, которые могут вызвать ошибку cudnn
                try:
                    # Пробуем операцию, которая использует cudnn
                    result = torch.nn.functional.conv2d(test_tensor.unsqueeze(0).unsqueeze(0), 
                                                      torch.randn(1, 1, 3, 3).cuda())
                    del result
                except Exception as cudnn_error:
                    if "cudnn_ops_infer64_8.dll" in str(cudnn_error):
                        self.logger.warning(f"Ошибка cudnn: {cudnn_error}")
                        self.logger.warning("Переключаемся на CPU из-за проблем с cudnn")
                        del test_tensor
                        torch.cuda.empty_cache()
                        self.device = "cpu"
                        self.compute_type = "float32"
                        self.logger.info("Используем CPU из-за проблем с cudnn")
                        return
                    else:
                        raise cudnn_error
                
                del test_tensor
                torch.cuda.empty_cache()
                
                self.device = "cuda"
                self.compute_type = "float16"
                self.logger.info("CUDA доступна, используем GPU")
            except Exception as cuda_error:
                self.logger.warning(f"CUDA недоступна из-за ошибки: {cuda_error}")
                self.device = "cpu"
                self.compute_type = "float32"
                self.logger.info("Переключились на CPU из-за проблем с CUDA")
        else:
            self.device = "cpu"
            self.compute_type = "float32"
            self.logger.info("CUDA недоступна, используем CPU")
        
        # Кэш для модели диаризации
        self._cached_diarize_model = None
        
        self.logger.info("=== Инициализация завершена ===")

    def _load_local_diarization_pipeline(self):
        """Загружает локальный пайплайн диаризации"""
        try:
            from pyannote.audio import Pipeline
            
            # Путь к локальному конфигу
            config_path = os.path.join(self.diarize_model_path, "pyannote_diarization_config.yaml")
            
            if not os.path.exists(config_path):
                print(f"Конфиг файл не найден: {config_path}")
                return None
            
            print(f"Конфиг файл: {config_path}")
            
            # Проверяем наличие .bin файлов
            models_dir = os.path.join(self.diarize_model_path, "models")
            required_files = [
                "pyannote_model_segmentation-3.0.bin",
                "pyannote_model_wespeaker-voxceleb-resnet34-LM.bin"
            ]
            
            print(f"   🔍 Проверяем наличие .bin файлов в {models_dir}...")
            
            for file_name in required_files:
                file_path = os.path.join(models_dir, file_name)
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path) / 1024 / 1024
                    print(f"{file_name}: {size:.1f} МБ")
                else:
                    print(f"{file_name}: НЕ НАЙДЕН")
                    return None
            
            # Загружаем пайплайн из локального конфига
            print(f"Загружаем локальный пайплайн...")
            pipeline = Pipeline.from_pretrained(config_path)
            
            print("Локальный пайплайн диаризации загружен успешно!")
            return pipeline
            
        except Exception as e:
            print(f"Ошибка загрузки пайплайна: {e}")
            return None

    def _check_ffmpeg_availability(self) -> bool:
        """Проверяет доступность FFmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _update_progress(self, progress: int):
        """Обновляет прогресс, если установлен callback"""
        try:
            if self.progress_callback:
                self.progress_callback(progress)
        except Exception as e:
            # Игнорируем ошибки прогресса
            pass

    def transcribe_audio_file(self, audio_path: str) -> Tuple[bool, str]:
        """Транскрибирует аудио файл с диаризацией"""
        try:
            print(f"=== Начало транскрипции аудио файла: {audio_path} ===")
            print(f"LOCAL_DIARIZATION_AVAILABLE: {LOCAL_DIARIZATION_AVAILABLE}")
            
            # Проверяем существование файла
            if not os.path.exists(audio_path):
                print(f"Аудио файл не найден: {audio_path}")
                print(f"Текущая директория: {os.getcwd()}")
                print(f"Абсолютный путь: {os.path.abspath(audio_path)}")
                print(f"Содержимое директории: {os.listdir(os.path.dirname(audio_path) if os.path.dirname(audio_path) else '.')}")
                return False, f"Аудио файл не найден: {audio_path}"
            
            # Проверяем размер файла
            file_size = os.path.getsize(audio_path)
            print(f"Файл найден, размер: {file_size / 1024:.1f} КБ")
            
            if file_size == 0:
                print(f"Файл пустой: {audio_path}")
                return False, f"Аудио файл пустой: {audio_path}"
            
            self._update_progress(10)
            
            # Настройка совместимости версий
            print("Настройка совместимости версий...")
            try:
                # Включаем TF32 для совместимости с новыми версиями torch
                if torch.cuda.is_available():
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    print("TF32 включен для совместимости")
                
                # Отключаем предупреждения о совместимости версий
                import warnings
                warnings.filterwarnings("ignore", category=UserWarning, module="pytorch_lightning")
                warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
                print("Предупреждения о совместимости отключены")
            except Exception as compat_error:
                print(f"Предупреждение при настройке совместимости: {compat_error}")
            
            # Загружаем модель WhisperX
            print("Загрузка модели WhisperX...")
            model = whisperx.load_model(
                self.model_size, 
                self.device, 
                compute_type=self.compute_type,
                language=self.language,
                download_root=self.whisper_model_path  # Используем локальную папку
            )
            
            self._update_progress(50)
            
            # Транскрибируем аудио
            print("Выполняю транскрипцию...")
            try:
                print("Пробуем стандартный способ транскрибации...")
                result = model.transcribe(audio_path)
                print("Стандартная транскрибация успешна")
                
            except Exception as transcribe_error:
                print(f"Стандартная транскрибация не удалась: {transcribe_error}")
                
                # Проверяем, не связана ли ошибка с cudnn
                if "cudnn_ops_infer64_8.dll" in str(transcribe_error):
                    print("Обнаружена ошибка cudnn, переключаемся на CPU...")
                    # Переключаемся на CPU
                    self.device = "cpu"
                    self.compute_type = "float32"
                    
                    # Перезагружаем модель на CPU
                    print("Перезагружаем модель на CPU...")
                    model = whisperx.load_model(
                        self.model_size, 
                        "cpu", 
                        compute_type="float32",
                        language=self.language,
                        download_root=self.whisper_model_path
                    )
                    
                    # Пробуем транскрибацию на CPU
                    try:
                        result = model.transcribe(audio_path)
                        print("Транскрибация на CPU успешна")
                    except Exception as cpu_error:
                        print(f"Транскрибация на CPU не удалась: {cpu_error}")
                        raise Exception(f"Не удалось транскрибировать аудио: {cpu_error}")
                else:
                    # Пробуем через torchaudio как fallback
                    try:
                        print("Пробуем через torchaudio...")
                        import torchaudio
                        
                        # Загружаем аудио как тензор
                        waveform, sample_rate = torchaudio.load(audio_path)
                        print(f"Аудио загружено: форма {waveform.shape}, частота {sample_rate}")
                        
                        # Конвертируем в моно если нужно
                        if waveform.shape[0] > 1:
                            waveform = torch.mean(waveform, dim=0, keepdim=True)
                            print("Аудио конвертировано в моно")
                        
                        # Проверяем, что тензор не пустой
                        if waveform.numel() == 0:
                            raise Exception("Аудио файл пустой или поврежден")
                        
                        # Нормализуем (с проверкой на пустой тензор)
                        max_val = torch.max(torch.abs(waveform))
                        if max_val > 0:
                            waveform = waveform / max_val
                            print("Аудио нормализовано")
                        
                        print(f"Тензор готов для транскрибации: форма {waveform.shape}")
                        
                        # Транскрибируем тензор
                        print("Начинаем транскрипцию через тензор...")
                        if waveform.dim() == 1:
                            waveform = waveform.unsqueeze(0)
                        elif waveform.dim() == 2 and waveform.shape[0] == 1:
                            pass
                        else:
                            raise Exception(f"Неподдерживаемая форма тензора: {waveform.shape}")
                        
                        result = model.transcribe(waveform, sample_rate)
                        print("Транскрибация через тензор успешна")
                        
                    except Exception as tensor_error:
                        print(f"Транскрибация через torchaudio не удалась: {tensor_error}")
                        raise Exception(f"Не удалось транскрибировать аудио: {transcribe_error}")
            
            self._update_progress(70)
            
            # Диаризация с использованием локального пайплайна
            try:
                print("Загрузка модели диаризации...")
                print(f"LOCAL_DIARIZATION_AVAILABLE: {LOCAL_DIARIZATION_AVAILABLE}")
                
                # Пробуем использовать локальный пайплайн диаризации
                if LOCAL_DIARIZATION_AVAILABLE:
                    print("   Пытаемся загрузить локальный пайплайн диаризации...")
                    
                    # Сначала пробуем использовать предзагруженную модель
                    if hasattr(self, '_cached_diarize_model') and self._cached_diarize_model:
                        print("Используем предзагруженную модель диаризации")
                        diarize_model = self._cached_diarize_model
                    else:
                        # Загружаем локальный пайплайн
                        print("Загружаем локальный пайплайн диаризации...")
                        try:
                            diarize_model = self._load_local_diarization_pipeline()
                            
                            if diarize_model:
                                print("Локальный пайплайн диаризации загружен")
                                # Кэшируем модель для следующего использования
                                self._cached_diarize_model = diarize_model
                            else:
                                print("Не удалось загрузить локальный пайплайн диаризации")
                                print("Используем простую транскрипцию без диаризации")
                                transcript = self._format_simple_transcript(result)
                                return True, transcript
                        except Exception as diarize_load_error:
                            print(f"Ошибка загрузки диаризации: {diarize_load_error}")
                            print("Используем простую транскрипцию без диаризации")
                            transcript = self._format_simple_transcript(result)
                            return True, transcript
                    
                    self._update_progress(80)
                    
                    # Выполняем диаризацию
                    print("Выполняю диаризацию...")
                    
                    # Проверяем, является ли файл видео - если да, извлекаем аудио
                    if audio_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                        print("Обнаружен видео файл, извлекаем аудио для диаризации...")
                        try:
                            import tempfile
                            temp_dir = tempfile.gettempdir()
                            audio_for_diarization = os.path.join(temp_dir, f"audio_for_diarization_{os.path.basename(audio_path)}.wav")
                            
                            # Используем ffmpeg для извлечения аудио
                            if self._check_ffmpeg_availability():
                                command = [
                                    "ffmpeg", "-y", "-i", audio_path,
                                    "-ar", "16000", "-ac", "1", "-f", "wav",
                                    audio_for_diarization
                                ]
                                subprocess.run(command, check=True, capture_output=True)
                                print(f"Аудио извлечено: {audio_for_diarization}")
                                
                                # Выполняем диаризацию на извлеченном аудио
                                diarize_segments = diarize_model(audio_for_diarization)
                                
                                # Удаляем временный аудио файл
                                if os.path.exists(audio_for_diarization):
                                    os.remove(audio_for_diarization)
                            else:
                                print("FFmpeg недоступен, пропускаем диаризацию")
                                diarize_segments = None
                        except Exception as extract_error:
                            print(f"Ошибка извлечения аудио: {extract_error}")
                            diarize_segments = None
                    else:
                        # Для аудио файлов выполняем диаризацию напрямую
                        diarize_segments = diarize_model(audio_path)
                    
                    # Диагностика результатов диаризации
                    print(f"Результат диаризации: {type(diarize_segments)}")
                    print(f"Количество сегментов диаризации: {len(diarize_segments) if hasattr(diarize_segments, '__len__') else 'N/A'}")
                    if diarize_segments:
                        print(f"Содержимое diarize_segments: {diarize_segments}")
                        print(f"Атрибуты diarize_segments: {dir(diarize_segments) if hasattr(diarize_segments, '__dir__') else 'N/A'}")
                    else:
                        print("Диаризация не выполнена")
                    
                    # Пробуем получить информацию о спикерах из диаризации
                    if diarize_segments:
                        try:
                            if hasattr(diarize_segments, 'get_timeline'):
                                timeline = diarize_segments.get_timeline()
                                print(f"Timeline диаризации: {len(timeline) if timeline else 0} сегментов")
                                if timeline:
                                    for i, segment in enumerate(timeline[:3]):  # Показываем первые 3 сегмента
                                        print(f"      Сегмент {i+1}: {segment}")
                        except Exception as timeline_error:
                            print(f"Не удалось получить timeline: {timeline_error}")
                        
                        self._update_progress(90)
                        
                        # Объединяем результаты диаризации с транскрипцией
                        print("   Объединяем результаты диаризации...")
                        try:
                            print(f"Результат транскрипции до диаризации: {len(result.get('segments', []))} сегментов")
                            
                            # Показываем первые сегменты транскрипции
                            for i, seg in enumerate(result.get('segments', [])[:3]):
                                print(f"      Сегмент {i+1}: {seg.get('text', '')[:50]}... (start: {seg.get('start', 'N/A')}, end: {seg.get('end', 'N/A')})")
                            
                            result_with_speakers = whisperx.assign_word_speakers(diarize_segments, result)
                            
                            print(f"Результат после assign_word_speakers: {len(result_with_speakers.get('segments', []))} сегментов")
                            
                            # Проверяем, что результат корректный
                            if (isinstance(result_with_speakers, dict) and 
                                'segments' in result_with_speakers and 
                                len(result_with_speakers['segments']) > 0):
                                
                                # Показываем первые сегменты после объединения
                                for i, seg in enumerate(result_with_speakers['segments'][:3]):
                                    speaker = seg.get('speaker', 'N/A')
                                    text = seg.get('text', '')[:50]
                                    print(f"      Сегмент {i+1}: Speaker {speaker} - {text}...")
                                
                                # Проверяем, что у сегментов есть информация о спикерах
                                has_speakers = any('speaker' in segment for segment in result_with_speakers['segments'])
                                
                                if has_speakers:
                                    result = result_with_speakers
                                    # Форматируем результат с диаризацией
                                    transcript = self._format_transcript_with_speakers(result)
                                    print("Диаризация завершена успешно")
                                else:
                                    print("Диаризация не добавила информацию о спикерах")
                                    print("Пробуем альтернативный способ...")
                                    
                                    # Пробуем альтернативный способ - ручное объединение
                                    manual_result = self._manual_assign_speakers(diarize_segments, result)
                                    if manual_result:
                                        print("Альтернативная диаризация успешна")
                                        # Форматируем результат в строку
                                        transcript = self._format_transcript_with_speakers(manual_result)
                                    else:
                                        print("Альтернативная диаризация не удалась, используем простую транскрипцию")
                                        transcript = self._format_simple_transcript(result)
                                        
                        except Exception as assign_error:
                            print(f"Ошибка объединения диаризации: {assign_error}")
                            print(f"Тип ошибки: {type(assign_error)}")
                            import traceback
                            traceback.print_exc()
                            
                            # Пробуем альтернативный способ
                            print("Пробуем альтернативный способ диаризации...")
                            manual_result = self._manual_assign_speakers(diarize_segments, result)
                            if manual_result:
                                # Форматируем результат в строку
                                transcript = self._format_transcript_with_speakers(manual_result)
                            else:
                                transcript = self._format_simple_transcript(result)
                    else:
                        print("Диаризация не выполнена, используем простую транскрипцию")
                        transcript = self._format_simple_transcript(result)
                
                else:
                    print("Локальный пайплайн диаризации недоступен")
                    print("Используем простую транскрипцию без диаризации")
                    transcript = self._format_simple_transcript(result)
            
            except Exception as diarize_error:
                print(f"Ошибка диаризации: {diarize_error}")
                print("Используем простую транскрипцию без диаризации")
                transcript = self._format_simple_transcript(result)
            
            self._update_progress(100)
            
            # Очищаем память
            del model
            if 'diarize_model' in locals():
                del diarize_model
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            print("Транскрипция завершена успешно")
            return True, transcript
            
        except Exception as e:
            print(f"Ошибка транскрипции: {e}")
            return False, f"Ошибка: {str(e)}"

    def transcribe_youtube(self, url: str) -> Tuple[bool, str]:
        """Транскрибирует аудио с YouTube"""
        try:
            print(f"Начинаю транскрипцию YouTube: {url}")
            
            # Загружаем аудио
            audio_path = self._download_youtube_audio(url)
            if not audio_path:
                return False, "Не удалось загрузить аудио с YouTube"
            
            print(f"Аудио загружено: {audio_path}")
            
            # Транскрибируем
            return self.transcribe_audio_file(audio_path)
            
        except Exception as e:
            print(f"Ошибка транскрипции YouTube: {e}")
            return False, f"Ошибка: {str(e)}"

    def _format_transcript_with_speakers(self, result: Dict) -> str:
        """Форматирует транскрипт с информацией о спикерах в простом формате времени"""
        try:
            print(f"=== Форматирование с диаризацией ===")
            print(f"Тип result: {type(result)}")
            print(f"Ключи result: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            
            transcript = []
            
            # Проверяем, что у нас есть сегменты
            segments = result.get("segments", [])
            print(f"Количество сегментов: {len(segments)}")
            if not segments:
                print("Нет сегментов для форматирования")
                return self._format_simple_transcript(result)
            
            # Форматируем каждый сегмент отдельно - без группировки
            for i, segment in enumerate(segments):
                print(f"Обработка сегмента {i+1}: {segment}")
                
                # Получаем информацию о спикере
                speaker = segment.get("speaker", None)
                text = segment.get("text", "").strip()
                start_time = segment.get("start", 0)
                
                print(f"  Speaker: {speaker}, Start: {start_time}, Text: {text[:50]}...")
                
                # Если нет информации о спикере, используем номер сегмента
                if speaker is None:
                    speaker = f"Спикер_{i+1}"
                    print(f"  Используем дефолтный speaker: {speaker}")
                
                # Если текст пустой, пропускаем
                if not text:
                    print(f"  Пропускаем пустой текст")
                    continue
                
                # Форматируем в простом виде: "12:23 Спикер_1: текст"
                time_str = self._format_time_simple(start_time)
                formatted_line = f"{time_str} {speaker}: {text}"
                transcript.append(formatted_line)
                print(f"  Добавлена строка: {formatted_line[:50]}...")
            
            # Если получился пустой результат, используем простую транскрипцию
            if not transcript:
                print("Результат диаризации пустой, используем простую транскрипцию")
                return self._format_simple_transcript(result)
            
            # Простой вывод без заголовков - только список диалогов
            return "\n".join(transcript)
            
        except Exception as e:
            print(f"Ошибка форматирования с диаризацией: {e}")
            return self._format_simple_transcript(result)
    
    def _format_time(self, seconds):
        """Форматирует время в секундах в читаемый вид"""
        try:
            if seconds is None:
                return "00:00"
            
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        except:
            return "00:00"
    
    def _format_time_simple(self, seconds):
        """Форматирует время в простом виде для диалогов (часы:минуты)"""
        try:
            if seconds is None:
                return "00:00"
            
            total_minutes = int(seconds // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}"
            else:
                return f"{minutes:02d}:{int(seconds % 60):02d}"
        except:
            return "00:00"

    def _format_simple_transcript(self, result: Dict) -> str:
        """Форматирует простую транскрипт без диаризации"""
        try:
            segments = result.get("segments", [])
            transcript = []
            
            for segment in segments:
                text = segment.get("text", "").strip()
                if text:
                    transcript.append(text)
            
            return " ".join(transcript)
            
        except Exception as e:
            print(f"Ошибка форматирования простой транскрипции: {e}")
            return str(result)

    def _download_youtube_audio(self, url: str) -> Optional[str]:
        """Загружает аудио с YouTube"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Загрузка аудио с YouTube: {url} (попытка {retry_count + 1}/{max_retries})")
                
                # Создаем временную директорию
                temp_dir = tempfile.mkdtemp()
                print(f"Создана временная директория: {temp_dir}")
                
                # Загружаем аудио с обработкой SSL ошибок
                try:
                    yt = pytubefix.YouTube(url)
                    audio_stream = yt.streams.filter(only_audio=True).first()
                except Exception as yt_error:
                    if "SSL" in str(yt_error) or "EOF" in str(yt_error):
                        print(f"SSL/сетевая ошибка: {yt_error}")
                        if retry_count < max_retries - 1:
                            print(f"Повторная попытка через 2 секунды...")
                            import time
                            time.sleep(2)
                            retry_count += 1
                            continue
                        else:
                            print(f"Все попытки исчерпаны")
                            return None
                    else:
                        raise yt_error
                
                if not audio_stream:
                    print("Аудио поток не найден")
                    return None
                
                print(f"Найден аудио поток: {audio_stream}")
                
                # Скачиваем аудио
                print("Скачиваем аудио...")
                audio_stream.download(output_path=temp_dir, filename="youtube_audio")
                
                # Проверяем, что файл скачался
                downloaded_file = os.path.join(temp_dir, "youtube_audio")
                if not os.path.exists(downloaded_file):
                    print(f"Скачанный файл не найден: {downloaded_file}")
                    return None
                
                print(f"Файл скачан: {downloaded_file}")
                print(f"Размер файла: {os.path.getsize(downloaded_file) / 1024:.1f} КБ")
                
                # Определяем расширение скачанного файла
                file_extension = os.path.splitext(downloaded_file)[1]
                print(f"Расширение файла: {file_extension}")
                
                # Если файл уже WAV, используем его
                if file_extension.lower() == '.wav':
                    audio_path = downloaded_file
                    print(f"Файл уже в формате WAV: {audio_path}")
                else:
                    # Конвертируем в WAV
                    audio_path = os.path.join(temp_dir, "youtube_audio.wav")
                    print(f"Конвертируем в WAV: {audio_path}")
                    
                    try:
                        # Используем ffmpeg для конвертации
                        result = subprocess.run([
                            'ffmpeg', '-y', '-i', downloaded_file, 
                            '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 
                            audio_path
                        ], capture_output=True, text=True, timeout=60)
                        
                        if result.returncode != 0:
                            print(f"Ошибка конвертации FFmpeg: {result.stderr}")
                            # Пробуем использовать оригинальный файл
                            audio_path = downloaded_file
                            print(f"Используем оригинальный файл: {audio_path}")
                        else:
                            print(f"Конвертация в WAV завершена")
                            
                    except subprocess.TimeoutExpired:
                        print(f"Таймаут конвертации, используем оригинальный файл")
                        audio_path = downloaded_file
                    except Exception as conv_error:
                        print(f"Ошибка конвертации: {conv_error}, используем оригинальный файл")
                        audio_path = downloaded_file
                
                # Финальная проверка существования файла
                if not os.path.exists(audio_path):
                    print(f"Финальный аудио файл не найден: {audio_path}")
                    return None
                
                file_size = os.path.getsize(audio_path) / 1024
                print(f"Аудио файл готов: {audio_path}")
                print(f"Финальный размер: {file_size:.1f} КБ")
                
                return audio_path
                
            except Exception as e:
                print(f"Ошибка загрузки YouTube аудио (попытка {retry_count + 1}): {e}")
                
                if retry_count < max_retries - 1:
                    print(f"Повторная попытка через 3 секунды...")
                    import time
                    time.sleep(3)
                    retry_count += 1
                else:
                    print(f"Все попытки исчерпаны")
                    import traceback
                    traceback.print_exc()
                    return None
        
        return None

    def set_progress_callback(self, callback: Callable[[int], None]):
        """Устанавливает callback для обновления прогресса"""
        self.progress_callback = callback

    def set_language(self, language: str):
        """Устанавливает язык транскрибации"""
        self.language = language
        self.logger.info(f"Язык транскрибации изменен на: {language}")

    def cleanup(self):
        """Очищает временные файлы"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                print(f"Временная директория очищена: {self.temp_dir}")
        except Exception as e:
            print(f"Ошибка при очистке: {e}")

    def __del__(self):
        """Деструктор для очистки ресурсов"""
        self.cleanup()

    def _manual_assign_speakers(self, diarize_segments, whisper_result):
        """Альтернативный способ объединения диаризации с транскрипцией"""
        try:
            print("Используем ручное объединение диаризации...")
            
            # Получаем сегменты транскрипции
            segments = whisper_result.get('segments', [])
            if not segments:
                print("Нет сегментов транскрипции")
                return None
            
            # Получаем timeline диаризации
            try:
                if hasattr(diarize_segments, 'get_timeline'):
                    diarize_timeline = diarize_segments.get_timeline()
                    print(f"Timeline диаризации: {len(diarize_timeline)} сегментов")
                else:
                    print("Не удается получить timeline диаризации")
                    return None
            except Exception as e:
                print(f"Ошибка получения timeline: {e}")
                return None
            
            if not diarize_timeline:
                print("Timeline диаризации пустой")
                return None
            
            # Создаем новый результат с информацией о спикерах
            result_with_speakers = whisper_result.copy()
            result_with_speakers['segments'] = []
            
            # Анализируем все сегменты диаризации для получения уникальных спикеров
            unique_speakers = self._analyze_diarization_speakers(diarize_timeline)
            print(f"Найдено уникальных спикеров: {len(unique_speakers)}")
            for i, speaker in enumerate(unique_speakers):
                print(f"      Спикер {i+1}: {speaker}")
            
            # Разбиваем длинные сегменты транскрипции на более мелкие
            refined_segments = self._refine_segments_for_diarization(segments, diarize_timeline)
            print(f"Разбито на {len(refined_segments)} сегментов для диаризации")
            
            # Для каждого сегмента транскрипции находим соответствующий спикер
            for i, segment in enumerate(refined_segments):
                segment_start = segment.get('start', 0)
                segment_end = segment.get('end', 0)
                segment_text = segment.get('text', '').strip()
                
                if not segment_text:
                    continue
                
                # Находим спикера для этого временного интервала
                speaker = self._find_speaker_for_time(diarize_timeline, segment_start, segment_end)
                
                # Создаем новый сегмент с информацией о спикере
                new_segment = segment.copy()
                new_segment['speaker'] = speaker
                result_with_speakers['segments'].append(new_segment)
                
                print(f"Сегмент {i+1}: {segment_text[:30]}... -> Speaker {speaker}")
            
            print(f"Ручное объединение завершено: {len(result_with_speakers['segments'])} сегментов")
            return result_with_speakers
            
        except Exception as e:
            print(f"Ошибка ручного объединения: {e}")
            return None
    
    def _refine_segments_for_diarization(self, segments, diarize_timeline):
        """Оставляет сегменты как есть - без искусственного разбиения"""
        try:
            # НЕ разбиваем сегменты - оставляем естественное разбиение по диалогу
            # Спикер может говорить как несколько секунд, так и несколько минут
            print(f"Оставляем {len(segments)} сегментов без разбиения")
            return segments
            
        except Exception as e:
            print(f"Ошибка обработки сегментов: {e}")
            return segments
    
    def _split_text_into_parts(self, text, total_duration, chunk_duration):
        """Разбивает текст на части пропорционально времени"""
        try:
            parts = []
            words = text.split()
            total_words = len(words)
            
            if total_words == 0:
                return []
            
            # Для более детального разбиения используем меньше слов на сегмент
            # Минимум 2-3 слова на сегмент, максимум 8-10 слов
            max_words_per_chunk = min(8, max(2, total_words // max(1, int(total_duration / chunk_duration))))
            
            current_start = 0
            current_word_index = 0
            
            while current_word_index < total_words:
                # Определяем размер текущего чанка (адаптивно)
                remaining_words = total_words - current_word_index
                remaining_chunks = max(1, int((total_duration - current_start) / chunk_duration))
                
                words_in_chunk = min(max_words_per_chunk, max(2, remaining_words // remaining_chunks))
                chunk_end_word_index = min(current_word_index + words_in_chunk, total_words)
                
                # Вычисляем время для текущего чанка
                chunk_ratio = (chunk_end_word_index - current_word_index) / total_words
                chunk_time = total_duration * chunk_ratio
                current_end = current_start + chunk_time
                
                # Берем слова для текущего чанка
                chunk_words = words[current_word_index:chunk_end_word_index]
                chunk_text = ' '.join(chunk_words)
                
                if chunk_text.strip():
                    parts.append((chunk_text.strip(), current_start, current_end))
                
                current_start = current_end
                current_word_index = chunk_end_word_index
            
            print(f"Разбили текст на {len(parts)} частей (было {total_words} слов)")
            return parts
            
        except Exception as e:
            print(f"Ошибка разбиения текста: {e}")
            return [(text, 0, total_duration)]
    
    def _find_speaker_for_time(self, diarize_timeline, start_time, end_time):
        """Находит спикера для заданного временного интервала"""
        try:
            best_match = None
            best_overlap = 0
            
            # Ищем сегмент диаризации с наибольшим перекрытием
            for segment in diarize_timeline:
                try:
                    # Получаем время начала и конца сегмента диаризации
                    if hasattr(segment, 'start') and hasattr(segment, 'end'):
                        diarize_start = segment.start
                        diarize_end = segment.end
                    elif hasattr(segment, '__getitem__'):
                        # Альтернативный способ доступа к времени
                        diarize_start = segment[0] if len(segment) > 0 else 0
                        diarize_end = segment[1] if len(segment) > 1 else 0
                    else:
                        continue
                    
                    # Вычисляем перекрытие временных интервалов
                    overlap_start = max(diarize_start, start_time)
                    overlap_end = min(diarize_end, end_time)
                    overlap_duration = max(0, overlap_end - overlap_start)
                    
                    if overlap_duration > best_overlap:
                        best_overlap = overlap_duration
                        best_match = segment
                        
                except Exception as segment_error:
                    print(f"Ошибка обработки сегмента диаризации: {segment_error}")
                    continue
            
            # Если нашли подходящий сегмент, извлекаем метку спикера
            if best_match and best_overlap > 0:
                try:
                    # Получаем уникальный идентификатор спикера из pyannote
                    speaker_id = None
                    
                    # Пробуем разные способы получения идентификатора спикера
                    if hasattr(best_match, 'track'):
                        speaker_id = str(best_match.track)
                        print(f"Идентификатор спикера из track: {speaker_id}")
                    elif hasattr(best_match, 'label'):
                        speaker_id = str(best_match.label) 
                        print(f"Идентификатор спикера из label: {speaker_id}")
                    else:
                        # Пытаемся извлечь информацию о спикере из diarize_segments напрямую
                        try:
                            # Ищем сегмент в исходном результате диаризации
                            for track, label in self._extract_speaker_tracks(best_match, start_time, end_time):
                                speaker_id = f"TRACK_{track}"
                                print(f"Извлечен track: {track} -> {speaker_id}")
                                break
                            
                            if not speaker_id:
                                # Если track не найден, используем хеш координат сегмента для постоянства
                                coord_hash = hash(f"{best_match.start:.3f}_{best_match.end:.3f}") % 100
                                speaker_id = f"SPEAKER_{coord_hash:02d}"
                                print(f"Сгенерирован стабильный идентификатор: {speaker_id}")
                                
                        except Exception as track_error:
                            print(f"Ошибка извлечения track: {track_error}")
                            # Резервный вариант - используем стабильный хеш
                            coord_hash = hash(f"{best_match.start:.3f}_{best_match.end:.3f}") % 100
                            speaker_id = f"SPEAKER_{coord_hash:02d}"
                            print(f"Резервный идентификатор: {speaker_id}")
                    
                    # Нормализуем имя спикера
                    normalized_speaker = self._normalize_speaker_name(speaker_id)
                    print(f"Финальное имя спикера: {normalized_speaker} (перекрытие: {best_overlap:.2f}с)")
                    return normalized_speaker
                        
                except Exception as label_error:
                    print(f"Ошибка извлечения метки спикера: {label_error}")
            
            # Если не нашли подходящий сегмент, используем дефолтную метку
            print(f"Спикер не найден для времени [{start_time:.2f} - {end_time:.2f}], используем Speaker_A")
            return "Speaker_A"
            
        except Exception as e:
            print(f"Ошибка поиска спикера: {e}")
            return "Speaker_A"
    
    def _normalize_speaker_name(self, speaker_id):
        """Нормализует имя спикера к читаемому формату"""
        try:
            # Создаем маппинг уникальных идентификаторов на простые имена
            if not hasattr(self, '_speaker_mapping'):
                self._speaker_mapping = {}
                self._speaker_counter = 0
            
            if speaker_id not in self._speaker_mapping:
                # Присваиваем новое простое имя
                speaker_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                if self._speaker_counter < len(speaker_letters):
                    simple_name = f"Speaker_{speaker_letters[self._speaker_counter]}"
                else:
                    simple_name = f"Speaker_{self._speaker_counter + 1}"
                
                self._speaker_mapping[speaker_id] = simple_name
                self._speaker_counter += 1
                print(f"Маппинг: {speaker_id} -> {simple_name}")
            
            return self._speaker_mapping[speaker_id]
            
        except Exception as e:
            print(f"Ошибка нормализации имени спикера: {e}")
            return "Speaker_A"
    
    def _extract_speaker_tracks(self, segment, start_time, end_time):
        """Извлекает информацию о треках спикеров из сегмента диаризации"""
        try:
            # Пытаемся получить доступ к внутренней структуре pyannote Annotation
            if hasattr(segment, '_tracks') and hasattr(segment, '_labels'):
                tracks = segment._tracks
                labels = segment._labels
                
                for track_id, label in zip(tracks, labels):
                    yield track_id, label
                    
            elif hasattr(segment, 'get_tracks'):
                # Альтернативный способ получения треков
                for track in segment.get_tracks():
                    yield track, f"speaker_{track}"
                    
            else:
                # Если нет доступа к tracks, используем альтернативный подход
                segment_str = str(segment)
                print(f"Анализируем строку сегмента: {segment_str}")
                
                # Попытка извлечь track из строкового представления
                import re
                track_match = re.search(r'track_(\d+)', segment_str.lower())
                if track_match:
                    track_id = track_match.group(1)
                    yield track_id, f"speaker_{track_id}"
                    
        except Exception as e:
            print(f"Ошибка извлечения треков: {e}")
            return
    
    def _analyze_diarization_speakers(self, diarize_timeline):
        """Анализирует диаризацию для получения списка уникальных спикеров"""
        try:
            unique_speakers = set()
            
            for segment in diarize_timeline:
                try:
                    # Пытаемся получить реальную информацию о спикере
                    speaker_info = None
                    
                    if hasattr(segment, 'track'):
                        speaker_info = f"TRACK_{segment.track}"
                    elif hasattr(segment, 'label'):
                        speaker_info = str(segment.label)
                    else:
                        # Анализируем строковое представление
                        segment_str = str(segment)
                        
                        # Ищем стандартные паттерны pyannote
                        import re
                        patterns = [
                            r'(\w+_\d+)',  # SPEAKER_01, track_1, etc.
                            r'<Segment\((.+?)\)>',  # <Segment(track_1)>
                            r'track[_\s]*(\d+)',  # track_1, track 1
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, segment_str, re.IGNORECASE)
                            if match:
                                speaker_info = match.group(1)
                                break
                        
                        if not speaker_info:
                            # Если ничего не найдено, используем координаты
                            start_coord = getattr(segment, 'start', 0)
                            end_coord = getattr(segment, 'end', 0)
                            coord_hash = hash(f"{start_coord:.3f}_{end_coord:.3f}") % 10
                            speaker_info = f"SPEAKER_{coord_hash}"
                    
                    if speaker_info:
                        unique_speakers.add(speaker_info)
                        
                except Exception as segment_error:
                    print(f"Ошибка анализа сегмента: {segment_error}")
                    continue
            
            return sorted(list(unique_speakers))
            
        except Exception as e:
            print(f"Ошибка анализа уникальных спикеров: {e}")
            return []
