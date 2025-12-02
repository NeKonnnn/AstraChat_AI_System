try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None
    print("Предупреждение: llama_cpp недоступен. Используйте llm-svc для работы с моделями.")

from backend.config.config import MODEL_PATH
from backend.context_prompts import context_prompt_manager
import os
import glob
import json

# Класс для хранения настроек модели
class ModelSettings:
    def __init__(self):
        self.settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_settings.json")
        # Настройки модели по умолчанию (оптимизированные)
        self.default_settings = {
            "context_size": 8192,      # Размер контекста (увеличен для лучшей производительности)
            "output_tokens": 1024,     # Размер выходного текста
            "batch_size": 512,         # Размер батча (оптимальный для GPU)
            "n_threads": 12,           # Количество потоков (оптимально для 24-ядерного CPU)
            "use_mmap": True,          # Использовать mmap
            "use_mlock": False,        # Блокировать в памяти
            "verbose": True,           # Подробный вывод (для диагностики)
            "temperature": 0.7,        # Температура генерации
            "top_p": 0.95,             # Top-p sampling
            "repeat_penalty": 1.05,    # Штраф за повторения
            "top_k": 40,               # Top-k sampling
            "min_p": 0.05,             # Min-p sampling
            "frequency_penalty": 0.0,  # Frequency penalty
            "presence_penalty": 0.0,    # Presence penalty
            "use_gpu": True,           # Использовать GPU
            "streaming": True,         # Использовать потоковую генерацию
            "legacy_api": False        # Режим совместимости для несовместимых архитектур
        }
        self.settings = self.default_settings.copy()
        self.load_settings()
    
    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                print("Настройки модели загружены")
        except Exception as e:
            print(f"Ошибка при загрузке настроек модели: {str(e)}")
    
    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            print("Настройки модели сохранены")
        except Exception as e:
            print(f"Ошибка при сохранении настроек модели: {str(e)}")
    
    def get(self, key, default=None):
        """Получение значения настройки"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Установка значения настройки"""
        if key in self.settings:
            self.settings[key] = value
            self.save_settings()
            return True
        return False
    
    def reset_to_defaults(self):
        """Сброс настроек к рекомендуемым значениям по умолчанию"""
        self.settings = self.default_settings.copy()
        self.save_settings()
        print("Настройки сброшены к рекомендуемым значениям")
    
    def get_recommended_settings(self):
        """Получение рекомендуемых настроек (без применения)"""
        return self.default_settings.copy()
    
    def get_max_values(self):
        """Получение максимальных значений для настроек"""
        return {
            "context_size": 32768,     # Максимальный контекст для большинства моделей
            "output_tokens": 100000,   # Максимальный размер ответа (увеличено для снятия ограничения)
            "batch_size": 2048,        # Максимальный размер батча
            "n_threads": 24,           # Максимум потоков (по количеству ядер)
            "temperature": 2.0,        # Максимальная температура
            "top_p": 1.0,              # Максимальный top_p
            "repeat_penalty": 2.0,      # Максимальный штраф за повторения
            "top_k": 200,              # Максимальный top_k
            "min_p": 1.0,              # Максимальный min_p
            "frequency_penalty": 2.0,  # Максимальный frequency_penalty
            "presence_penalty": 2.0    # Максимальный presence_penalty
        }
    
    def get_all(self):
        """Получение всех настроек"""
        return self.settings.copy()

# Создаем экземпляр класса настроек
model_settings = ModelSettings()

# Настройки модели
MODEL_CONTEXT_SIZE = model_settings.get("context_size")
DEFAULT_OUTPUT_TOKENS = model_settings.get("output_tokens")
VERBOSE_OUTPUT = model_settings.get("verbose")

# Поиск доступных моделей
def find_available_model():
    models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    if not os.path.exists(models_dir):
        print(f"Директория с моделями не существует: {models_dir}")
        return None
    
    # Ищем модели с расширением .gguf
    model_files = glob.glob(os.path.join(models_dir, '*.gguf'))
    if model_files:
        print(f"Найдена модель: {model_files[0]}")
        return model_files[0]
    
    print("Модели в формате GGUF не найдены в директории models/")
    return None

# Инициализация модели с проверкой существования файла
llm = None

