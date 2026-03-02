import os
import sys
import torch
import queue
import sounddevice as sd
import re
import time
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Проверяем, нужно ли использовать llm-svc  
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

# Импортируем Vosk только если НЕ используем llm-svc  
if not USE_LLM_SVC:
    try:
        from vosk import Model, KaldiRecognizer
        VOSK_AVAILABLE = True
    except ImportError:
        logger.warning("Vosk не доступен локально, требуется llm-svc")
        VOSK_AVAILABLE = False
else:
    VOSK_AVAILABLE = False
    logger.info("Используется llm-svc для распознавания речи")

# Импортируем функции связи с микросервисами
try:
    from backend.llm_client import synthesize_speech_llm_svc, transcribe_audio_llm_svc, transcribe_audio_whisperx_llm_svc
    from backend.agent_llm_svc import ask_agent
except ImportError:
    from llm_client import synthesize_speech_llm_svc, transcribe_audio_llm_svc, transcribe_audio_whisperx_llm_svc
    from agent_llm_svc import ask_agent

from backend.database.memory_service import save_to_memory

# Попытка импорта librosa для изменения темпа аудио  
try:
    import librosa
    import librosa.effects
    librosa_available = True
    logger.info("librosa доступна для изменения темпа аудио")
except ImportError:
    librosa_available = False
    logger.warning("librosa не установлена, изменение темпа аудио будет недоступно")

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

# Резервная библиотека pyttsx3  
try:
    import pyttsx3
    pyttsx3_available = True
except ImportError:
    pyttsx3_available = False

def change_audio_speed(audio, sample_rate, speed_factor):
    """Изменяет скорость воспроизведения аудио  """
    if not librosa_available:
        return audio
    try:
        if isinstance(audio, torch.Tensor):
            audio_numpy = audio.cpu().numpy()
        else:
            audio_numpy = audio
        audio_fast = librosa.effects.time_stretch(audio_numpy, rate=speed_factor)
        if isinstance(audio, torch.Tensor):
            return torch.from_numpy(audio_fast)
        else:
            return audio_fast
    except Exception as e:
        logger.error(f"Ошибка при изменении темпа аудио: {e}")
        return audio

def init_pyttsx3():
    """Инициализация резервной системы pyttsx3  """
    global pyttsx3_engine
    if pyttsx3_available:
        try:
            pyttsx3_engine = pyttsx3.init()
            voices = pyttsx3_engine.getProperty('voices')
            for voice in voices:
                if 'russian' in str(voice).lower() or 'ru' in str(voice).lower():
                    pyttsx3_engine.setProperty('voice', voice.id)
                    break
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации pyttsx3: {e}")
    return False

def download_model(lang):
    """Загрузка модели из интернета  """
    if USE_LLM_SVC: return True # В режиме сервиса скачивание на бэк не нужно
    model_path = MODEL_PATHS[lang]
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    if not os.path.isfile(model_path):
        try:
            torch.hub.download_url_to_file(MODELS_URLS[lang], model_path)
            return True
        except: return False
    return True

def load_model(lang):
    """Загрузка модели из локального файла  """
    global models, tts_model_loaded
    if USE_LLM_SVC: return False
    if lang in models: return True
    model_path = MODEL_PATHS[lang]
    try:
        if os.path.isfile(model_path):
            models[lang] = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
            models[lang].to('cpu')
            tts_model_loaded = True
            return True
        return False
    except: return False

def init_tts():
    """Инициализация системы TTS"""
    global tts_model_loaded
    if USE_LLM_SVC:
        logger.info("TTS инициализирован в режиме микросервиса")
        return
    init_pyttsx3()
    if download_model('ru') and load_model('ru'):
        tts_model_loaded = True
    download_model('en') and load_model('en')

def split_text_into_chunks(text, max_chunk_size=1000):
    """Разделение текста на предложения  """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
            current_chunk += sentence + " "
        else:
            if current_chunk: chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    if current_chunk: chunks.append(current_chunk.strip())
    return chunks

