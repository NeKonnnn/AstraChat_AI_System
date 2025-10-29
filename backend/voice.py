import os
import sys
import torch
import queue
import sounddevice as sd
import re
import time
import json
from pathlib import Path

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
else:
    VOSK_AVAILABLE = False
    print("Используется llm-svc для распознавания речи")

from backend.agent import ask_agent
from backend.memory import save_to_memory

# Попытка импорта librosa для изменения темпа аудио
try:
    import librosa
    import librosa.effects
    librosa_available = True
    print("librosa доступна для изменения темпа аудио")
except ImportError:
    librosa_available = False
    print("librosa не установлена, изменение темпа аудио будет недоступно")

# Константы
SAMPLE_RATE = 16000
VOSK_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_small")
SILERO_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'silero_models')
MODELS_URLS = {
    'ru': 'https://models.silero.ai/models/tts/ru/v3_1_ru.pt',
    'en': 'https://models.silero.ai/models/tts/en/v3_en.pt'
}
MODEL_PATHS = {
    'ru': os.path.join(SILERO_MODELS_DIR, 'ru', 'model.pt'),
    'en': os.path.join(SILERO_MODELS_DIR, 'en', 'model.pt')
}

# Глобальные переменные для TTS
models = {}
tts_model_loaded = False
pyttsx3_engine = None

# Попытка импорта резервной библиотеки TTS
try:
    import pyttsx3
    pyttsx3_available = True
except ImportError:
    pyttsx3_available = False
    print("ПРЕДУПРЕЖДЕНИЕ: pyttsx3 не установлен, запасной TTS будет недоступен")

#---------- Функции для изменения темпа аудио ----------#

def change_audio_speed(audio, sample_rate, speed_factor):
    """Изменяет скорость воспроизведения аудио без изменения частоты"""
    if not librosa_available:
        print("librosa недоступна, возвращаю оригинальное аудио")
        return audio
    
    try:
        # Конвертируем torch tensor в numpy array
        if isinstance(audio, torch.Tensor):
            audio_numpy = audio.cpu().numpy()
        else:
            audio_numpy = audio
        
        # Изменяем темп аудио
        audio_fast = librosa.effects.time_stretch(audio_numpy, rate=speed_factor)
        
        # Конвертируем обратно в torch tensor
        if isinstance(audio, torch.Tensor):
            return torch.from_numpy(audio_fast)
        else:
            return audio_fast
            
    except Exception as e:
        print(f"Ошибка при изменении темпа аудио: {e}")
        return audio

#---------- Функции для озвучивания текста (Silero TTS) ----------#

def init_pyttsx3():
    """Инициализация резервной системы pyttsx3"""
    global pyttsx3_engine
    if pyttsx3_available:
        try:
            pyttsx3_engine = pyttsx3.init()
            # Настройка голоса
            voices = pyttsx3_engine.getProperty('voices')
            for voice in voices:
                if 'russian' in str(voice).lower() or 'ru' in str(voice).lower():
                    pyttsx3_engine.setProperty('voice', voice.id)
                    break
            return True
        except Exception as e:
            print(f"Ошибка инициализации pyttsx3: {e}")
    return False

def download_model(lang):
    """Загрузка модели из интернета, если она отсутствует"""
    model_path = MODEL_PATHS[lang]
    model_url = MODELS_URLS[lang]
    
    # Создаем директорию, если не существует
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    if not os.path.isfile(model_path):
        print(f"Загружаю модель {lang} из {model_url}")
        try:
            torch.hub.download_url_to_file(model_url, model_path)
            print(f"Модель {lang} успешно загружена")
            return True
        except Exception as e:
            print(f"Ошибка загрузки модели {lang}: {e}")
            return False
    return True

def load_model(lang):
    """Загрузка модели из локального файла"""
    global models, tts_model_loaded
    
    if lang in models:
        return True
        
    model_path = MODEL_PATHS[lang]
    
    try:
        if os.path.isfile(model_path):
            model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
            model.to('cpu')
            models[lang] = model
            tts_model_loaded = True
            return True
        else:
            print(f"Файл модели {lang} не найден")
            return False
    except Exception as e:
        print(f"Ошибка загрузки модели {lang}: {e}")
        return False

def init_tts():
    """Инициализация всей системы TTS"""
    global tts_model_loaded
    
    # Инициализация pyttsx3 как резервной системы
    pyttsx3_initialized = init_pyttsx3()
    
    # Пытаемся загрузить русскую модель
    if download_model('ru') and load_model('ru'):
        tts_model_loaded = True
    
    # Пытаемся загрузить английскую модель
    download_model('en') and load_model('en')