def initialize_model():
    """Инициализация модели с текущими настройками"""
    global llm
    
    # Проверяем доступность llama_cpp
    if not LLAMA_CPP_AVAILABLE:
        print("ПРЕДУПРЕЖДЕНИЕ: llama_cpp недоступен. Используйте llm-svc для работы с моделями.")
        return False
    
    # Освобождаем ресурсы, если модель уже была загружена
    if llm is not None:
        try:
            # Сохраняем ссылку, чтобы очистить её позже
            old_llm = llm
            # Сбрасываем глобальную переменную перед удалением
            llm = None
            # Явно удаляем объект
            del old_llm
            
            # Вызываем сборщик мусора несколько раз
            import gc
            gc.collect()
            # Ждем некоторое время перед продолжением
            import time
            time.sleep(1)
            # Повторяем еще раз для уверенности
            gc.collect()
            
            print("Предыдущая модель успешно выгружена из памяти")
        except Exception as e:
            print(f"Ошибка при освобождении ресурсов: {str(e)}")
            # Продолжаем, даже если не удалось освободить ресурсы
        
    try:
        model_to_use = MODEL_PATH
        if not os.path.exists(model_to_use):
            print(f"ПРЕДУПРЕЖДЕНИЕ: Модель по указанному пути не найдена: {model_to_use}")
            model_to_use = find_available_model()
        
        if model_to_use and os.path.exists(model_to_use):
            use_gpu = model_settings.get("use_gpu", False)
            device_type = "GPU" if use_gpu else "CPU"
            print(f"Загружаю модель из: {model_to_use} (устройство: {device_type})")
            
            # Проверяем файл модели на наличие архитектуры
            # Это помогает определить, нужно ли использовать legacy_api
            legacy_mode = False
            try:
                # Импортируем функцию для чтения метаданных модели
                from llama_cpp.llama_grammar import LlamaGrammar
                import json
                import struct
                
                # Проверяем, является ли файл GGUF форматом
                with open(model_to_use, "rb") as f:
                    magic = f.read(4)
                    if magic == b"GGUF":
                        # Файл в формате GGUF, читаем метаданные для определения архитектуры
                        f.seek(0)
                        # Пропускаем magic + version + metadata_kv_count
                        f.read(4 + 4 + 8)
                        try:
                            # Пытаемся прочитать ключи метаданных
                            architecture_found = False
                            for _ in range(100):  # Ограничиваем количество итераций для безопасности
                                # Чтение длины ключа
                                key_length_bytes = f.read(8)
                                if not key_length_bytes:
                                    break
                                key_length = int.from_bytes(key_length_bytes, byteorder='little')
                                
                                # Чтение ключа
                                key = f.read(key_length).decode('utf-8')
                                
                                # Чтение типа значения
                                value_type = int.from_bytes(f.read(4), byteorder='little')
                                
                                if key == "general.architecture":
                                    # Чтение длины значения (для строк)
                                    if value_type == 3:  # STRING
                                        value_length = int.from_bytes(f.read(8), byteorder='little')
                                        value = f.read(value_length).decode('utf-8')
                                        print(f"Обнаружена архитектура: {value}")
                                        
                                        # Проверяем, поддерживается ли архитектура
                                        unsupported_archs = ["qwen", "qwen2", "qwen3", "phi", "yi", "mamba"]
                                        if any(arch in value.lower() for arch in unsupported_archs):
                                            print(f"Архитектура {value} может быть несовместима с llama-cpp напрямую, "
                                                  f"будет использован режим совместимости")
                                            legacy_mode = True
                                        architecture_found = True
                                        break
                                    else:
                                        # Пропускаем значение
                                        f.seek(f.tell() + 8)  # Пропускаем размер значения
                                else:
                                    # Пропускаем значение
                                    f.seek(f.tell() + 12)  # Пропускаем тип, размер и значение
                            
                            if not architecture_found:
                                print("Архитектура не найдена в метаданных, будет использован обычный режим")
                        except Exception as e:
                            print(f"Ошибка при чтении метаданных модели: {str(e)}")
            except Exception as e:
                print(f"Не удалось проверить архитектуру модели: {str(e)}")
            
            try:
                # Перед созданием новой модели вызываем сборщик мусора
                import gc
                gc.collect()
                
                # Параметры для модели с текущими настройками
                # Если модель несовместима, используем legacy_api=True
                use_legacy_api = model_settings.get("legacy_api", False) or legacy_mode
                if use_legacy_api:
                    print(f"Используется режим совместимости (legacy_api=True) для загрузки модели")
                
                # Дополнительные параметры для оптимизации производительности
                # Принудительно используем GPU слои если CUDA доступна
                import torch
                n_gpu_layers = -1 if (use_gpu and torch.cuda.is_available()) else 0  # Использовать все слои на GPU
                
                llm = Llama(
                    model_path=model_to_use,
                    n_ctx=model_settings.get("context_size"),
                    n_batch=model_settings.get("batch_size"),
                    n_gpu_layers=n_gpu_layers,       # Количество слоев на GPU
                    use_mmap=model_settings.get("use_mmap"),
                    use_mlock=model_settings.get("use_mlock"),
                    verbose=model_settings.get("verbose"),
                    seed=42,                          # Фиксированное зерно для стабильности
                    n_threads=model_settings.get("n_threads"),
                    use_gpu=use_gpu,
                    legacy_api=use_legacy_api         # Режим совместимости для несовместимых архитектур
                )
                print(f"Модель успешно загружена на {device_type} с контекстным окном {model_settings.get('context_size')} токенов!")
                return True
            except Exception as e:
                print(f"ОШИБКА: Не удалось загрузить модель: {str(e)}")
                
                # Если ошибка связана с архитектурой и мы не используем режим совместимости,
                # попробуем еще раз с включенным режимом
                if not use_legacy_api and "unknown model architecture" in str(e):
                    print("Обнаружена несовместимая архитектура. Повторная попытка с режимом совместимости...")
                    try:
                        # Обновляем n_gpu_layers для повторной попытки
                        n_gpu_layers = -1 if (use_gpu and torch.cuda.is_available()) else 0
                        
                        llm = Llama(
                            model_path=model_to_use,
                            n_ctx=model_settings.get("context_size"),
                            n_batch=model_settings.get("batch_size"),
                            n_gpu_layers=n_gpu_layers,  # Количество слоев на GPU
                            use_mmap=model_settings.get("use_mmap"),
                            use_mlock=model_settings.get("use_mlock"),
                            verbose=model_settings.get("verbose"),
                            seed=42,
                            n_threads=model_settings.get("n_threads"),
                            use_gpu=use_gpu,
                            legacy_api=True    # Принудительно включаем режим совместимости
                        )
                        print(f"Модель успешно загружена в режиме совместимости на {device_type}!")
                        return True
                    except Exception as e2:
                        print(f"ОШИБКА при повторной попытке с режимом совместимости: {str(e2)}")
                
                # Сбрасываем глобальную переменную, если произошла ошибка во время загрузки
                llm = None
                # Принудительно вызываем сборщик мусора
                gc.collect()
                raise
        else:
            print("ОШИБКА: Не удалось найти подходящую модель.")
            raise ValueError("Модель не найдена")
    except Exception as e:
        print(f"ОШИБКА при загрузке модели: {str(e)}")
        raise