def detect_language(text):
    """Определение языка  """
    cyrillic_count = sum(1 for char in text if 'а' <= char.lower() <= 'я' or char.lower() in 'ёіїєґ')
    return 'ru' if cyrillic_count / max(1, len(text)) > 0.5 else 'en'

def speak_text_silero(text, speaker='baya', sample_rate=48000, lang=None, speech_rate=1.0, save_to_file=None):
    """Озвучивание текста локально через Silero  """
    global models
    if not text: return False
    if lang is None: lang = detect_language(text)
    if lang not in models:
        if not load_model(lang): return False
    try:
        effective_sample_rate = 48000
        if len(text.strip()) < 10:
            text = f"Ответ: {text.replace(',', ' и ').replace('.', ' точка').replace('1', 'один').replace('2', 'два').replace('3', 'три').replace('4', 'четыре').replace('5', 'пять')}"
        chunks = split_text_into_chunks(text)
        all_audio = []
        for i, chunk in enumerate(chunks):
            audio = models[lang].apply_tts(text=chunk, speaker=speaker, sample_rate=effective_sample_rate, put_accent=False, put_yo=False)
            if speech_rate != 1.0: audio = change_audio_speed(audio, effective_sample_rate, speech_rate)
            if save_to_file: all_audio.append(audio)
            else: sd.play(audio, effective_sample_rate); sd.wait()
        if save_to_file and all_audio:
            import scipy.io.wavfile
            combined_audio = torch.cat(all_audio, dim=0)
            audio_numpy = combined_audio.cpu().numpy()
            if audio_numpy.max() <= 1.0: audio_numpy = (audio_numpy * 32767).astype('int16')
            scipy.io.wavfile.write(save_to_file, effective_sample_rate, audio_numpy)
            return True
        return True
    except Exception as e:
        logger.error(f"Ошибка Silero: {e}")
        return False

def speak_text_pyttsx3(text, speech_rate=1.0):
    """Озвучивание текста через pyttsx3  """
    global pyttsx3_engine
    if not text or not pyttsx3_engine: return False
    try:
        pyttsx3_engine.setProperty('rate', int(200 * speech_rate))
        pyttsx3_engine.say(text); pyttsx3_engine.runAndWait()
        return True
    except: return False

def speak_text(text, speaker='baya', voice_id='ru', speech_rate=1.0, save_to_file=None):
    """Озвучивание текста (ПРИОРИТЕТ СЕРВИСУ)"""
    if USE_LLM_SVC:
        try:
            logger.info(f"[SVC] Синтез через микросервис")
            # Русские спикеры Silero — всегда используем русскую модель
            # Русская модель нормально справляется с английскими словами в тексте
            ru_speakers = {'baya', 'kseniya', 'xenia', 'eugene', 'aidar'}
            if speaker in ru_speakers:
                lang = "ru"
            else:
                cyrillic = sum(1 for c in text if 'а' <= c.lower() <= 'я' or c.lower() in 'ёіїєґ')
                lang = "ru" if cyrillic / max(1, len(text)) > 0.3 else "en"
            audio_data = synthesize_speech_llm_svc(
                text=text, 
                language=lang, 
                speaker=speaker, 
                sample_rate=48000, 
                speech_rate=speech_rate
            )
            if audio_data:
                if save_to_file:
                    with open(save_to_file, 'wb') as f: f.write(audio_data)
                else:
                    import io, scipy.io.wavfile
                    audio_array = scipy.io.wavfile.read(io.BytesIO(audio_data))[1]
                    sd.play(audio_array, 48000); sd.wait()
                return True
        except Exception as e:
            logger.error(f"Сервис TTS недоступен: {e}. Пробуем локально.")
    
    if not text: return False
    if tts_model_loaded and speak_text_silero(text, speaker, lang=voice_id, speech_rate=speech_rate, save_to_file=save_to_file):
        return True
    if not save_to_file and speak_text_pyttsx3(text, speech_rate):
        return True
    return False

# ---------- Функции для распознавания речи (Vosk) ---------- #

