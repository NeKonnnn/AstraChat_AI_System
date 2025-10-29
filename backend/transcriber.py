import os
import tempfile
import subprocess
import wave
import json
import pytubefix

# Проверяем, нужно ли использовать llm-svc
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

# Импортируем Vosk только если НЕ используем llm-svc
if not USE_LLM_SVC:
    try:
        from vosk import Model, KaldiRecognizer
        VOSK_AVAILABLE = True
    except ImportError:
        print("Vosk не доступен локально, требуется llm-svc")
        VOSK_AVAILABLE = False
        Model = None
        KaldiRecognizer = None
else:
    VOSK_AVAILABLE = False
    Model = None
    KaldiRecognizer = None
    print("Используется llm-svc для Vosk транскрипции")
try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
    print("MoviePy успешно импортирован")
except ImportError as e:
    VideoFileClip = None
    MOVIEPY_AVAILABLE = False
    print(f"MoviePy не импортирован: {e}")
except Exception as e:
    VideoFileClip = None
    MOVIEPY_AVAILABLE = False
    print(f"Неожиданная ошибка при импорте MoviePy: {e}")
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
import logging
import traceback

class Transcriber:
    def __init__(self):
        # Настройка логирования
        self.logger = logging.getLogger(f"{__name__}.Transcriber")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s [Vosk] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("=== Инициализация Vosk Transcriber ===")
        
        # Если используем llm-svc, не инициализируем локальную модель
        if USE_LLM_SVC:
            self.logger.info("[LLM-SVC] Используется llm-svc, локальная модель Vosk не загружается")
            self.model = None
            self.temp_dir = tempfile.mkdtemp()
            self.language = "ru"
            return
        
        # Проверяем доступность Vosk
        if not VOSK_AVAILABLE:
            raise Exception("Vosk недоступен. Установите USE_LLM_SVC=true для использования llm-svc")
        
        # Получаем абсолютный путь к корневой директории проекта (на уровень выше backend)
        self.project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        self.logger.debug(f"Директория проекта: {self.project_dir}")
        
        self.model = None
        self.temp_dir = tempfile.mkdtemp()
        self.logger.debug(f"Временная директория: {self.temp_dir}")
        
        self.language = "ru"  # По умолчанию используем русский
        self.logger.debug(f"Установлен язык: {self.language}")
        
        # Устанавливаем путь к модели - используем model_small в директории проекта
        self.model_size = os.path.join(self.project_dir, "model_small")
        self.logger.info(f"Путь к модели Vosk: {self.model_size}")
        
        # Проверяем существование папки модели и наличие в ней файлов
        try:
            self.logger.info("Проверка и подготовка модели Vosk...")
            self.check_and_prepare_model()
            self.logger.info("Модель Vosk проверена успешно")
        except Exception as e:
            self.logger.error(f"Ошибка при проверке модели Vosk: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Параметры для аудио
        self.sample_rate = 16000  # 16кГц
        self.logger.debug(f"Частота дискретизации: {self.sample_rate}")
        
        self.use_ffmpeg = self._check_ffmpeg_availability()  # Проверка доступности FFmpeg
        self.logger.debug(f"FFmpeg доступен: {self.use_ffmpeg}")
        
        # Обратный вызов для обновления прогресса
        self.progress_callback = None
        
        self.logger.info("Vosk Transcriber успешно инициализирован")
        
    def check_and_prepare_model(self):
        """Проверяет наличие модели Vosk и при необходимости загружает её"""
        self.logger.info("Проверка наличия модели Vosk...")
        # Проверяем существование папки и наличие в ней файлов модели
        if not os.path.exists(self.model_size) or not os.listdir(self.model_size):
            self.logger.warning(f"Папка модели пуста или не существует: {self.model_size}")
            
            # Автоматически пытаемся загрузить модель без пользовательского ввода
            self.logger.info("Попытка автоматической загрузки модели Vosk...")
            try:
                self.download_vosk_model()
            except Exception as e:
                self.logger.error(f"Не удалось автоматически загрузить модель: {e}")
                self.logger.info("Для работы транскрибации необходимо вручную загрузить модель с https://alphacephei.com/vosk/models")
                self.logger.info("и распаковать её в папку 'model_small' в корне проекта.")
        else:
            self.logger.info(f"Модель Vosk найдена в директории: {self.model_size}")
            # Проверяем основные файлы модели
            required_files = ['final.mdl', 'conf', 'graph']
            missing_files = []
            for req_file in required_files:
                if not os.path.exists(os.path.join(self.model_size, req_file)):
                    missing_files.append(req_file)
            
            if missing_files:
                self.logger.warning(f"Отсутствуют файлы модели: {missing_files}")
            else:
                self.logger.info("Все необходимые файлы модели найдены")
    
    def download_vosk_model(self):
        """Загружает модель Vosk из интернета и распаковывает её"""
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
        zip_path = os.path.join(self.temp_dir, "vosk-model.zip")
        
        try:
            # Создаем папку model_small, если её нет
            if not os.path.exists(self.model_size):
                os.makedirs(self.model_size, exist_ok=True)
                self.logger.debug(f"Создана директория для модели: {self.model_size}")
            
            self.logger.info(f"Загрузка модели Vosk с {model_url}...")
            # Загружаем ZIP-архив
            response = requests.get(model_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            self.logger.debug(f"Размер загружаемого файла: {total_size} байт")
            
            with open(zip_path, 'wb') as f:
                for chunk in tqdm(response.iter_content(chunk_size=8192), total=total_size//8192, unit='KB'):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info("Распаковка архива с моделью...")
            # Распаковываем архив
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Извлекаем в временную папку
                temp_extract = os.path.join(self.temp_dir, "extract")
                if not os.path.exists(temp_extract):
                    os.makedirs(temp_extract)
                zip_ref.extractall(temp_extract)
                self.logger.debug(f"Архив извлечен в: {temp_extract}")
                
                # Находим распакованную папку модели
                extracted_folders = [f for f in os.listdir(temp_extract) if os.path.isdir(os.path.join(temp_extract, f))]
                self.logger.debug(f"Найдены папки: {extracted_folders}")
                
                if extracted_folders:
                    model_folder = os.path.join(temp_extract, extracted_folders[0])
                    self.logger.debug(f"Копирование модели из: {model_folder}")
                    # Копируем содержимое в целевую папку model_small
                    for item in os.listdir(model_folder):
                        s = os.path.join(model_folder, item)
                        d = os.path.join(self.model_size, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d)
                            self.logger.debug(f"Скопирована папка: {item}")
                        else:
                            shutil.copy2(s, d)
                            self.logger.debug(f"Скопирован файл: {item}")
            
            self.logger.info(f"Модель Vosk успешно загружена и распакована в {self.model_size}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке модели: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        
    def _check_ffmpeg_availability(self):
        """Проверка доступности FFmpeg в системе"""
        try:
            self.logger.debug("Проверка доступности FFmpeg...")
            result = subprocess.run(["ffmpeg", "-version"], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
            if result.returncode == 0:
                self.logger.info("FFmpeg найден и доступен")
                return True
            else:
                self.logger.warning(f"FFmpeg вернул код ошибки: {result.returncode}")
                return False
        except FileNotFoundError:
            self.logger.warning("FFmpeg не найден в системе. Будет использован альтернативный метод.")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при проверке FFmpeg: {e}")
            return False
        
    def load_model(self, model_path=None):
        """Загрузка модели для транскрибации"""
        if model_path:
            self.model_size = model_path
            self.logger.debug(f"Установлен новый путь к модели: {model_path}")
            
        try:
            self.logger.info(f"Загрузка модели Vosk ({self.model_size})...")
            
            # Проверяем, что директория модели существует и содержит файлы
            if not os.path.exists(self.model_size) or not os.listdir(self.model_size):
                self.logger.error(f"Директория модели пуста или не существует: {self.model_size}")
                
                # Автоматически пробуем загрузить модель
                self.logger.info("Попытка автоматической загрузки модели...")
                try:
                    success = self.download_vosk_model()
                    if not success:
                        return False
                except Exception as download_error:
                    self.logger.error(f"Не удалось загрузить модель автоматически: {download_error}")
                    self.logger.info("Модель Vosk не найдена. Пожалуйста, скачайте модель с https://alphacephei.com/vosk/models")
                    self.logger.info("и распакуйте её в папку 'model_small' в корне проекта.")
                    return False
            
            # Явно освобождаем предыдущую модель, если она была загружена
            if self.model is not None:
                self.logger.debug("Освобождение предыдущей модели...")
                self.model = None
            
            # Загружаем модель
            self.logger.info("Инициализация модели Vosk...")
            self.model = Model(self.model_size)
            self.logger.info("Модель Vosk успешно загружена")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке модели Vosk: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.model = None
            return False
    
    def transcribe_audio(self, audio_path):
        """Транскрибация аудио файла"""
        self.logger.info(f"=== Начало транскрибации аудио файла: {audio_path} ===")
        
        # Обновляем прогресс
        self.update_progress(20)
        
        # Проверяем, что модель загружена
        if not self.model:
            self.logger.warning("Модель не загружена, загружаем...")
            success = self.load_model()
            if not success:
                self.logger.error("Не удалось загрузить модель транскрибации")
                return False, "Не удалось загрузить модель транскрибации"
        
        try:
            self.logger.info(f"Начинаю транскрибацию файла: {audio_path}")
            self.update_progress(30)
            
            # Проверяем, существует ли файл
            if not os.path.exists(audio_path):
                self.logger.error(f"Файл не найден: {audio_path}")
                return False, f"Файл не найден: {audio_path}"
            
            self.logger.debug(f"Размер файла: {os.path.getsize(audio_path)} байт")
            
            # Убедимся, что временная директория существует
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
            
            # Преобразуем аудио в WAV 16кГц 16bit моно если нужно
            wav_path = os.path.abspath(os.path.join(self.temp_dir, "audio_for_transcription.wav"))
            
            # Проверяем формат входного файла
            if self._is_wav_16khz_mono(audio_path):
                # Если файл уже в нужном формате, используем его напрямую
                wav_path = audio_path
                self.update_progress(40)
            else:
                # Конвертируем файл в нужный формат
                self.update_progress(35)
                print("Преобразование аудио в нужный формат...")
                if self.use_ffmpeg:
                    success, wav_path = self._convert_with_ffmpeg(audio_path, wav_path)
                    if not success:
                        return False, wav_path
                else:
                    success, wav_path = self._convert_with_sounddevice(audio_path, wav_path)
                    if not success:
                        return False, wav_path
                self.update_progress(40)
            
            # Проверяем файл перед открытием
            if not os.path.exists(wav_path):
                return False, f"Ошибка: WAV файл не был создан: {wav_path}"
                
            try:
                # Открываем WAV файл для распознавания
                wf = wave.open(wav_path, "rb")
                
                # Проверяем параметры аудио
                print(f"Параметры WAV файла: каналы={wf.getnchannels()}, частота={wf.getframerate()}, "
                      f"сэмплов={wf.getnframes()}, длительность={wf.getnframes()/wf.getframerate():.2f} сек")
                
                # Создаем распознаватель с точным указанием параметров
                rec = KaldiRecognizer(self.model, wf.getframerate())
                
                # Проверяем, что распознаватель создан успешно
                if rec is None:
                    return False, "Не удалось создать распознаватель Kaldi"
                
                # Собираем результаты транскрибации
                result_text = []
                
                # Увеличиваем размер буфера для ускорения обработки (40000 сэмплов вместо 4000)
                buffer_size = 40000
                
                # Читаем аудио по частям и распознаем
                print("Обработка аудио...")
                total_frames = wf.getnframes()
                processed_frames = 0
                
                # Устанавливаем начальный прогресс транскрибации
                self.update_progress(45)
                
                while True:
                    data = wf.readframes(buffer_size)
                    if len(data) == 0:
                        break
                    
                    # Обновляем прогресс
                    processed_frames += buffer_size
                    progress = min(100, int(processed_frames * 100 / total_frames))
                    
                    # Рассчитываем общий прогресс (от 45% до 95%)
                    total_progress = 45 + int(progress * 0.5)  # 50% диапазона для транскрибации
                    self.update_progress(total_progress)
                    
                    if progress % 10 == 0:
                        print(f"Прогресс транскрибации: {progress}%")
                        
                    # Отправляем данные в распознаватель
                    if rec.AcceptWaveform(data):
                        part_result = json.loads(rec.Result())
                        if 'text' in part_result and part_result['text'].strip():
                            result_text.append(part_result['text'])
                
                # Получаем финальный результат
                part_result = json.loads(rec.FinalResult())
                if 'text' in part_result and part_result['text'].strip():
                    result_text.append(part_result['text'])
                
                # Закрываем файл
                wf.close()
                
                full_text = " ".join(result_text)
                
                # Проверяем, что есть какой-то результат
                if not full_text.strip():
                    return False, "Не удалось распознать текст в аудио (пустой результат)"
                
                print(f"Транскрибация завершена, получено {len(full_text.split())} слов")
                self.update_progress(100)
                return True, full_text
                
            except Exception as wav_err:
                print(f"Ошибка при обработке WAV файла: {str(wav_err)}")
                return False, f"Ошибка при обработке WAV файла: {str(wav_err)}"
            
        except Exception as e:
            print(f"Ошибка при транскрибации аудио: {str(e)}")
            return False, f"Ошибка при транскрибации: {str(e)}"
            
    def _is_wav_16khz_mono(self, file_path):
        """Проверяет, соответствует ли WAV файл требованиям 16кГц, моно"""
        try:
            if not file_path.lower().endswith('.wav'):
                return False
                
            wf = wave.open(file_path, 'rb')
            is_valid = (wf.getnchannels() == 1 and wf.getframerate() == 16000)
            wf.close()
            return is_valid
        except:
            return False
            
    def _convert_with_ffmpeg(self, input_path, output_path):
        """Использует FFmpeg для конвертации аудио"""
        try:
            # Используем ffmpeg для конвертации
            command = [
                "ffmpeg", 
                "-y",  # Перезаписывать существующие файлы
                "-i", input_path,  # Входной файл
                "-ar", "16000",  # Частота дискретизации 16 кГц
                "-ac", "1",      # Моно
                "-bits_per_raw_sample", "16",  # 16 бит
                output_path  # Выходной файл
            ]
            print(f"Выполняем команду: {' '.join(command)}")
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Проверяем, создан ли файл
            if not os.path.exists(output_path):
                stderr = result.stderr.decode('utf-8', errors='ignore')
                return False, f"Не удалось конвертировать аудио. FFmpeg ошибка: {stderr}"
            
            return True, output_path
                
        except FileNotFoundError:
            return False, "FFmpeg не найден. Пожалуйста, установите FFmpeg и добавьте его в PATH."
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode('utf-8', errors='ignore')
            return False, f"Ошибка FFmpeg: {stderr}"
            
    def _convert_with_sounddevice(self, input_path, output_path):
        """Использует sounddevice и soundfile для конвертации аудио"""
        try:
            # Загружаем аудио файл с помощью soundfile
            print(f"Конвертация {input_path} с использованием sounddevice")
            
            try:
                # Пытаемся прочитать файл с помощью soundfile
                data, fs = sf.read(input_path)
            except Exception as sf_err:
                print(f"Ошибка soundfile: {sf_err}")
                # Если формат не поддерживается soundfile, используем moviepy
                try:
                    audio_clip = VideoFileClip(input_path).audio
                    temp_audio_path = os.path.join(self.temp_dir, "temp_audio.wav")
                    audio_clip.write_audiofile(
                        temp_audio_path,
                        codec='pcm_s16le',
                        ffmpeg_params=[],  # Не используем ffmpeg
                        logger=None        # Отключаем логирование
                    )
                    audio_clip.close()
                    data, fs = sf.read(temp_audio_path)
                except Exception as mp_err:
                    return False, f"Не удалось прочитать аудио файл: {str(mp_err)}"
            
            # Преобразуем в моно, если это стерео
            if len(data.shape) > 1 and data.shape[1] > 1:
                data = np.mean(data, axis=1)
            
            # Ресемплирование до 16кГц, если необходимо
            if fs != 16000:
                # Простое ресемплирование для аудио (не самое качественное, но работает)
                ratio = 16000.0 / fs
                n_samples = int(len(data) * ratio)
                data = np.interp(
                    np.linspace(0, len(data) - 1, n_samples),
                    np.arange(len(data)),
                    data
                )
            
            # Записываем в WAV формат
            sf.write(output_path, data, 16000, subtype='PCM_16')
            
            # Проверяем, создан ли файл
            if not os.path.exists(output_path):
                return False, "Не удалось создать WAV файл с использованием sounddevice"
                
            return True, output_path
        except Exception as e:
            print(f"Ошибка при конвертации аудио: {str(e)}")
            return False, f"Ошибка при конвертации аудио: {str(e)}"
    
    def extract_audio_from_video(self, video_path):
        """Извлечение аудио из видео файла"""
        try:
            print(f"Начинаем извлечение аудио из: {video_path}")
            
            # Убедимся, что временная директория существует
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                print(f"Создана временная директория: {self.temp_dir}")
                
            # Создаем абсолютный путь к файлу
            audio_path = os.path.abspath(os.path.join(self.temp_dir, "extracted_audio.wav"))
            print(f"Путь к аудиофайлу: {audio_path}")
            
            print(f"Извлечение аудио из видео в файл: {audio_path}")
            self.update_progress(75)
            
            print(f"FFmpeg доступен: {self.use_ffmpeg}")
            if self.use_ffmpeg:
                # Используем FFmpeg напрямую для извлечения аудио
                print("Используем FFmpeg напрямую для извлечения аудио...")
                
                try:
                    # Команда FFmpeg для извлечения аудио
                    ffmpeg_cmd = [
                        "ffmpeg", "-y",  # Перезаписывать существующие файлы
                        "-i", video_path,  # Входной файл
                        "-vn",  # Без видео
                        "-acodec", "pcm_s16le",  # 16-бит PCM
                        "-ar", "16000",  # Частота 16 кГц
                        "-ac", "1",  # Моно
                        audio_path  # Выходной файл
                    ]
                    
                    print("Выполняем команду FFmpeg...")
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        print("FFmpeg выполнен успешно")
                        
                        # Проверяем, что файл создан
                        if os.path.exists(audio_path):
                            file_size = os.path.getsize(audio_path)
                            if file_size > 0:
                                print(f"Аудио успешно извлечено: {audio_path} ({file_size} байт)")
                                self.update_progress(90)
                                return True, audio_path
                            else:
                                return False, "Созданный аудиофайл пуст"
                        else:
                            return False, "Аудиофайл не был создан"
                    else:
                        print(f"Ошибка FFmpeg: {result.stderr}")
                        return False, f"Ошибка FFmpeg: {result.stderr}"
                        
                except Exception as e:
                    print(f"Ошибка при выполнении FFmpeg: {e}")
                    return False, f"Ошибка при выполнении FFmpeg: {e}"
            else:
                # Используем альтернативный метод без ffmpeg
                try:
                    # Загружаем видео
                    print("Загрузка видео...")
                    self.update_progress(75)
                    video = VideoFileClip(video_path)
                    
                    if video.audio is None:
                        return False, "В видеофайле нет аудиодорожки"
                    
                    print(f"Видео загружено. Длительность: {video.duration:.2f} сек")
                    self.update_progress(80)
                    
                    # Извлекаем аудио
                    print("Извлечение аудиодорожки...")
                    
                    # Пытаемся получить аудиодорожку через MoviePy
                    try:
                        # Получаем аудиоданные в виде NumPy массива
                        # Используем стандартный метод с более крупным буфером
                        audio_data = video.audio.to_soundarray(fps=16000, nbytes=2, buffersize=20000)
                        
                        # Преобразуем в моно, если стерео
                        if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
                            audio_data = np.mean(audio_data, axis=1)
                        
                        # Сохраняем в WAV файл
                        sf.write(audio_path, audio_data, 16000, subtype='PCM_16')
                        print(f"Аудио успешно извлечено и сохранено в {audio_path}")
                        self.update_progress(90)
                        
                        # Проверяем, что файл создан
                        if os.path.exists(audio_path):
                            print(f"Аудио успешно извлечено: {audio_path}")
                            return True, audio_path
                        else:
                            return False, "Файл аудио не был создан"
                        
                    except Exception as audio_err:
                        print(f"Ошибка при извлечении аудио напрямую: {audio_err}")
                        
                        # Пробуем через непосредственное использование moviepy без настройки ffmpeg
                        print("Попытка извлечения с помощью нативной функциональности moviepy...")
                        self.update_progress(82)
                        
                        try:
                            # Используем метод write_audiofile с минимальными аргументами
                            video.audio.write_audiofile(
                                audio_path,
                                fps=16000,         # Частота 16 кГц
                                nbytes=2,          # 16 бит
                                verbose=False,     # Без подробного вывода
                                logger=None        # Без логирования
                            )
                            print(f"Аудио успешно извлечено и сохранено в {audio_path}")
                            self.update_progress(90)
                            
                            # Проверяем, что файл создан
                            if os.path.exists(audio_path):
                                print(f"Аудио успешно извлечено: {audio_path}")
                                return True, audio_path
                            else:
                                return False, "Файл аудио не был создан"
                            
                        except Exception as alt_err:
                            print(f"Ошибка при извлечении аудио: {alt_err}")
                            self.update_progress(84)
                            
                            # Еще один метод - попытка использовать numpy напрямую
                            print("Пробуем еще один альтернативный метод...")
                            
                            try:
                                # Создаем очень короткий временный WAV файл
                                test_audio_path = os.path.join(self.temp_dir, "test_audio.wav")
                                
                                # Создаем тишину длительностью 1 секунда
                                rate = 16000
                                silence = np.zeros(rate, dtype=np.int16)
                                sf.write(test_audio_path, silence, rate)
                                
                                # Проверяем наличие аудиодорожки
                                if video.audio is None:
                                    # Если нет аудио, создаем тестовый файл с тишиной
                                    sf.write(audio_path, np.zeros(int(video.duration * 16000), dtype=np.int16), 16000)
                                    print("Создан пустой аудиофайл, так как видео не содержит аудиодорожки")
                                else:
                                    # Используем блочную обработку вместо одной большой операции
                                    print("Извлечение аудио блоками...")
                                    # Разбиваем видео на 10-секундные блоки
                                    block_duration = 10  # секунд
                                    num_blocks = int(np.ceil(video.duration / block_duration))
                                    
                                    # Создаем массив для хранения всего аудио
                                    full_audio = np.array([], dtype=np.float32)
                                    
                                    for i in range(num_blocks):
                                        start_time = i * block_duration
                                        end_time = min((i + 1) * block_duration, video.duration)
                                        
                                        print(f"Обработка блока {i+1}/{num_blocks}: {start_time:.1f}-{end_time:.1f} сек")
                                        
                                        # Создаем подклип для текущего блока
                                        block_clip = video.subclip(start_time, end_time)
                                        
                                        try:
                                            # Извлекаем аудио из блока
                                            block_audio = block_clip.audio.to_soundarray(fps=16000, nbytes=2)
                                            
                                            # Если стерео, преобразуем в моно
                                            if len(block_audio.shape) > 1 and block_audio.shape[1] > 1:
                                                block_audio = np.mean(block_audio, axis=1)
                                                
                                            # Добавляем к полному аудио
                                            full_audio = np.append(full_audio, block_audio)
                                            
                                        except Exception as block_err:
                                            print(f"Ошибка при обработке блока {i+1}: {block_err}")
                                            # Добавляем тишину вместо ошибочного блока
                                            silence_duration = end_time - start_time
                                            full_audio = np.append(full_audio, np.zeros(int(silence_duration * 16000), dtype=np.float32))
                                        
                                        # Закрываем подклип
                                        block_clip.close()
                                        
                                        # Обновляем прогресс (от 85% до 90%)
                                        progress = 85 + int((i + 1) * 5 / num_blocks)
                                        self.update_progress(progress)
                                    
                                    # Сохраняем полное аудио
                                    sf.write(audio_path, full_audio, 16000, subtype='PCM_16')
                                    print(f"Аудио успешно извлечено блочным методом и сохранено в {audio_path}")
                                    
                                    # Проверяем, что файл создан
                                    if os.path.exists(audio_path):
                                        print(f"Аудио успешно извлечено: {audio_path}")
                                        return True, audio_path
                                    else:
                                        return False, "Файл аудио не был создан"
                            
                            except Exception as np_err:
                                print(f"Все методы извлечения аудио не удались: {np_err}")
                                return False, f"Не удалось извлечь аудио из видео: {np_err}"
                    
                    video.close()
                    
                except Exception as ve:
                    print(f"Ошибка при извлечении аудио из видео: {str(ve)}")
                    return False, f"Не удалось извлечь аудио из видео: {str(ve)}"
            
            # Проверяем, что файл был создан
            if not os.path.exists(audio_path):
                return False, f"Не удалось создать аудиофайл: {audio_path}"
            
            # Проверяем, что файл не пуст
            if os.path.getsize(audio_path) == 0:
                return False, "Созданный аудиофайл пуст"
                
            print(f"Аудио успешно извлечено, размер файла: {os.path.getsize(audio_path)/1024/1024:.2f} МБ")
            return True, audio_path
        except Exception as e:
            print(f"Ошибка при извлечении аудио из видео: {str(e)}")
            return False, f"Ошибка при извлечении аудио: {str(e)}"
    
    def transcribe_video(self, video_path):
        """Транскрибация видео файла"""
        # Проверяем существование файла
        if not os.path.exists(video_path):
            return False, f"Видеофайл не найден: {video_path}"
            
        try:
            # Получаем информацию о видео
            video_info = VideoFileClip(video_path)
            print(f"Видео загружено: {os.path.basename(video_path)}")
            
            video_info.close()
            
            # Шаг 1: Извлекаем аудио из видео
            print("\nШаг 1: Извлечение аудио из видео")
            success, audio_path = self.extract_audio_from_video(video_path)
            if not success:
                return False, audio_path  # возвращаем сообщение об ошибке
            
            # Шаг 2: Транскрибируем полученное аудио
            print("\nШаг 2: Транскрибация аудио")
            return self.transcribe_audio(audio_path)
        except Exception as e:
            print(f"Ошибка при обработке видео: {str(e)}")
            return False, f"Ошибка при обработке видео: {str(e)}"
    
    def download_youtube(self, url):
        """Загрузка видео с YouTube"""
        try:
            print(f"Загрузка видео с YouTube: {url}")
            self.update_progress(10)
            
            # Нормализация YouTube URL
            url = self.normalize_youtube_url(url)
            if not url:
                return False, "Некорректный формат URL YouTube"
            
            # Убедимся, что временная директория существует
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                
            video_path = os.path.abspath(os.path.join(self.temp_dir, "youtube_video.mp4"))
            
            # Инициализируем объект YouTube
            print("Получение информации о видео...")
            self.update_progress(15)
            
            # Добавляем обработку ошибок сети с повтором
            max_retries = 3
            connection_error = None
            yt = None
            
            # Настройка прокси для обхода возможных блокировок API
            # Используем только если есть проблемы с соединением
            proxies = None
            
            for retry in range(max_retries):
                try:
                    # Создаем объект YouTube с дополнительными параметрами
                    yt = pytubefix.YouTube(
                        url,
                        use_oauth=False,
                        allow_oauth_cache=True,
                        proxies=proxies
                    )
                    # Проверяем, что можем получить базовую информацию
                    if yt.title:
                        break
                except pytubefix.exceptions.RegexMatchError as e:
                    # Проблема с форматом URL
                    return False, f"Неверный формат URL: {str(e)}"
                except pytubefix.exceptions.VideoUnavailable as e:
                    # Видео недоступно
                    return False, f"Видео недоступно: {str(e)}"
                except (pytubefix.exceptions.PytubeError, Exception) as e:
                    connection_error = str(e)
                    if "HTTP Error 400" in connection_error or "Bad Request" in connection_error:
                        # Возможно, блокировка API, пробуем с другими параметрами
                        if retry == 0:
                            print("Получен HTTP Error 400, пробуем альтернативные методы доступа...")
                    else:
                        print(f"Ошибка при подключении (попытка {retry+1}/{max_retries}): {connection_error}")
                    
                    # При повторе пытаемся использовать другие параметры
                    time.sleep(2 * (retry + 1))  # Увеличиваем задержку с каждой попыткой
            
            if yt is None:
                return False, f"Не удалось подключиться к YouTube после {max_retries} попыток: {connection_error}"
            
            # Получаем и выводим информацию о видео
            try:
                print(f"Название видео: {yt.title}")
                print(f"Длительность: {yt.length} сек")
                print(f"Автор: {yt.author}")
                self.update_progress(20)
            except Exception as info_err:
                pass
            
            # Получаем доступные потоки
            print("Получение доступных форматов видео...")
            self.update_progress(25)
            
            try:
                # Устанавливаем повторы для получения потоков
                stream = None
                streams_error = None
                
                for retry in range(max_retries):
                    try:
                        # Сначала пробуем прогрессивные потоки (с аудио)
                        video_streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution')
                        
                        # Ищем самое качественное видео с аудио
                        stream = video_streams.last()
                        if not stream:
                            # Если не нашли прогрессивный поток, попробуем любой с аудио
                            stream = yt.streams.filter(only_audio=False).first()
                            
                        if not stream:
                            # Если всё ещё нет подходящего потока, возьмем только аудио
                            stream = yt.streams.filter(only_audio=True).first()
                        
                        if stream:
                            break
                    except Exception as e:
                        streams_error = str(e)
                        print(f"Ошибка при получении потоков (попытка {retry+1}/{max_retries}): {streams_error}")
                        time.sleep(2 * (retry + 1))
                
                if not stream:
                    return False, f"Не удалось найти подходящий поток для загрузки: {streams_error}"
                
                print(f"Выбран поток: {getattr(stream, 'resolution', 'аудио')}, {getattr(stream, 'fps', 'N/A')}fps")
                self.update_progress(30)
            except Exception as stream_err:
                print(f"Ошибка при получении потоков: {stream_err}")
                return False, f"Ошибка при получении форматов видео: {stream_err}"
            
            # Устанавливаем обработчик прогресса
            def progress_callback(stream, chunk, bytes_remaining):
                total_size = stream.filesize
                bytes_downloaded = total_size - bytes_remaining
                percentage = (bytes_downloaded / total_size) * 100
                # Пересчитываем прогресс для диапазона 30-70%
                progress_value = 30 + int(percentage * 0.4)
                self.update_progress(progress_value)
                print(f"\rЗагрузка видео: {percentage:.1f}%", end="")
            
            # Регистрируем обработчик
            yt.register_on_progress_callback(progress_callback)
            
            # Загружаем видео
            print("Начинаю загрузку видео...")
            try:
                stream.download(output_path=self.temp_dir, filename="youtube_video.mp4")
                print("\nЗагрузка видео завершена!")
                self.update_progress(70)
            except Exception as download_err:
                print(f"\nОшибка при загрузке видео: {download_err}")
                return False, f"Ошибка при загрузке видео: {download_err}"
            
            # Проверяем, что файл был загружен
            if not os.path.exists(video_path):
                return False, "Не удалось загрузить видео с YouTube"
                
            print(f"Видео успешно загружено: {video_path}")
            print(f"Размер файла: {os.path.getsize(video_path)/1024/1024:.2f} МБ")
            
            return True, video_path
        except Exception as e:
            print(f"Ошибка при загрузке видео с YouTube: {str(e)}")
            return False, f"Ошибка при загрузке видео с YouTube: {str(e)}"
            
    def normalize_youtube_url(self, url):
        """Нормализует URL YouTube для корректной обработки"""
        # Очищаем URL от лишних пробелов
        url = url.strip()
        
        # Проверяем базовые шаблоны YouTube URL
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube-nocookie\.com)',
            r'(https?://)?(www\.)?m\.youtube\.com',
        ]
        
        # Проверяем, соответствует ли URL хотя бы одному шаблону
        if not any(re.match(pattern, url) for pattern in youtube_patterns):
            # Если URL не соответствует шаблонам, проверим, не является ли это просто ID видео
            video_id_pattern = r'^[a-zA-Z0-9_-]{11}$'
            if re.match(video_id_pattern, url):
                # Если это похоже на ID видео, добавляем стандартный префикс
                return f'https://www.youtube.com/watch?v={url}'
            else:
                # Не удалось распознать как URL YouTube
                return None
        
        # Извлекаем ID видео из URL
        video_id = None
        
        # Для формата youtu.be/ID
        if 'youtu.be' in url:
            match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
            if match:
                video_id = match.group(1)
        # Для формата youtube.com/watch?v=ID
        elif 'youtube.com/watch' in url:
            match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
            if match:
                video_id = match.group(1)
        # Для формата youtube.com/v/ID
        elif '/v/' in url:
            match = re.search(r'/v/([a-zA-Z0-9_-]+)', url)
            if match:
                video_id = match.group(1)
        # Для формата youtube.com/embed/ID
        elif '/embed/' in url:
            match = re.search(r'/embed/([a-zA-Z0-9_-]+)', url)
            if match:
                video_id = match.group(1)
        
        # Если ID видео найден, формируем стандартный URL
        if video_id:
            return f'https://www.youtube.com/watch?v={video_id}'
        
        # Если не удалось извлечь ID, возвращаем исходный URL (pytube попытается его обработать)
        return url
    
    def transcribe_youtube(self, url):
        """Транскрибация видео с YouTube"""
        # Сбрасываем прогресс
        self.update_progress(5)
        
        # Шаг 1: Загрузка видео с YouTube
        print("Шаг 1: Загрузка видео с YouTube")
        success, video_path = self.download_youtube(url)
        if not success:
            return False, video_path  # Возвращаем сообщение об ошибке
        
        # Уже достигли 70% после загрузки видео
        
        # Шаг 2: Извлечение аудио из видео
        print("\nШаг 2: Извлечение аудио из видео")
        success, audio_path = self.extract_audio_from_video(video_path)
        if not success:
            return False, audio_path
            
        # Достигли 90% после извлечения аудио
            
        # Шаг 3: Транскрибация аудио
        # Установим начальный прогресс для транскрибации на 90%
        print("\nШаг 3: Транскрибация аудио")
        
        # Подготовим функцию-обёртку для обновления прогресса
        original_callback = self.progress_callback
        
        def progress_wrapper(value):
            # Преобразуем значение 0-100 от транскрибации в 90-100 для общего прогресса
            if value <= 100:
                mapped_value = 90 + value / 10  # От 90% до 100%
                if original_callback:
                    original_callback(mapped_value)
        
        # Временно заменяем callback на обёртку
        self.progress_callback = progress_wrapper
        
        # Выполняем транскрибацию
        result = self.transcribe_audio(audio_path)
        
        # Восстанавливаем оригинальный callback
        self.progress_callback = original_callback
        
        return result
    
    def transcribe_zoom_meeting(self, zoom_recording_path):
        """Транскрибация записи Zoom"""
        # Zoom сохраняет записи в формате mp4, поэтому используем метод для транскрибации видео
        return self.transcribe_video(zoom_recording_path)
    
    def transcribe_streaming_audio(self, audio_stream_url):
        """Транскрибация потокового аудио"""
        try:
            # Сохраняем поток во временный файл
            temp_audio_file = os.path.join(self.temp_dir, "stream_audio.wav")
            
            if self.use_ffmpeg:
                # Используем ffmpeg для захвата потока
                command = [
                    "ffmpeg", 
                    "-y",  # Перезаписывать существующие файлы
                    "-i", audio_stream_url,  # Входной поток
                    "-ar", "16000",  # Частота 16 кГц
                    "-ac", "1",      # Моно
                    "-f", "wav",     # Формат WAV
                    temp_audio_file  # Выходной файл
                ]
                
                # Запускаем команду
                subprocess.run(command, check=True)
            else:
                # Используем sounddevice для записи и сохранения потока
                # Это временное решение, без настоящего потока
                print("Запись аудио с микрофона на 10 секунд...")
                
                # Запись аудио с микрофона
                myrecording = sd.rec(int(10 * self.sample_rate), 
                                   samplerate=self.sample_rate,
                                   channels=1,
                                   dtype='int16')
                sd.wait()  # Ожидаем окончания записи
                
                # Сохраняем запись в wav файл
                sf.write(temp_audio_file, myrecording, self.sample_rate)
                
                print(f"Запись сохранена в {temp_audio_file}")
            
            # Транскрибируем сохраненный аудиофайл
            return self.transcribe_audio(temp_audio_file)
        except Exception as e:
            print(f"Ошибка при транскрибации потокового аудио: {str(e)}")
            return False, f"Ошибка при транскрибации потока: {str(e)}"
    
    def process_audio_file(self, file_path):
        """Обработка аудио файла"""
        # Проверяем расширение файла
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension in ['.mp3', '.wav', '.m4a', '.aac', '.flac']:
            # Транскрибируем аудио напрямую
            return self.transcribe_audio(file_path)
        elif file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            # Если это видеофайл, извлекаем аудио и транскрибируем
            return self.transcribe_video(file_path)
        else:
            return False, f"Неподдерживаемый формат файла: {file_extension}"
    
    def set_language(self, language_code):
        """Установка языка для транскрибации"""
        self.language = language_code
        print(f"Установлен язык транскрибации: {language_code}")
        
    def set_model_size(self, model_size):
        """Установка размера модели Vosk"""
        # Проверяем, является ли входной параметр одним из стандартных размеров модели
        standard_sizes = ["tiny", "base", "small", "medium", "large"]
        
        if model_size in standard_sizes:
            # Используем локальную модель из директории проекта
            model_dir = os.path.join(self.project_dir, "model_small")
            
            if os.path.exists(model_dir):
                self.model_size = model_dir
                self.model = None  # Сбрасываем текущую модель
                print(f"Выбран размер модели: {model_size}, используем: {model_dir}")
                return True
            else:
                print(f"Модель {model_size} не найдена по пути: {model_dir}")
                return False
        elif os.path.exists(model_size):
            # Если указан полный путь к существующей директории
            self.model_size = os.path.abspath(model_size)
            self.model = None
            print(f"Установлен пользовательский путь к модели Vosk: {self.model_size}")
            return True
        else:
            # Проверяем, может быть это относительный путь
            relative_path = os.path.join(self.project_dir, model_size)
            if os.path.exists(relative_path):
                self.model_size = relative_path
                self.model = None
                print(f"Использую модель по относительному пути: {relative_path}")
                return True
                
            # Если ничего не подошло, используем модель по умолчанию
            default_path = os.path.join(self.project_dir, "model_small")
            if os.path.exists(default_path):
                self.model_size = default_path
                self.model = None
                print(f"Некорректный путь к модели: {model_size}, используем модель по умолчанию: {default_path}")
                return True
            else:
                print(f"Не удалось найти модель. Проверьте наличие директории 'model_small' в корне проекта.")
                return False
    
    def clean_temp_files(self):
        """Очистка временных файлов"""
        try:
            if os.path.exists(self.temp_dir):
                for file_name in os.listdir(self.temp_dir):
                    file_path = os.path.join(self.temp_dir, file_name)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                            print(f"Удален временный файл: {file_path}")
                    except Exception as e:
                        print(f"Ошибка при удалении {file_path}: {e}")
                print("Временные файлы очищены")
            return True
        except Exception as e:
            print(f"Ошибка при очистке временных файлов: {str(e)}")
            return False
    
    def record_microphone(self, duration=10):
        """Запись аудио с микрофона и транскрибация"""
        try:
            print(f"Запись аудио с микрофона на {duration} секунд...")
            
            # Убедимся, что временная директория существует
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                
            temp_audio_file = os.path.join(self.temp_dir, "mic_recording.wav")
            
            # Запись аудио с микрофона
            myrecording = sd.rec(int(duration * self.sample_rate), 
                               samplerate=self.sample_rate,
                               channels=1,
                               dtype='int16')
            
            # Ожидаем окончания записи
            sd.wait()
            
            # Сохраняем запись в wav файл
            sf.write(temp_audio_file, myrecording, self.sample_rate)
            
            print(f"Запись сохранена в {temp_audio_file}")
            
            # Транскрибируем записанное аудио
            return self.transcribe_audio(temp_audio_file)
            
        except Exception as e:
            print(f"Ошибка при записи аудио с микрофона: {str(e)}")
            return False, f"Ошибка при записи аудио: {str(e)}"
    
    def set_progress_callback(self, callback):
        """Устанавливает функцию обратного вызова для отображения прогресса"""
        self.progress_callback = callback
        
    def update_progress(self, progress):
        """Обновляет прогресс, если установлен callback"""
        try:
            if self.progress_callback:
                self.progress_callback(progress)
        except Exception as e:
            # Игнорируем ошибки прогресса
            pass 