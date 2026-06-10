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
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    sd = None
    SOUNDDEVICE_AVAILABLE = False
import time
import requests
import zipfile
import shutil
from tqdm import tqdm
import re
import sys
from typing import Optional, Callable, Tuple, List, Dict
import gc
import logging
import traceback
import warnings

# Базовый логгер модуля (используется в коде до инициализации класса)
logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [WhisperXModule] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ПРОВЕРКА РЕЖИМА МИКРОСЕРВИСОВ
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

# Импортируем WhisperX локально только если НЕ используем сервисы
if not USE_LLM_SVC:
    try:
        import whisperx
        WHISPERX_AVAILABLE = True
    except ImportError:
        logger.warning("WhisperX не доступен локально, требуется запуск через микросервисы")
        whisperx = None
        WHISPERX_AVAILABLE = False
else:
    whisperx = None
    WHISPERX_AVAILABLE = False
    logger.info("Используется микросервис для WhisperX транскрипции")

# Импорт клиента для связи по сети
try:
    from backend.llm_client import transcribe_with_diarization_llm_svc
except ImportError:
    transcribe_with_diarization_llm_svc = None

# Настройка предупреждений  
warnings.filterwarnings("ignore", category=UserWarning, module="pytorch_lightning")
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")


def _torch():
    """Ленивый импорт: при USE_LLM_SVC=true torch в backend не нужен."""
    import torch as _torch_mod
    return _torch_mod


if not USE_LLM_SVC:
    try:
        _t = _torch()
        if _t.cuda.is_available():
            _t.backends.cuda.matmul.allow_tf32 = True
            _t.backends.cudnn.allow_tf32 = True
    except Exception as e:
        print(f"Предупреждение при настройке TF32: {e}")

# Импортируем пути к локальным моделям  
try:
    from config.config import WHISPERX_MODELS_DIR, DIARIZE_MODELS_DIR, WHISPERX_BASE_MODEL, DIARIZE_MODEL
    LOCAL_MODELS_AVAILABLE = True
