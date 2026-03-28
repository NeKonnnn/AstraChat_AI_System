import os
import sys
import re

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    # ImportError - sounddevice не установлен
    # OSError  - sounddevice установлен, но нет PortAudio (типично в Docker)
    SOUNDDEVICE_AVAILABLE = False
    sd = None
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Проверяем, нужно ли использовать llm-svc  
USE_LLM_SVC = os.getenv('USE_LLM_SVC', 'false').lower() == 'true'

if USE_LLM_SVC:
    logger.info("Используется llm-svc для распознавания речи (WhisperX)")

# Импортируем функции связи с микросервисами
try:
    from backend.llm_client import synthesize_speech_llm_svc, transcribe_audio_whisperx_llm_svc
    from backend.agent_llm_svc import ask_agent
except ImportError:
    from llm_client import synthesize_speech_llm_svc, transcribe_audio_whisperx_llm_svc
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
MIC_RECORD_SECONDS = 6.0
_backend_dir = os.path.dirname(os.path.dirname(__file__))
if os.environ.get("SILERO_MODELS_DIR"):
    SILERO_MODELS_DIR = os.environ["SILERO_MODELS_DIR"]
elif os.path.basename(os.path.normpath(_backend_dir)) == "backend":
    SILERO_MODELS_DIR = os.path.join(os.path.dirname(_backend_dir), "silero_models")
else:
    SILERO_MODELS_DIR = os.path.join(_backend_dir, "models", "silero")
MODELS_URLS = {
    'ru': 'https://models.silero.ai/models/tts/ru/v3_1_ru.pt',
    'en': 'https://models.silero.ai/models/tts/en/v3_en.pt'
}
MODEL_PATHS = {
    'ru': os.path.join(SILERO_MODELS_DIR, 'ru', 'model.pt'),
    'en': os.path.join(SILERO_MODELS_DIR, 'en', 'model.pt'),
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
        if TORCH_AVAILABLE and isinstance(audio, torch.Tensor):
            audio_numpy = audio.cpu().numpy()
        else:
            audio_numpy = audio
        audio_fast = librosa.effects.time_stretch(audio_numpy, rate=speed_factor)
        if TORCH_AVAILABLE and isinstance(audio, torch.Tensor):
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

# ---------- Распознавание речи (WhisperX) ---------- #

def check_stt_available():
    """STT доступен: микросервис WhisperX или локальный WhisperX."""
    if USE_LLM_SVC:
        return True
    try:
        from backend.transcription import whisperx_transcriber as wxt
        return bool(wxt.WHISPERX_AVAILABLE)
    except Exception:
        return False


def recognize_speech():
    """Запись короткого фрагмента с микрофона и распознавание через WhisperX."""
    if not check_stt_available():
        raise Exception("STT недоступен: включите USE_LLM_SVC или установите локальный WhisperX")
    if not SOUNDDEVICE_AVAILABLE:
        raise Exception("Для записи с микрофона нужен пакет sounddevice и PortAudio")
    import tempfile
    import wave
    frames = int(MIC_RECORD_SECONDS * SAMPLE_RATE)
    print(f"Говорите (~{int(MIC_RECORD_SECONDS)} с)...")
    rec = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = tmp.name
    tmp.close()
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(rec.tobytes())
        return recognize_speech_from_file(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def recognize_speech_from_file(file_path):
    """Распознавание речи из файла через WhisperX (сервис или локально)."""
    if USE_LLM_SVC:
        print(f"[LLM-SVC] Распознавание через WhisperX: {file_path}")
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        result = transcribe_audio_whisperx_llm_svc(
            audio_data, filename=os.path.basename(file_path), language="ru"
        )
        print(f"[LLM-SVC] Распознанный текст: '{result}'")
        return result

    if not check_stt_available():
        raise Exception("Локальный WhisperX недоступен. Установите зависимости или USE_LLM_SVC=true")
    try:
        from backend.transcription.whisperx_transcriber import WhisperXTranscriber
        wx = WhisperXTranscriber()
        ok, text = wx.transcribe_audio_file(file_path)
        wx.cleanup()
        return text if ok else ""
    except Exception as e:
        print(f"Ошибка локального WhisperX: {e}")
        import traceback
        traceback.print_exc()
        return ""


def run_voice():
    """Запуск голосового интерфейса в консоли  """
    if not check_stt_available():
        raise Exception("STT недоступен: включите USE_LLM_SVC или установите локальный WhisperX")
    
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