if LLAMA_CPP_AVAILABLE:
    try:
        initialize_model()
    except Exception as e:
        print(f"ОШИБКА при инициализации модели: {str(e)}")
else:
    print("llama_cpp недоступен, пропуск инициализации локальной модели")

def update_model_settings(new_settings):
    """Обновление настроек модели и перезагрузка"""
    global model_settings, MODEL_CONTEXT_SIZE, DEFAULT_OUTPUT_TOKENS, VERBOSE_OUTPUT
    
    # Обновляем настройки
    for key, value in new_settings.items():
        model_settings.set(key, value)
    
    # Обновляем глобальные переменные
    MODEL_CONTEXT_SIZE = model_settings.get("context_size")
    DEFAULT_OUTPUT_TOKENS = model_settings.get("output_tokens")
    VERBOSE_OUTPUT = model_settings.get("verbose")
    
    # Перезагружаем модель с новыми настройками
    return initialize_model()

def reload_model_by_path(model_path):
    """Перезагрузка модели с новым файлом модели"""
    global MODEL_PATH, llm
    
    # Проверяем доступность llama_cpp
    if not LLAMA_CPP_AVAILABLE:
        print("ПРЕДУПРЕЖДЕНИЕ: llama_cpp недоступен. Используйте llm-svc для работы с моделями.")
        return False
    
    # Проверяем существование файла модели
    if not os.path.exists(model_path):
        print(f"ОШИБКА: Модель по указанному пути не найдена: {model_path}")
        return False
    
    # Если текущая модель та же самая, возвращаем успех без перезагрузки
    if MODEL_PATH == model_path and llm is not None:
        print(f"Модель {model_path} уже загружена, перезагрузка не требуется")
        return True
    
    try:
        # Принудительный сброс всех ссылок на модель перед сменой
        if llm is not None:
            try:
                # Сохраняем ссылку, чтобы очистить её позже
                old_llm = llm
                # Сбрасываем глобальную переменную перед удалением
                llm = None
                # Явно удаляем объект
                del old_llm
                
                # Запускаем сборщик мусора несколько раз
                import gc
                gc.collect()
                # Ждем некоторое время перед продолжением
                import time
                time.sleep(1)
                # Повторяем еще раз для уверенности
                gc.collect()
                
                print("Предыдущая модель успешно выгружена из памяти")
            except Exception as e:
                print(f"Ошибка при освобождении ресурсов: {str(e)}")
        
        # Делаем более длительную паузу перед загрузкой новой модели
        import time
        time.sleep(2)
        
        # Обновляем глобальный путь к модели
        MODEL_PATH = model_path
        print(f"Сменяем модель на: {model_path}")
        
        # Перезагружаем модель
        return initialize_model()
    except Exception as e:
        print(f"ОШИБКА при смене модели: {str(e)}")
        return False

