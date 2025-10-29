import os
import sys
import json
import time
import queue
import threading
import tempfile
import numpy as np
import sounddevice as sd
from datetime import datetime

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
    print("Используется llm-svc для онлайн транскрипции")

# Импортируем наш класс для записи системного звука
from .system_audio import SystemAudioRecorder
# Новый импорт для использования улучшенной реализации записи системного звука
from .system_audio_capture import WasapiLoopbackCapture

class OnlineTranscriber:
    def __init__(self):
        self.model = None
        self.mic_recognizer = None
        self.system_recognizer = None
        self.temp_dir = tempfile.mkdtemp()
        self.language = "ru"  # По умолчанию русский
        self.vosk_model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model_small")  # Путь к модели Vosk
        self.sample_rate = 16000
        
        # Очереди для аудиоданных
        self.mic_queue = queue.Queue()
        self.system_queue = queue.Queue()
        
        # Флаги для управления потоками
        self.is_running = False
        self.capture_mic = True
        self.capture_system = True
        
        # Накопленный текст
        self.transcript = []
        
        # Результаты распознавания
        self.results_callback = None
        
        # Для улучшенной записи системного звука
        self.system_audio_recorder = None
        self.wasapi_recorder = None
        self.using_system_recorder = False
        self.system_audio_device = None
        self.mic_audio_device = None
        
    def load_model(self):
        """Загрузка модели Vosk"""
        
        # Если используем llm-svc, модель не загружается локально
        if USE_LLM_SVC:
            print("[LLM-SVC] Используется llm-svc, локальная модель Vosk не загружается")
            print("[LLM-SVC] Онлайн транскрипция через llm-svc пока не поддерживается")
            return False
        
        # Проверяем доступность Vosk
        if not VOSK_AVAILABLE:
            print("Vosk недоступен. Установите USE_LLM_SVC=true для использования llm-svc")
            return False
        
        try:
            if not os.path.exists(self.vosk_model_path):
                raise ValueError(f"Путь к модели Vosk не существует: {self.vosk_model_path}")
                
            print(f"Загрузка модели Vosk из {self.vosk_model_path}...")
            self.model = Model(self.vosk_model_path)
            
            # Создаем распознаватели
            self.mic_recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.system_recognizer = KaldiRecognizer(self.model, self.sample_rate)
            
            print("Модель Vosk успешно загружена")
            return True
        except Exception as e:
            print(f"Ошибка при загрузке модели Vosk: {str(e)}")
            return False
    
    def mic_callback(self, indata, frames, time, status):
        """Callback для захвата аудио с микрофона"""
        if status:
            print(f"Статус микрофона: {status}")
        if self.capture_mic:
            self.mic_queue.put(bytes(indata))
    
    def system_callback(self, indata, frames, time, status):
        """Callback для захвата системного аудио"""
        if status:
            print(f"Статус системного аудио: {status}")
        if self.capture_system:
            self.system_queue.put(bytes(indata))
    
    def process_mic_audio(self):
        """Обработка аудио с микрофона"""
        print("Начало обработки аудио с микрофона")
        
        while self.is_running:
            try:
                data = self.mic_queue.get(timeout=1)
                if self.mic_recognizer.AcceptWaveform(data):
                    result = json.loads(self.mic_recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        speaker = "Вы"
                        entry = {"time": timestamp, "speaker": speaker, "text": text}
                        self.transcript.append(entry)
                        
                        if self.results_callback:
                            self.results_callback(entry)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Ошибка при обработке аудио с микрофона: {str(e)}")
    
    def process_system_audio(self):
        """Обработка системного аудио"""
        print("Начало обработки системного аудио")
        
        while self.is_running:
            try:
                data = self.system_queue.get(timeout=1)
                if self.system_recognizer.AcceptWaveform(data):
                    result = json.loads(self.system_recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        speaker = "Собеседник"
                        entry = {"time": timestamp, "speaker": speaker, "text": text}
                        self.transcript.append(entry)
                        
                        if self.results_callback:
                            self.results_callback(entry)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Ошибка при обработке системного аудио: {str(e)}")
                
    def process_meeting_recording(self):
        """Периодически останавливает и обрабатывает запись встречи"""
        segment_duration = 10  # Длительность каждого сегмента в секундах
        
        while self.is_running:
            try:
                # Ждем некоторое время для накопления аудио
                time.sleep(segment_duration)
                
                if not self.is_running:
                    break
                
                # Останавливаем запись и получаем файл
                if self.using_system_recorder:
                    audio_file = self.system_audio_recorder.stop_recording()
                else:
                    audio_file = self.wasapi_recorder.stop_recording()
                
                if audio_file:
                    # Транскрибируем временный файл
                    print(f"Транскрибация сегмента: {audio_file}")
                    
                    # Создаем временный распознаватель для этого файла
                    segment_recognizer = KaldiRecognizer(self.model, self.sample_rate)
                    
                    # Открываем и обрабатываем аудиофайл
                    with open(audio_file, "rb") as wf:
                        wf.read(44)  # Пропускаем WAV-заголовок
                        
                        # Обрабатываем файл блоками
                        while True:
                            data = wf.read(4000)
                            if len(data) == 0:
                                break
                                
                            if segment_recognizer.AcceptWaveform(data):
                                result = json.loads(segment_recognizer.Result())
                                text = result.get("text", "").strip()
                                
                                if text:
                                    timestamp = datetime.now().strftime("%H:%M:%S")
                                    entry = {"time": timestamp, "speaker": "Разговор", "text": text}
                                    self.transcript.append(entry)
                                    
                                    if self.results_callback:
                                        self.results_callback(entry)
                    
                    # Обрабатываем последний фрагмент
                    result = json.loads(segment_recognizer.FinalResult())
                    text = result.get("text", "").strip()
                    
                    if text:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        entry = {"time": timestamp, "speaker": "Разговор", "text": text}
                        self.transcript.append(entry)
                        
                        if self.results_callback:
                            self.results_callback(entry)
                
                # Перезапускаем запись для следующего сегмента, если транскрибация еще идет
                if self.is_running:
                    if self.using_system_recorder:
                        self.system_audio_recorder.start_recording(
                            system_device_index=self.system_audio_device,
                            mic_device_index=self.mic_audio_device
                        )
                    else:
                        self.wasapi_recorder.start_recording(self.system_audio_device)
                    
            except Exception as e:
                print(f"Ошибка при обработке записи встречи: {str(e)}")
    
    def start_transcription(self, results_callback=None, capture_mic=True, capture_system=True, mic_device=None, system_device=None, use_wasapi=False):
        """
        Запуск одновременной транскрибации с микрофона и системного аудио
        
        Args:
            results_callback: Функция обратного вызова для получения результатов
            capture_mic: Захватывать аудио с микрофона
            capture_system: Захватывать системное аудио
            mic_device: Индекс устройства микрофона
            system_device: Индекс устройства для системного звука 
            use_wasapi: Использовать WASAPI Loopback вместо Stereo Mix
        """
        if self.is_running:
            print("Транскрибация уже запущена")
            return False
            
        if not self.model:
            if not self.load_model():
                return False
                
        self.capture_mic = capture_mic
        self.capture_system = capture_system
        self.results_callback = results_callback
        self.system_audio_device = system_device
        self.mic_audio_device = mic_device
        
        if capture_mic and not capture_system:
            # Только микрофон
            try:
                self.is_running = True
                
                # Запускаем поток чтения с микрофона
                self.mic_stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    blocksize=8000,
                    dtype="int16",
                    channels=1,
                    callback=self.mic_callback,
                    device=mic_device
                )
                
                self.mic_stream.start()
                
                # Запускаем поток обработки аудио с микрофона
                self.mic_thread = threading.Thread(target=self.process_mic_audio)
                self.mic_thread.daemon = True
                self.mic_thread.start()
                
                print(f"Транскрибация начата (только микрофон)")
                
                # Уведомляем о начале через callback
                if self.results_callback:
                    start_entry = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "speaker": "Система",
                        "text": "Запись совещания началась. Говорите в микрофон."
                    }
                    self.results_callback(start_entry)
                    
                return True
                
            except Exception as e:
                print(f"Ошибка при запуске транскрибации с микрофона: {str(e)}")
                self.is_running = False
                return False
                
        elif capture_system:
            # Системный звук + опционально микрофон
            try:
                self.is_running = True
                
                # Используем WASAPI Loopback или Stereo Mix
                if use_wasapi:
                    self.using_system_recorder = False
                    self.wasapi_recorder = WasapiLoopbackCapture()
                    self.wasapi_recorder.start_recording(system_device)
                    print(f"Используется улучшенная запись системного звука через WASAPI Loopback")
                else:
                    # Используем SystemAudioRecorder для записи системного звука
                    self.using_system_recorder = True
                    self.system_audio_recorder = SystemAudioRecorder()
                    self.system_audio_recorder.start_recording(
                        system_device_index=system_device,
                        mic_device_index=mic_device if capture_mic else None
                    )
                    print(f"Используется запись системного звука {'и микрофона' if capture_mic else ''}")
                
                # Запускаем поток для периодической обработки записей
                self.meeting_thread = threading.Thread(target=self.process_meeting_recording)
                self.meeting_thread.daemon = True
                self.meeting_thread.start()
                
                if capture_mic and not self.using_system_recorder:
                    # Запускаем отдельный микрофонный поток для WASAPI режима
                    self.mic_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        blocksize=8000,
                        dtype="int16",
                        channels=1,
                        callback=self.mic_callback,
                        device=mic_device
                    )
                    
                    self.mic_stream.start()
                    
                    # Запускаем поток обработки аудио с микрофона
                    self.mic_thread = threading.Thread(target=self.process_mic_audio)
                    self.mic_thread.daemon = True
                    self.mic_thread.start()
                
                print(f"Транскрибация начата (системный звук {'+ микрофон' if capture_mic else ''})")
                
                # Уведомляем о начале через callback
                if self.results_callback:
                    msg = "Используется улучшенная запись системного звука" if use_wasapi else "Используется стандартная запись системного звука"
                    start_entry = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "speaker": "Система",
                        "text": f"Запись совещания началась. {msg}. Голоса участников будут распознаны."
                    }
                    self.results_callback(start_entry)
                
                return True
                
            except Exception as e:
                print(f"Ошибка при запуске транскрибации системного звука: {str(e)}")
                self.is_running = False
                return False
        
        return False
    
    def stop_transcription(self):
        """Остановка транскрибации"""
        if not self.is_running:
            print("Транскрибация не была запущена")
            return False
            
        try:
            self.is_running = False
            
            if hasattr(self, 'mic_stream') and self.mic_stream:
                self.mic_stream.stop()
                self.mic_stream.close()
            
            if hasattr(self, 'system_stream') and self.system_stream:
                self.system_stream.stop()
                self.system_stream.close()
            
            if self.using_system_recorder and self.system_audio_recorder:
                self.system_audio_recorder.stop_recording()
            
            if self.wasapi_recorder:
                self.wasapi_recorder.stop_recording()
                
            # Ждем завершения потоков
            if hasattr(self, 'mic_thread') and self.mic_thread and self.mic_thread.is_alive():
                self.mic_thread.join(timeout=2)
                
            if hasattr(self, 'system_thread') and self.system_thread and self.system_thread.is_alive():
                self.system_thread.join(timeout=2)
                
            if hasattr(self, 'meeting_thread') and self.meeting_thread and self.meeting_thread.is_alive():
                self.meeting_thread.join(timeout=2)
                
            # Уведомляем о завершении через callback
            if self.results_callback:
                fragments_count = len(self.transcript)
                end_entry = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "speaker": "Система",
                    "text": f"Запись совещания завершена. Всего записано {fragments_count} фрагментов."
                }
                self.results_callback(end_entry)
                
            print("Транскрибация остановлена")
            return True
            
        except Exception as e:
            print(f"Ошибка при остановке транскрибации: {str(e)}")
            return False
    
    def get_transcript(self):
        """Получить накопленную транскрибацию"""
        return self.transcript
    
    def save_transcript(self, file_path=None):
        """Сохранить транскрибацию в файл"""
        if not self.transcript:
            print("Нет данных для сохранения")
            return None
            
        if not file_path:
            file_path = os.path.join(self.temp_dir, f"transcript_{int(time.time())}.txt")
            
        with open(file_path, "w", encoding="utf-8") as f:
            for entry in self.transcript:
                f.write(f"[{entry['time']}] {entry['speaker']}: {entry['text']}\n")
                
        print(f"Транскрибация сохранена в {file_path}")
        return file_path
    
    @staticmethod
    def get_system_audio_devices():
        """Получить список устройств для захвата системного звука"""
        try:
            # Создаем временный экземпляр для получения списка устройств
            recorder = SystemAudioRecorder()
            devices = recorder.list_audio_devices()
            
            # Ищем устройства для записи системного звука
            system_devices = []
            
            # Проверяем, есть ли Stereo Mix среди устройств
            if devices.get('system_device'):
                system_devices.append({
                    'index': devices['system_device']['index'],
                    'name': devices['system_device']['name'],
                    'is_default': True
                })
            
            # Ищем другие потенциальные устройства
            for device in devices.get('all_devices', []):
                if 'input' in device.get('type', []) and device.get('index') not in [d['index'] for d in system_devices]:
                    lower_name = device.get('name', '').lower()
                    # Ищем потенциальные устройства для системного звука
                    if any(keyword in lower_name for keyword in ['stereo mix', 'mixer', 'mix', 'микшер']):
                        system_devices.append({
                            'index': device['index'],
                            'name': device['name'],
                            'is_default': False
                        })
            
            return system_devices
        except Exception as e:
            print(f"Ошибка при получении устройств системного звука: {str(e)}")
            return []

    @staticmethod
    def get_output_devices():
        """Получить список устройств вывода звука для захвата через WASAPI Loopback"""
        try:
            # Создаем временный экземпляр для получения списка устройств вывода
            wasapi_recorder = WasapiLoopbackCapture()
            devices = wasapi_recorder.list_devices()
            
            # Возвращаем список устройств вывода для WASAPI Loopback
            output_devices = []
            
            for device in devices:
                if device.get('is_loopback', False) or 'output' in device.get('type', []):
                    output_devices.append({
                        'index': device['index'],
                        'name': device['name']
                    })
            
            return output_devices
        except Exception as e:
            print(f"Ошибка при получении устройств вывода звука: {str(e)}")
            return []
    
    @staticmethod
    def get_mic_devices():
        """Получить список устройств микрофона"""
        mic_devices = []
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            
            # Получаем список всех устройств
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                
                # Проверяем, является ли устройство микрофоном
                if dev_info.get('maxInputChannels', 0) > 0:
                    name = dev_info.get('name', f'Микрофон {i}')
                    
                    # Проверяем, не является ли это устройство стерео микшером
                    is_stereo_mix = False
                    lower_name = name.lower()
                    if any(keyword in lower_name for keyword in ['stereo mix', 'mixer', 'mix', 'микшер']):
                        is_stereo_mix = True
                    
                    if not is_stereo_mix:
                        mic_devices.append({
                            'index': i,
                            'name': name,
                        })
            
            p.terminate()
            
        except Exception as e:
            print(f"Ошибка при получении устройств микрофона: {str(e)}")
        
        return mic_devices 