def split_text_into_chunks(text, max_chunk_size=1000):
    """Делит текст на части, длина каждой не превышает max_chunk_size символов"""
    # Разбиваем текст на предложения
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # Если добавление очередного предложения не превысит лимит,
        # то добавляем его к текущему фрагменту
        if len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def detect_language(text):
    """Простое определение языка текста"""
    # Подсчитываем кириллические символы
    cyrillic_count = sum(1 for char in text if 'а' <= char.lower() <= 'я' or char.lower() in 'ёіїєґ')
    
    # Если более 50% символов кириллические, считаем текст русским
    if cyrillic_count / max(1, len(text)) > 0.5:
        return 'ru'
    else:
        return 'en'

def speak_text_silero(text, speaker='baya', sample_rate=48000, lang=None, speech_rate=1.0, save_to_file=None):
    """Озвучивание текста с помощью Silero TTS"""
    global models
    
    if not text:
        return False
    
    # Определяем язык, если не указан
    if lang is None:
        lang = detect_language(text)
    
    # Проверяем, загружена ли нужная модель
    if lang not in models:
        if not load_model(lang):
            return False
    
    try:
        # Логируем параметры скорости речи
        print(f"Применяю скорость речи: {speech_rate}x")
        print(f"Исходная частота дискретизации: {sample_rate} Hz")
        
        # Используем стандартную частоту дискретизации для Silero
        effective_sample_rate = 48000  # Всегда используем максимальное качество
        
        print(f"Использую стандартную частоту дискретизации: {effective_sample_rate} Hz")
        print(f"Скорость речи будет изменена через изменение темпа аудио: {speech_rate}x")
        
        # Обрабатываем короткие тексты и проблемные символы
        if len(text.strip()) < 10:
            # Для коротких текстов добавляем контекст и заменяем проблемные символы
            text = f"Ответ: {text.replace(',', ' и ').replace('.', ' точка').replace('1', 'один').replace('2', 'два').replace('3', 'три').replace('4', 'четыре').replace('5', 'пять')}"
        
        # Разбиваем текст на части, если он длинный
        chunks = split_text_into_chunks(text)
        all_audio = []
        
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.3)  # Пауза между частями
                
            try:
                audio = models[lang].apply_tts(
                    text=chunk, 
                    speaker=speaker,
                    sample_rate=effective_sample_rate,
                    put_accent=False,  # Убираем акценты для стабильности
                    put_yo=False       # Убираем ё для стабильности
                )
                
                # Изменяем темп аудио для изменения скорости речи
                if speech_rate != 1.0:
                    print(f"Изменяю темп аудио с {speech_rate}x")
                    audio = change_audio_speed(audio, effective_sample_rate, speech_rate)
                
                if save_to_file:
                    all_audio.append(audio)
                else:
                    sd.play(audio, effective_sample_rate)
                    sd.wait()
                    
            except Exception as chunk_error:
    
                # Пытаемся с упрощенными настройками
                try:
                    simplified_chunk = chunk.replace(',', '').replace('.', '').replace('!', '').replace('?', '')
                    if simplified_chunk.strip():
                        audio = models[lang].apply_tts(
                            text=simplified_chunk, 
                            speaker='baya',  # Принудительно используем простой голос
                            sample_rate=effective_sample_rate,  # Используем ту же частоту
                            put_accent=False,
                            put_yo=False
                        )
                        
                        # Изменяем темп аудио для изменения скорости речи
                        if speech_rate != 1.0:
                            print(f"Fallback: изменяю темп аудио с {speech_rate}x")
                            audio = change_audio_speed(audio, effective_sample_rate, speech_rate)
                        
                        if save_to_file:
                            all_audio.append(audio)
                        else:
                            sd.play(audio, effective_sample_rate)
                            sd.wait()
                except Exception as fallback_error:
                    print(f"Fallback тоже не сработал: {fallback_error}")
                    continue
        
        if save_to_file and all_audio:
            try:
                import torch
                import scipy.io.wavfile
                
                # Объединяем все части аудио
                combined_audio = torch.cat(all_audio, dim=0)
                audio_numpy = combined_audio.cpu().numpy()
                
                # Нормализуем аудио
                if audio_numpy.max() <= 1.0:
                    audio_numpy = (audio_numpy * 32767).astype('int16')
                
                # Сохраняем в файл с учетом измененной частоты дискретизации
                scipy.io.wavfile.write(save_to_file, effective_sample_rate, audio_numpy)
                print(f"Аудио сохранено в {save_to_file}")
                return True
                
            except Exception as save_error:
                print(f"Ошибка сохранения аудио: {save_error}")
                return False
        
        return True
    except Exception as e:
        print(f"Ошибка при синтезе речи через Silero: {e}")
        import traceback
        traceback.print_exc()
        return False