def get_model_info():
    """Получение информации о текущей модели"""
    if llm is None:
        return {
            "loaded": False,
            "metadata": None,
            "path": MODEL_PATH
        }
    
    try:
        # Создаем базовую структуру метаданных
        metadata = {
            "general.name": "Неизвестно",
            "general.architecture": "Неизвестно",
            "general.size_label": "Неизвестно"
        }
        
        # Пытаемся получить информацию через метод model_metadata
        try:
            if hasattr(llm, 'model_metadata'):
                model_meta = llm.model_metadata()
                metadata.update(model_meta)
        except Exception as e:
            print(f"Предупреждение: Не удалось получить метаданные модели: {e}")
        
        # Информация о контексте
        n_ctx = 4096  # значение по умолчанию
        try:
            if hasattr(llm, 'n_ctx'):
                if callable(llm.n_ctx):
                    n_ctx = llm.n_ctx()
                else:
                    n_ctx = llm.n_ctx
        except Exception as e:
            print(f"Предупреждение: Не удалось получить размер контекста: {e}")
        
        # Слои GPU
        n_gpu_layers = 0
        try:
            if hasattr(llm, 'params') and hasattr(llm.params, 'n_gpu_layers'):
                n_gpu_layers = llm.params.n_gpu_layers
        except Exception as e:
            print(f"Предупреждение: Не удалось получить количество GPU слоев: {e}")
        
        # Получаем тип модели и имя файла для более информативного отображения
        model_filename = os.path.basename(MODEL_PATH)
        if "general.architecture" not in metadata or metadata["general.architecture"] == "Неизвестно":
            # Пытаемся определить архитектуру по имени файла
            if "llama" in model_filename.lower():
                metadata["general.architecture"] = "LLaMA"
            elif "mistral" in model_filename.lower():
                metadata["general.architecture"] = "Mistral"
            elif "qwen" in model_filename.lower():
                metadata["general.architecture"] = "Qwen"
            elif "phi" in model_filename.lower():
                metadata["general.architecture"] = "Phi"
            elif "gemma" in model_filename.lower():
                metadata["general.architecture"] = "Gemma"
        
        # Возвращаем собранную информацию
        return {
            "loaded": True,
            "metadata": metadata,
            "path": MODEL_PATH,
            "n_ctx": n_ctx,
            "n_gpu_layers": n_gpu_layers
        }
    except Exception as e:
        print(f"Ошибка при получении информации о модели: {e}")
        return {
            "loaded": True,
            "error": str(e),
            "path": MODEL_PATH,
            "metadata": {
                "general.name": os.path.basename(MODEL_PATH),
                "general.architecture": "Неизвестно"
            }
        }

