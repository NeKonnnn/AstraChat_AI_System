"""
MemoAI Agent с поддержкой llm-svc
Модифицированная версия agent.py для работы через llm-svc API
"""

# Настройка кодировки для Windows
import sys
import os

# Импортируем утилиту для исправления кодировки
try:
    from utils.encoding_fix import fix_windows_encoding, safe_print
    fix_windows_encoding()
except ImportError:
    # Если утилита недоступна, используем базовую настройку
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')

import json
import logging
from typing import List, Dict, Any, Optional, Callable
from backend.config.config import MODEL_PATH
from backend.context_prompts import context_prompt_manager
from backend.llm_client import ask_agent_llm_svc, get_llm_service

# Настройка логирования с поддержкой UTF-8
logger = logging.getLogger(__name__)

# Настройка кодировки для обработчиков логирования
for handler in logging.root.handlers:
    if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
        handler.stream.reconfigure(encoding='utf-8')

# Класс для хранения настроек модели (совместимость)
class ModelSettings:
    def __init__(self):
        self.settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_settings.json")
        # Настройки модели по умолчанию
        self.default_settings = {
            "context_size": 8192,
            "output_tokens": 1024,
            "batch_size": 512,
            "n_threads": 12,
            "use_mmap": True,
            "use_mlock": False,
            "verbose": True,
            "temperature": 0.7,
            "top_p": 0.95,
            "repeat_penalty": 1.05,
            "use_gpu": True,
            "streaming": True,
            "legacy_api": False
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
            "context_size": 32768,
            "output_tokens": 100000,  # Увеличено для снятия ограничения на длину генерации
            "batch_size": 2048,
            "n_threads": 24,
            "temperature": 2.0,
            "top_p": 1.0,
            "repeat_penalty": 2.0
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

# Флаг использования llm-svc
USE_LLM_SVC = True  # Переключатель между прямой работой с llama-cpp и llm-svc

def initialize_model():
    """Инициализация модели (теперь через llm-svc)"""
    if USE_LLM_SVC:
        logger.info("Инициализация через llm-svc...")
        try:
            import asyncio
            # Инициализируем llm-svc сервис
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаем новый в отдельном потоке
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_llm_service())
                    service = future.result()
            else:
                service = loop.run_until_complete(get_llm_service())
            
            logger.info("llm-svc сервис инициализирован успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации llm-svc: {e}")
            return False
    else:
        # Fallback к оригинальной инициализации
        logger.info("Используется оригинальная инициализация модели")
        return True

def update_model_settings(new_settings):
    """Обновление настроек модели"""
    global model_settings, MODEL_CONTEXT_SIZE, DEFAULT_OUTPUT_TOKENS, VERBOSE_OUTPUT
    
    # Обновляем настройки
    for key, value in new_settings.items():
        model_settings.set(key, value)
    
    # Обновляем глобальные переменные
    MODEL_CONTEXT_SIZE = model_settings.get("context_size")
    DEFAULT_OUTPUT_TOKENS = model_settings.get("output_tokens")
    VERBOSE_OUTPUT = model_settings.get("verbose")
    
    logger.info("Настройки модели обновлены")
    return True

def reload_model_by_path(model_path):
    """Перезагрузка модели с новым файлом модели (через llm-svc)"""
    if USE_LLM_SVC:
        logger.info(f"Перезагрузка модели через llm-svc: {model_path}")
        # В llm-svc перезагрузка модели происходит через конфигурацию
        # Здесь мы можем обновить настройки или перезапустить сервис
        logger.info("Для смены модели в llm-svc обновите конфигурацию и перезапустите сервис")
        return True
    else:
        # Fallback к оригинальной логике
        logger.info("Используется оригинальная перезагрузка модели")
        return True

def get_model_info():
    """Получение информации о текущей модели (через llm-svc)"""
    if USE_LLM_SVC:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, get_llm_service())
                    service = future.result()
            else:
                service = loop.run_until_complete(get_llm_service())
            
            # Получаем информацию о модели через llm-svc
            health = service.client.health_check()
            if health.get("status") == "healthy":
                return {
                    "loaded": True,
                    "metadata": {
                        "general.name": service.model_name,
                        "general.architecture": "LLM-SVC",
                        "general.size_label": "Unknown"
                    },
                    "path": "llm-svc",
                    "n_ctx": MODEL_CONTEXT_SIZE,
                    "n_gpu_layers": 0
                }
            else:
                return {
                    "loaded": False,
                    "error": "llm-svc недоступен",
                    "path": "llm-svc"
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации о модели: {e}")
            return {
                "loaded": False,
                "error": str(e),
                "path": "llm-svc"
            }
    else:
        # Fallback к оригинальной логике
        return {
            "loaded": True,
            "metadata": {"general.name": "Local Model"},
            "path": MODEL_PATH
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
    """Основная функция для работы с AI агентом через llm-svc"""
    
    if USE_LLM_SVC:
        # Используем llm-svc
        logger.info("Используется llm-svc для генерации ответа")
        
        # Если не указано количество токенов, берем из настроек
        if max_tokens is None:
            max_tokens = model_settings.get("output_tokens")
        
        try:
            # Используем llm_client для генерации
            response = ask_agent_llm_svc(
                prompt=prompt,
                history=history,
                max_tokens=max_tokens,
                streaming=streaming,
                stream_callback=stream_callback,
                model_path=model_path,
                custom_prompt_id=custom_prompt_id,
                images=images
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка генерации через llm-svc: {e}")
            return f"Извините, произошла ошибка при генерации ответа: {str(e)}"
    
    else:
        # Fallback к оригинальной логике (если llm-svc недоступен)
        logger.warning("llm-svc недоступен, используется fallback режим")
        return "llm-svc недоступен. Пожалуйста, запустите llm-svc сервис."

# Инициализация НЕ происходит автоматически при импорте модуля!
# Это позволяет избежать двойной загрузки модели.
# Инициализация будет выполнена явно из main.py при первом использовании.
logger.info("Модуль agent_llm_svc импортирован (инициализация отложена)")