def speak_text_pyttsx3(text, speech_rate=1.0):
    """Озвучивание текста с помощью pyttsx3"""
    global pyttsx3_engine
    
    if not text or not pyttsx3_engine:
        return False
    
    try:
        # Устанавливаем скорость речи
        rate = int(200 * speech_rate)
        print(f"pyttsx3: устанавливаю скорость речи {speech_rate}x (rate={rate})")
        pyttsx3_engine.setProperty('rate', rate)  # Базовая скорость 200
        pyttsx3_engine.say(text)
        pyttsx3_engine.runAndWait()
        return True
    except Exception as e:
        print(f"Ошибка при синтезе речи через pyttsx3: {e}")
        return False

def speak_text(text, speaker='baya', voice_id='ru', speech_rate=1.0, save_to_file=None):
    """Основная функция озвучивания текста"""
    print(f"🔧 speak_text вызвана с параметрами: speaker={speaker}, voice_id={voice_id}, speech_rate={speech_rate}")
    
    # Если используем llm-svc, вызываем его API
    if USE_LLM_SVC:
        try:
            print(f"[LLM-SVC] Синтез речи через llm-svc")
            from backend.llm_client import synthesize_speech_llm_svc
            
            # Определяем язык
            language = 'ru' if voice_id == 'ru' else 'en'
            
            # Вызываем llm-svc для синтеза
            audio_data = synthesize_speech_llm_svc(text, language, speaker, 48000, speech_rate)
            
            if audio_data and len(audio_data) > 0:
                if save_to_file:
                    # Сохраняем в файл
                    with open(save_to_file, 'wb') as f:
                        f.write(audio_data)
                    print(f"[LLM-SVC] Аудио сохранено в {save_to_file}")
                else:
                    # Воспроизводим
                    import io
                    import scipy.io.wavfile
                    audio_array = scipy.io.wavfile.read(io.BytesIO(audio_data))[1]
                    sd.play(audio_array, 48000)
                    sd.wait()
                    print(f"[LLM-SVC] Аудио воспроизведено")
                return True
            else:
                print(f"[LLM-SVC] Получены пустые аудио данные")
                return False
        except Exception as e:
            print(f"[LLM-SVC] Ошибка синтеза через llm-svc: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    if not text:
        return False
    
    # Пытаемся озвучить через Silero
    if tts_model_loaded and speak_text_silero(text, speaker, lang=voice_id, speech_rate=speech_rate, save_to_file=save_to_file):
        return True
    
    # Если не получилось, используем pyttsx3 (только для воспроизведения, не для сохранения)
    if not save_to_file and speak_text_pyttsx3(text, speech_rate):
        return True
    
    # Если ничего не сработало
    print("Не удалось озвучить текст:", text[:50] + "..." if len(text) > 50 else text)
    return False

#---------- Функции для распознавания речи (Vosk) ----------#

def check_vosk_model():
    """Проверка наличия модели распознавания речи"""
    if not os.path.exists(VOSK_MODEL_PATH):
        print(f"ОШИБКА: Модель распознавания речи не найдена в {VOSK_MODEL_PATH}")
        return False
    return True

def recognize_speech():
    """Распознавание речи с микрофона"""
    if not check_vosk_model():
        raise Exception("Модель распознавания речи не найдена")
    
    try:
        model = Model(VOSK_MODEL_PATH)
        q = queue.Queue()

        def callback(indata, frames, time, status):
            if status:
                print("Ошибка:", status, file=sys.stderr)
            q.put(bytes(indata))

        print("Скажи что-нибудь (Ctrl+C для выхода)...")
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                              channels=1, callback=callback):
            rec = KaldiRecognizer(model, SAMPLE_RATE)
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    return result.get("text", "")
    except Exception as e:
        print(f"Ошибка при распознавании речи: {e}")
        return ""