def prepare_prompt(text, system_prompt=None, history=None, model_path=None, custom_prompt_id=None):
    """Подготовка промпта в правильном формате с поддержкой истории диалога и контекстных промптов"""
    if system_prompt is None:
        # Используем контекстный промпт для модели, если доступен
        if model_path:
            system_prompt = context_prompt_manager.get_effective_prompt(model_path, custom_prompt_id)
        else:
            system_prompt = context_prompt_manager.get_global_prompt()
    
    # Базовый шаблон для чата
    prompt_parts = []
    
    # Добавляем системный промпт только если он не пустой
    if system_prompt and system_prompt.strip():
        prompt_parts.append(f"<|im_start|>system\n{system_prompt}\n<|im_end|>")
    
    # Добавляем историю диалога, если она есть
    if history:
        for entry in history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role == "user":
                prompt_parts.append(f"<|im_start|>user\n{content}\n<|im_end|>")
            elif role == "assistant":
                prompt_parts.append(f"<|im_start|>assistant\n{content}\n<|im_end|>")
    
    # Добавляем текущий запрос пользователя
    prompt_parts.append(f"<|im_start|>user\n{text.strip()}\n<|im_end|>")
    prompt_parts.append("<|im_start|>assistant\n")
    
    return "".join(prompt_parts)

def ask_agent(prompt, history=None, max_tokens=None, streaming=False, stream_callback=None, model_path=None, custom_prompt_id=None, images=None):
    if not LLAMA_CPP_AVAILABLE:
        raise ValueError("llama_cpp недоступен. Используйте llm-svc для работы с моделями.")
    
    # Параметр images игнорируется в этой реализации (для совместимости с agent_llm_svc)
    if images:
        print(f"ВНИМАНИЕ: Параметр images не поддерживается в agent.py, используйте agent_llm_svc.py для работы с изображениями")
    
    if llm is None:
        raise ValueError("Модель не загружена. Пожалуйста, убедитесь, что модель инициализирована.")
    
    # Если не указано количество токенов, берем из настроек
    if max_tokens is None:
        max_tokens = model_settings.get("output_tokens")
    
    # Формируем вход (можно добавить историю позже)
    try:
        # Используем правильный формат запроса с контекстными промптами
        full_prompt = prepare_prompt(prompt, history=history, model_path=model_path, custom_prompt_id=custom_prompt_id)
        
        # Если включен режим потоковой генерации
        if streaming and stream_callback:
            print("ask_agent: начинаем потоковую генерацию...")
            # Инициализируем переменную для накопления текста
            accumulated_text = ""
            
            # Создаем генератор для потоковой обработки
            generator = llm(
                full_prompt,
                max_tokens=max_tokens,
                stop=["<|im_end|>", "<|im_start|>"],
                echo=False,
                temperature=model_settings.get("temperature"),
                top_p=model_settings.get("top_p"),
                repeat_penalty=model_settings.get("repeat_penalty"),
                top_k=model_settings.get("top_k", 40),
                stream=True  # Включаем потоковую генерацию
            )
            
            print("ask_agent: генератор создан, начинаем обработку чанков...")
            
            # Обрабатываем каждый фрагмент
            chunk_counter = 0
            for output in generator:
                chunk = output["choices"][0]["text"]
                accumulated_text += chunk
                chunk_counter += 1
                
                print(f"ask_agent: получен чанк #{chunk_counter}, длина: {len(chunk)} символов")
                
                # Вызываем колбэк с текущим фрагментом
                print(f"ask_agent: вызываем stream_callback для чанка #{chunk_counter}")
                result = stream_callback(chunk, accumulated_text)
                
                # Если колбэк вернул False, останавливаем генерацию
                if result is False:
                    print("ask_agent: получен сигнал остановки от stream_callback, прерываем генерацию")
                    return None  # Возвращаем None вместо накопленного текста
            
            return accumulated_text
        else:
            # Обычная генерация без стриминга
            output = llm(
                full_prompt,
                max_tokens=max_tokens,     # Размер ответа
                stop=["<|im_end|>", "<|im_start|>"],  # Стоп-токены для формата чата
                echo=False,                # Не возвращать входной текст
                temperature=model_settings.get("temperature"),
                top_p=model_settings.get("top_p"),
                repeat_penalty=model_settings.get("repeat_penalty"),
                top_k=model_settings.get("top_k", 40)
            )
            
            generated_text = output["choices"][0]["text"].strip()
            

            
            # Обрабатываем случай пустого вывода
            if not generated_text:

                # Более безопасные параметры для повторной попытки
                output = llm(
                    prompt.strip(),  # Более простой формат
                    max_tokens=256,  # Уменьшенное число токенов
                    temperature=0.5, # Более низкая температура
                    echo=False
                )
                generated_text = output["choices"][0]["text"].strip()
                

            
            return generated_text
    except Exception as e:

        # Вместо непосредственной передачи ошибки, возвращаем сообщение об ошибке
        return f"Извините, произошла ошибка при генерации ответа: {str(e)}. Попробуйте задать вопрос иначе или позже."