except ImportError:
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
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s [WhisperX] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("=== Инициализация WhisperXTranscriber ===")
        
        # Если используем сервисы - выходим из инициализации тяжелых моделей
        if USE_LLM_SVC:
            self.logger.info("[SVC] Режим микросервисов: локальные модели не загружаются")
            self.model = None
            self.diarize_model = None
            self.device = "cpu"
            self.language = "ru"
            return

        # --- Локальная инициализация   ---
        if not WHISPERX_AVAILABLE:
            raise ImportError("WhisperX не установлен локально. Установите USE_LLM_SVC=true")
        
        self.project_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.temp_dir = tempfile.mkdtemp()
        self.language = "ru"
        self.whisper_model_path = os.path.join(self.project_dir, WHISPERX_MODELS_DIR)
        self.diarize_model_path = os.path.join(self.project_dir, DIARIZE_MODELS_DIR)
        self.sample_rate = 16000
        self.use_ffmpeg = self._check_ffmpeg_availability()
        self.progress_callback = None
        self.model_size = WHISPERX_BASE_MODEL
        
        # Определение устройства  
        _t = _torch()
        if _t.cuda.is_available():
            self.device = "cuda"
            self.compute_type = "float16"
        else:
            self.device = "cpu"
            self.compute_type = "float32"
        
        self._cached_diarize_model = None
        self.logger.info(f"Локальный режим: device={self.device}, compute={self.compute_type}")
    def _load_local_diarization_pipeline(self):
        """Загружает локальный пайплайн диаризации  """
        try:
            from pyannote.audio import Pipeline
            import yaml
            config_path = os.path.join(self.diarize_model_path, "pyannote_diarization_config.yaml")
            
            if not os.path.exists(config_path):
                self.logger.error(f"Конфиг диаризации не найден: {config_path}")
                return None
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if 'pipeline' in config_data and 'params' in config_data['pipeline']:
                params = config_data['pipeline']['params']
                if 'embedding' in params and isinstance(params['embedding'], str):
                    if not params['embedding'].startswith('/') and not '://' in params['embedding']:
                        params['embedding'] = os.path.abspath(os.path.join(self.diarize_model_path, params['embedding']))
                if 'segmentation' in params and isinstance(params['segmentation'], str):
                    if not params['segmentation'].startswith('/') and not '://' in params['segmentation']:
                        params['segmentation'] = os.path.abspath(os.path.join(self.diarize_model_path, params['segmentation']))
            
            temp_config_path = os.path.join(tempfile.gettempdir(), "pyannote_diarization_temp.yaml")
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f)
            
            pipeline = Pipeline.from_pretrained(temp_config_path)
            try: os.remove(temp_config_path)
            except: pass
            return pipeline
        except Exception as e:
            self.logger.error(f"Ошибка загрузки локального пайплайна: {e}")
            return None

    def _check_ffmpeg_availability(self) -> bool:
        """Проверка FFmpeg  """
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            return result.returncode == 0
        except: return False

    def _update_progress(self, progress: int):
        """Обновление прогресса  """
        if self.progress_callback:
            try: self.progress_callback(progress)
            except: pass

    def transcribe_audio_file(self, audio_path: str) -> Tuple[bool, str]:
        """Главный метод транскрибации """
        if not os.path.exists(audio_path):
            return False, f"Файл не найден: {audio_path}"

        # --- РЕЖИМ МИКРОСЕРВИСОВ ---
        if USE_LLM_SVC:
            self.logger.info(f"[SVC] Выполняю транскрибацию и диаризацию через микросервисы...")
            try:
                with open(audio_path, 'rb') as f:
                    audio_data = f.read()
                
                response = transcribe_with_diarization_llm_svc(
                    audio_data, 
                    filename=os.path.basename(audio_path),
                    language=self.language,
                    engine="whisperx"
                )
                
                if response.get("success"):
                    # segments уже содержат speaker, назначенный оркестратором в llm_client
                    segments = response.get("segments", [])
                    if segments:
                        transcript = self._format_transcript_with_speakers({"segments": segments})
                        return True, transcript
                    return False, "Сервис вернул пустые сегменты"
                else:
                    return False, f"Ошибка сервиса: {response.get('error')}"
            except Exception as e:
                self.logger.error(f"[SVC] Ошибка связи с микросервисами: {e}")
                return False, f"Ошибка микросервиса: {str(e)}"

        # --- ЛОКАЛЬНЫЙ РЕЖИМ  ---
        try:
            self._update_progress(10)
            # Загрузка модели WhisperX
            model = whisperx.load_model(self.model_size, self.device, compute_type=self.compute_type, 
                                      language=self.language, download_root=self.whisper_model_path)
            
            self._update_progress(50)
            # Транскрипция
            try:
                result = model.transcribe(audio_path)
            except Exception as transcribe_error:
                if "cudnn" in str(transcribe_error).lower():
                    model = whisperx.load_model(self.model_size, "cpu", compute_type="float32", 
                                              language=self.language, download_root=self.whisper_model_path)
                    result = model.transcribe(audio_path)
                else: raise transcribe_error

            self._update_progress(70)
            # Диаризация
            if hasattr(self, '_cached_diarize_model') and self._cached_diarize_model:
                diarize_model = self._cached_diarize_model
            else:
                diarize_model = self._load_local_diarization_pipeline()
                self._cached_diarize_model = diarize_model
            
            if not diarize_model:
                return False, "Не удалось загрузить модель диаризации"

            self._update_progress(80)
            # Извлечение аудио для диаризации (если видео)
            if audio_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                temp_audio = os.path.join(tempfile.gettempdir(), f"diarize_tmp_{os.path.basename(audio_path)}.wav")
                subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", temp_audio], capture_output=True)
                diarize_segments = diarize_model(temp_audio)
                try: os.remove(temp_audio)
                except: pass
            else:
                diarize_segments = diarize_model(audio_path)
            
            self._update_progress(90)
            # Объединение
            try:
                result = whisperx.assign_word_speakers(diarize_segments, result)
                if not any('speaker' in s for s in result['segments']):
                    result = self._manual_assign_speakers(diarize_segments, result)
            except:
                result = self._manual_assign_speakers(diarize_segments, result)

            transcript = self._format_transcript_with_speakers(result)
            self._update_progress(100)
            
            del model
            gc.collect()
            if self.device == "cuda":
                _torch().cuda.empty_cache()
            
            return True, transcript
        except Exception as e:
            self.logger.error(f"Локальная ошибка: {e}")
            return False, str(e)
    def transcribe_youtube(self, url: str) -> Tuple[bool, str]:
        """Транскрибирует аудио с YouTube  """
        try:
            print(f"Начинаю транскрипцию YouTube: {url}")
            
            # Загружаем аудио
            audio_path = self._download_youtube_audio(url)
            if not audio_path:
                return False, "Не удалось загрузить аудио с YouTube"
            
            print(f"Аудио загружено: {audio_path}")
            
            # Вызываем основной метод транскрибации (который сам выберет: сервис или локально)
            return self.transcribe_audio_file(audio_path)
            
        except Exception as e:
            print(f"Ошибка транскрипции YouTube: {e}")
            return False, f"Ошибка: {str(e)}"

    def _format_transcript_with_speakers(self, result: Dict) -> str:
        """Форматирует транскрипт с информацией о спикерах.
        Формат: SPEAKER_XX: текст (без временных меток).
        Смежные сегменты одного спикера объединяются в один блок.
        """
        try:
            segments = result.get("segments", [])
            if not segments:
                return self._format_simple_transcript(result)
            
            lines = []  # [(speaker, text)]
            for segment in segments:
                speaker = segment.get("speaker", None)
                text = segment.get("text", "").strip()
                if not text:
                    continue
                if speaker is None:
                    speaker = "SPEAKER_?"
                if lines and lines[-1][0] == speaker:
                    lines[-1] = (speaker, lines[-1][1] + " " + text)
                else:
                    lines.append((speaker, text))
            
            if not lines:
                return self._format_simple_transcript(result)
            
            return "\n".join(f"{spk}: {txt}" for spk, txt in lines)
            
        except Exception as e:
            print(f"Ошибка форматирования с диаризацией: {e}")
            return self._format_simple_transcript(result)
    
    def _format_time(self, seconds):
        """Форматирует время в секундах  """
        try:
            if seconds is None: return "00:00"
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        except: return "00:00"
    
    def _format_time_simple(self, seconds):
        """Форматирует время в простом виде  """
        try:
            if seconds is None: return "00:00"
            total_minutes = int(seconds // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}"
            else:
                return f"{minutes:02d}:{int(seconds % 60):02d}"
        except: return "00:00"

    def _format_simple_transcript(self, result: Dict) -> str:
        """Форматирует простую транскрипт без диаризации  """
        try:
            segments = result.get("segments", [])
            return " ".join([s.get("text", "").strip() for s in segments if s.get("text")])
        except: return str(result)

    def _download_youtube_audio(self, url: str) -> Optional[str]:
        """Загружает аудио с YouTube """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Загрузка аудио с YouTube: {url} (попытка {retry_count + 1}/{max_retries})")
                temp_dir = tempfile.mkdtemp()
                
                try:
                    yt = pytubefix.YouTube(url)
                    audio_stream = yt.streams.filter(only_audio=True).first()
                except Exception as yt_error:
                    if "SSL" in str(yt_error) or "EOF" in str(yt_error):
                        print(f"SSL/сетевая ошибка: {yt_error}")
                        if retry_count < max_retries - 1:
                            time.sleep(2); retry_count += 1; continue
                        else: return None
                    else: raise yt_error
                
                if not audio_stream: return None
                
                audio_stream.download(output_path=temp_dir, filename="youtube_audio")
                downloaded_file = os.path.join(temp_dir, "youtube_audio")
                
                if not os.path.exists(downloaded_file): return None
                
                # Конвертация в WAV через FFmpeg  
                audio_path = os.path.join(temp_dir, "youtube_audio.wav")
                result = subprocess.run([
                    'ffmpeg', '-y', '-i', downloaded_file, 
                    '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 
                    audio_path
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    audio_path = downloaded_file # Fallback
                
                return audio_path
                
            except Exception as e:
                print(f"Ошибка загрузки YouTube аудио (попытка {retry_count + 1}): {e}")
                if retry_count < max_retries - 1:
                    time.sleep(3); retry_count += 1
                else:
                    traceback.print_exc()
                    return None
        return None
    def set_progress_callback(self, callback: Callable[[int], None]):
        """Устанавливает callback для обновления прогресса  """
        self.progress_callback = callback

    def set_language(self, language: str):
        """Устанавливает язык транскрибации  """
        self.language = language
        self.logger.info(f"Язык транскрибации изменен на: {language}")

    def cleanup(self):
        """Очищает временные файлы  """
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                print(f"Временная директория очищена: {self.temp_dir}")
        except Exception as e:
            print(f"Ошибка при очистке: {e}")

    def __del__(self):
        """Деструктор для очистки ресурсов  """
        self.cleanup()

    def _manual_assign_speakers(self, diarize_segments, whisper_result):
        """
        Альтернативный способ объединения диаризации с транскрипцией  .
        Адаптирован для работы как с локальными объектами, так и с JSON из сервисов.
        """
        try:
            print("Используем ручное объединение диаризации...")
            
            segments = whisper_result.get('segments', [])
            if not segments:
                return None
            
            # Определяем формат входных данных диаризации (локальный Timeline или список из JSON)
            diarize_timeline = []
            if hasattr(diarize_segments, 'get_timeline'):
                diarize_timeline = diarize_segments.get_timeline()
            elif isinstance(diarize_segments, list):
                diarize_timeline = diarize_segments
            else:
                print("Неизвестный формат данных диаризации")
                return None
            
            if not diarize_timeline:
                return None
            
            # Создаем новый результат с информацией о спикерах
            result_with_speakers = whisper_result.copy()
            result_with_speakers['segments'] = []
            
            # Для каждого сегмента транскрипции находим соответствующего спикера по времени  
            for i, segment in enumerate(segments):
                segment_start = segment.get('start', 0)
                segment_end = segment.get('end', 0)
                segment_text = segment.get('text', '').strip()
                
                if not segment_text:
                    continue
                
                # Находим спикера для этого временного интервала
                speaker = self._find_speaker_for_time(diarize_timeline, segment_start, segment_end)
                
                new_segment = segment.copy()
                new_segment['speaker'] = speaker
                result_with_speakers['segments'].append(new_segment)
            
            return result_with_speakers
            
        except Exception as e:
            print(f"Ошибка ручного объединения: {e}")
            return None
    
    def _refine_segments_for_diarization(self, segments, diarize_timeline):
        """Оставляет сегменты как есть  """
        return segments
    
    def _find_speaker_for_time(self, diarize_timeline, start_time, end_time):
        """Находит спикера для заданного временного интервала """
        try:
            best_match = None
            best_overlap = 0
            
            for segment in diarize_timeline:
                try:
                    # Универсальное получение времени для объектов pyannote и словарей JSON
                    if hasattr(segment, 'start'):
                        d_start, d_end = segment.start, segment.end
                    elif isinstance(segment, dict):
                        d_start, d_end = segment.get('start', 0), segment.get('end', 0)
                    else: continue
                    
                    overlap_start = max(d_start, start_time)
                    overlap_end = min(d_end, end_time)
                    overlap_duration = max(0, overlap_end - overlap_start)
                    
                    if overlap_duration > best_overlap:
                        best_overlap = overlap_duration
                        best_match = segment
                except: continue
            
            if best_match and best_overlap > 0:
                speaker_id = None
                # Извлекаем ID спикера — возвращаем оригинальное имя без нормализации
                if isinstance(best_match, dict):
                    speaker_id = best_match.get('speaker')
                elif hasattr(best_match, 'track'):
                    speaker_id = str(best_match.track)
                elif hasattr(best_match, 'label'):
                    speaker_id = str(best_match.label)
                
                if speaker_id:
                    return speaker_id
            
            return "SPEAKER_?"
        except:
            return "SPEAKER_?"
    
    def _normalize_speaker_name(self, speaker_id):
        """Нормализует имя спикера к читаемому формату  """
        try:
            if not hasattr(self, '_speaker_mapping'):
                self._speaker_mapping = {}; self._speaker_counter = 0
            
            if speaker_id not in self._speaker_mapping:
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                if self._speaker_counter < len(letters):
                    simple_name = f"Speaker_{letters[self._speaker_counter]}"
                else:
                    simple_name = f"Speaker_{self._speaker_counter + 1}"
                
                self._speaker_mapping[speaker_id] = simple_name
                self._speaker_counter += 1
            
            return self._speaker_mapping[speaker_id]
        except: return "Speaker_A"

    def _analyze_diarization_speakers(self, diarize_timeline):
        """Анализирует список уникальных спикеров  """
        try:
            unique_speakers = set()
            for segment in diarize_timeline:
                if isinstance(segment, dict):
                    unique_speakers.add(segment.get('speaker'))
                elif hasattr(segment, 'track'):
                    unique_speakers.add(f"TRACK_{segment.track}")
            return sorted(list(unique_speakers))
        except: return []