def recognize_speech_from_file(file_path):
    """Распознавание речи из аудиофайла используя ту же логику что и recognize_speech"""
    
    # Если используем llm-svc, вызываем его API
    if USE_LLM_SVC:
        try:
            print(f"[LLM-SVC] Распознавание речи через llm-svc: {file_path}")
            from backend.llm_client import transcribe_audio_llm_svc
            
            # Читаем файл
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            # Вызываем llm-svc
            result = transcribe_audio_llm_svc(audio_data, os.path.basename(file_path), "ru")
            print(f"[LLM-SVC] Распознанный текст: '{result}'")
            return result
        except Exception as e:
            print(f"[LLM-SVC] Ошибка распознавания через llm-svc: {e}")
            return ""
    
    # Локальное распознавание через Vosk
    if not check_vosk_model():
        raise Exception("Модель распознавания речи не найдена")
    
    try:
        import wave
        import numpy as np
        print(f"Обрабатываю файл: {file_path}")
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise Exception(f"Файл не найден: {file_path}")
        
        # Сначала проверим размер файла
        file_size = os.path.getsize(file_path)
        print(f"Размер файла: {file_size} байт")
        
        if file_size < 10:  # Минимальный размер любого аудиофайла
            print("Файл слишком мал для содержания аудио")
            return ""
        
        # Определяем формат файла и конвертируем в WAV если нужно
        converted_file_path = None
        try:
            # Пытаемся определить формат по содержимому
            with open(file_path, 'rb') as f:
                header = f.read(12)
            
            is_wav = header.startswith(b'RIFF') and b'WAVE' in header
            is_webm = header.startswith(b'\x1a\x45\xdf\xa3')  # WebM signature
            
            if not is_wav:
                print(f"Файл не в формате WAV, конвертирую...")
        
                
                try:
                    from pydub import AudioSegment
                    
                    # Загружаем аудио в любом формате
                    if is_webm:
                        print("Обнаружен WebM формат")
                        audio = AudioSegment.from_file(file_path, format="webm")
                    else:
                        print("Пытаюсь загрузить в автоматическом режиме")
                        audio = AudioSegment.from_file(file_path)
                    
                    # Конвертируем в нужный формат
                    audio = audio.set_frame_rate(SAMPLE_RATE)  # 16kHz
                    audio = audio.set_channels(1)  # моно
                    audio = audio.set_sample_width(2)  # 16-bit
                    
                    # Сохраняем как WAV
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    converted_file_path = os.path.join(temp_dir, f"converted_{os.path.basename(file_path)}.wav")
                    audio.export(converted_file_path, format="wav")
                    
            
                    file_path = converted_file_path
                    
                except ImportError:
                    print("pydub не установлен, не могу конвертировать из WebM")
                    return ""
                except Exception as e:
                    print(f"Ошибка конвертации: {e}")
                    # Продолжаем с исходным файлом
                    pass
        except Exception as e:
            print(f"Ошибка при определении формата: {e}")
            # Продолжаем с исходным файлом
        
        # Пытаемся открыть как WAV файл
        try:
            with wave.open(file_path, 'rb') as wf:
                # Получаем параметры файла
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                
        
                
                if nframes == 0:
                    print("Аудиофайл не содержит данных")
                    return ""
                
                # Читаем все аудиоданные
                frames = wf.readframes(nframes)
                
                if len(frames) == 0:
                    print("Не удалось прочитать аудиоданные")
                    return ""
                
                # Конвертируем в numpy массив для обработки
                if sampwidth == 1:
                    dtype = np.uint8
                elif sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 4:
                    dtype = np.int32
                else:
                    dtype = np.int16
                
                audio_array = np.frombuffer(frames, dtype=dtype)
                
                if len(audio_array) == 0:
                    print("Пустой аудио массив")
                    return ""
                
                # Конвертируем в моно если нужно
                if channels == 2:
                    print("Конвертирую стерео в моно")
                    if len(audio_array) % 2 != 0:
                        # Обрезаем до четного числа для правильного reshape
                        audio_array = audio_array[:-1]
                    audio_array = audio_array.reshape(-1, 2)
                    audio_array = np.mean(audio_array, axis=1).astype(dtype)
                    channels = 1
                
                # Конвертируем в 16-бит если нужно
                if sampwidth != 2:
                    print(f"Конвертирую разрядность с {sampwidth*8} на 16 бит")
                    if sampwidth == 1:
                        # 8-бит в 16-бит (unsigned to signed)
                        audio_array = ((audio_array.astype(np.float32) - 128) * 256).astype(np.int16)
                    elif sampwidth == 4:
                        # 32-бит в 16-бит
                        audio_array = (audio_array // 65536).astype(np.int16)
                    sampwidth = 2
                
                # Ресэмплинг если нужно (простой decimation/interpolation)
                if framerate != SAMPLE_RATE:
                    print(f"Конвертирую частоту с {framerate} на {SAMPLE_RATE}")
                    if len(audio_array) > 1:
                        # Простой ресэмплинг
                        ratio = SAMPLE_RATE / framerate
                        new_length = max(1, int(len(audio_array) * ratio))
                        indices = np.linspace(0, len(audio_array) - 1, new_length)
                        audio_array = np.interp(indices, np.arange(len(audio_array)), audio_array.astype(np.float32)).astype(np.int16)
                        framerate = SAMPLE_RATE
                
                # Конвертируем обратно в байты
                frames = audio_array.tobytes()
                
        
        
        except (wave.Error, EOFError, Exception) as e:
            print(f"Ошибка чтения WAV файла: {e}")
            print("Попытка чтения как raw аудио...")
            
            # Попытаемся обработать как raw аудио
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                    
                if len(raw_data) < 4:
                    print("Слишком мало данных в файле")
                    return ""
                
                # Попробуем интерпретировать как 16-бит аудио
                # Убираем возможный заголовок
                if raw_data.startswith(b'RIFF'):
                    # Пропускаем WAV заголовок (обычно 44 байта)
                    header_size = 44
                    if len(raw_data) > header_size:
                        raw_data = raw_data[header_size:]
                    else:
                        print("Файл содержит только заголовок")
                        return ""
                
                # Преобразуем в 16-битные сэмплы
                if len(raw_data) % 2 != 0:
                    raw_data = raw_data[:-1]  # Убираем лишний байт
                
                frames = raw_data
                framerate = SAMPLE_RATE
                sampwidth = 2
                channels = 1
                
        
                
            except Exception as e2:
                print(f"Ошибка чтения raw аудио: {e2}")
                return ""
        
        # Инициализируем модель распознавания
        model = Model(VOSK_MODEL_PATH)
        rec = KaldiRecognizer(model, framerate)
        
        print("Начинаю распознавание...")
        
        # Обрабатываем аудио порциями
        results = []
        chunk_size = framerate * sampwidth * channels // 10  # 0.1 секунды
        
        for i in range(0, len(frames), chunk_size):
            chunk = frames[i:i + chunk_size]
            if len(chunk) == 0:
                break
                
            if rec.AcceptWaveform(chunk):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text.strip():
                    results.append(text.strip())
                    print(f"Частичный результат: {text}")
        
        # Получаем финальный результат
        final_result = json.loads(rec.FinalResult())
        final_text = final_result.get("text", "")
        if final_text.strip():
            results.append(final_text.strip())
            print(f"Финальный результат: {final_text}")
        
        # Объединяем все результаты
        full_text = " ".join(results).strip()

        
        return full_text
        
    except Exception as e:
        print(f"Ошибка при распознавании речи из файла: {e}")
        import traceback
        traceback.print_exc()
        return ""  # Возвращаем пустую строку вместо исключения
    finally:
        # Очищаем временный файл если он был создан
        if converted_file_path and os.path.exists(converted_file_path):
            try:
                os.remove(converted_file_path)
                print(f"Удален временный файл: {converted_file_path}")
            except Exception as e:
                print(f"Не удалось удалить временный файл: {e}")
        pass

def run_voice():
    """Запуск голосового интерфейса в консоли"""
    # Проверяем наличие модели распознавания речи
    if not check_vosk_model():
        print("Модель распознавания речи не найдена.")
        raise Exception("Модель распознавания речи не найдена")
    
    # Инициализируем систему TTS
    init_tts()
    
    try:
        print("Голосовой режим запущен. Нажмите Ctrl+C для выхода.")
        while True:
            try:
                phrase = recognize_speech()
                if not phrase:
                    continue
                print("Вы:", phrase)
                save_to_memory("Пользователь", phrase)

                response = ask_agent(phrase)
                print("Агент:", response)
                speak_text(response)
                save_to_memory("Агент", response)
                
            except Exception as e:
                print(f"Ошибка в цикле распознавания: {e}")
                print("Попробуйте снова...")

    except KeyboardInterrupt:
        print("\nГолосовой режим завершён.")

# Инициализируем TTS при импорте модуля
init_tts() 