def check_vosk_model():
    """Проверка наличия модели распознавания речи  """
    if USE_LLM_SVC: return True
    if not os.path.exists(VOSK_MODEL_PATH):
        print(f"ОШИБКА: Модель распознавания речи не найдена в {VOSK_MODEL_PATH}")
        return False
    return True

def recognize_speech():
    """Распознавание речи с микрофона  """
    if not check_vosk_model():
        raise Exception("Модель распознавания речи не найдена")
    
    try:
        from vosk import Model, KaldiRecognizer
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
    """Распознавание речи из файла"""
    
    # Сначала проверяем режим микросервиса
    if USE_LLM_SVC:
        try:
            print(f"[LLM-SVC] Распознавание речи через WhisperX: {file_path}")
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            # WhisperX даёт значительно лучшее качество распознавания чем Vosk
            result = transcribe_audio_whisperx_llm_svc(audio_data, filename=os.path.basename(file_path), language="ru")
            print(f"[LLM-SVC] Распознанный текст (WhisperX): '{result}'")
            return result
        except Exception as e:
            print(f"[LLM-SVC] Ошибка WhisperX: {e}. Пробуем Vosk...")
            try:
                with open(file_path, 'rb') as f:
                    audio_data = f.read()
                result = transcribe_audio_llm_svc(audio_data, filename=os.path.basename(file_path), language="ru")
                print(f"[LLM-SVC] Распознанный текст (Vosk fallback): '{result}'")
                return result
            except Exception as e2:
                print(f"[LLM-SVC] Ошибка Vosk fallback: {e2}. Пробуем локально.")
    
    # Локальное распознавание
    if not check_vosk_model():
        raise Exception("Модель распознавания речи не найдена")
    
    try:
        import wave
        import numpy as np
        print(f"Обрабатываю файл: {file_path}")
        
        if not os.path.exists(file_path):
            raise Exception(f"Файл не найден: {file_path}")
        
        file_size = os.path.getsize(file_path)
        print(f"Размер файла: {file_size} байт")
        
        if file_size < 10:
            print("Файл слишком мал для содержания аудио")
            return ""
        
        converted_file_path = None
        try:
            # Определение формата по сигнатуре  
            with open(file_path, 'rb') as f:
                header = f.read(12)
            
            is_wav = header.startswith(b'RIFF') and b'WAVE' in header
            is_webm = header.startswith(b'\x1a\x45\xdf\xa3')
            
            if not is_wav:
                print(f"Файл не в формате WAV, конвертирую...")
                try:
                    from pydub import AudioSegment
                    if is_webm:
                        print("Обнаружен WebM формат")
                        audio = AudioSegment.from_file(file_path, format="webm")
                    else:
                        print("Пытаюсь загрузить в автоматическом режиме")
                        audio = AudioSegment.from_file(file_path)
                    
                    # Принудительно в параметры Vosk: 16kHz, mono, 16-bit
                    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)
                    
                    import tempfile
                    temp_dir = tempfile.gettempdir()
                    converted_file_path = os.path.join(temp_dir, f"converted_{os.path.basename(file_path)}.wav")
                    audio.export(converted_file_path, format="wav")
                    file_path = converted_file_path
                    
                except ImportError:
                    print("pydub не установлен, не могу конвертировать")
                    return ""
                except Exception as e:
                    print(f"Ошибка конвертации: {e}")
                    pass
        except Exception as e:
            print(f"Ошибка при определении формата: {e}")

        # Начало чтения аудио-данных
        try:
            with wave.open(file_path, 'rb') as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                
                if nframes == 0:
                    print("Аудиофайл не содержит данных")
                    return ""
                
                frames = wf.readframes(nframes)
                if len(frames) == 0:
                    print("Не удалось прочитать аудиоданные")
                    return ""

                # Конвертация в numpy массив для ресэмплинга и моно  
                if sampwidth == 1: dtype = np.uint8
                elif sampwidth == 2: dtype = np.int16
                elif sampwidth == 4: dtype = np.int32
                else: dtype = np.int16
                
                audio_array = np.frombuffer(frames, dtype=dtype)
                if len(audio_array) == 0:
                    print("Пустой аудио массив")
                    return ""
                
                # Конвертируем в моно если нужно  
                if channels == 2:
                    print("Конвертирую стерео в моно")
                    if len(audio_array) % 2 != 0:
                        audio_array = audio_array[:-1]
                    audio_array = audio_array.reshape(-1, 2)
                    audio_array = np.mean(audio_array, axis=1).astype(dtype)
                    channels = 1
                
                # Конвертируем в 16-бит если нужно  
                if sampwidth != 2:
                    print(f"Конвертирую разрядность с {sampwidth*8} на 16 бит")
                    if sampwidth == 1:
                        audio_array = ((audio_array.astype(np.float32) - 128) * 256).astype(np.int16)
                    elif sampwidth == 4:
                        audio_array = (audio_array // 65536).astype(np.int16)
                    sampwidth = 2
                
                # Ресэмплинг если нужно 
                if framerate != SAMPLE_RATE:
                    print(f"Конвертирую частоту с {framerate} на {SAMPLE_RATE}")
                    if len(audio_array) > 1:
                        ratio = SAMPLE_RATE / framerate
                        new_length = max(1, int(len(audio_array) * ratio))
                        indices = np.linspace(0, len(audio_array) - 1, new_length)
                        audio_array = np.interp(indices, np.arange(len(audio_array)), 
                                               audio_array.astype(np.float32)).astype(np.int16)
                        framerate = SAMPLE_RATE
                
                frames = audio_array.tobytes()
        
        except (wave.Error, EOFError, Exception) as e:
            print(f"Ошибка чтения WAV файла: {e}")
            print("Попытка чтения как raw аудио...")
            
            # Попытка обработать как raw аудио  
            try:
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                if len(raw_data) < 4: return ""
                if raw_data.startswith(b'RIFF'):
                    header_size = 44
                    if len(raw_data) > header_size: raw_data = raw_data[header_size:]
                    else: return ""
                if len(raw_data) % 2 != 0: raw_data = raw_data[:-1]
                frames = raw_data
                framerate = SAMPLE_RATE
                sampwidth = 2
                channels = 1
            except Exception as e2:
                print(f"Ошибка чтения raw аудио: {e2}")
                return ""
        
        # Инициализируем модель распознавания локально  
        from vosk import Model, KaldiRecognizer
        model = Model(VOSK_MODEL_PATH)
        rec = KaldiRecognizer(model, framerate)
        
        print("Начинаю распознавание...")
        results = []
        chunk_size = framerate * sampwidth * channels // 10 # 0.1 секунды
        
        # Цикл распознавания по чанкам  
        for i in range(0, len(frames), chunk_size):
            chunk = frames[i:i + chunk_size]
            if len(chunk) == 0: break
            if rec.AcceptWaveform(chunk):
                part = json.loads(rec.Result())
                if part.get("text", "").strip():
                    results.append(part["text"].strip())
                    print(f"Частичный результат: {part['text']}")
        
        # Финальный результат  
        final_result = json.loads(rec.FinalResult())
        if final_result.get("text", "").strip():
            results.append(final_result["text"].strip())
            print(f"Финальный результат: {final_result['text']}")
        
        full_text = " ".join(results).strip()
        return full_text
        
    except Exception as e:
        print(f"Ошибка при распознавании речи из файла: {e}")
        import traceback
        traceback.print_exc()
        return ""
    finally:
        # Очистка временных файлов  
        if 'converted_file_path' in locals() and converted_file_path and os.path.exists(converted_file_path):
            try:
                os.remove(converted_file_path)
                print(f"Удален временный файл: {converted_file_path}")
            except: pass

def run_voice():
    """Запуск голосового интерфейса в консоли  """
    if not check_vosk_model():
        raise Exception("Модель распознавания речи не найдена")
    
    init_tts()
    
    try:
        print("Голосовой режим запущен. Нажмите Ctrl+C для выхода.")
        while True:
            try:
                phrase = recognize_speech()
                if not phrase: continue
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