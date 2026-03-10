"""
AstraChat Agent с поддержкой микросервисов
Модифицированная версия для работы через распределенную архитектуру (llm-service)
"""

# Настройка кодировки для Windows  
import sys
import os

try:
    from utils.encoding_fix import fix_windows_encoding, safe_print
    fix_windows_encoding()
except ImportError:
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable

# Импорт путей и настроек
try:
    from backend.config import get_path
    MODEL_PATH = get_path("model_path")
    from backend.context_prompts import context_prompt_manager
    from backend.llm_client import ask_agent_llm_svc, get_llm_service
except ImportError:
    from config import get_path
    MODEL_PATH = get_path("model_path")
    from context_prompts import context_prompt_manager
    from llm_client import ask_agent_llm_svc, get_llm_service

logger = logging.getLogger(__name__)

# Настройка кодировки логов  
for handler in logging.root.handlers:
    if hasattr(handler, 'stream') and hasattr(handler.stream, 'reconfigure'):
        handler.stream.reconfigure(encoding='utf-8')

class ModelSettings:
    """Класс для хранения настроек модели  """
    def __init__(self):
        # Находим файл настроек относительно корня бэкенда
        self.settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_settings.json")
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
            "top_k": 40,
            "min_p": 0.05,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "use_gpu": True,
            "streaming": True,
            "legacy_api": False
        }
        self.settings = self.default_settings.copy()
        self.load_settings()
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                logger.info("Настройки LLM загружены из файла")
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек модели: {e}")
    
    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек модели: {e}")
    
    def get(self, key, default=None): return self.settings.get(key, default)
    def set(self, key, value):
        if key in self.settings:
            self.settings[key] = value
            self.save_settings()
            return True
        return False
    
    def reset_to_defaults(self):
        self.settings = self.default_settings.copy()
        self.save_settings()

    def get_recommended_settings(self): return self.default_settings.copy()
    
    def get_max_values(self):
        return {
            "context_size": 32768, "output_tokens": 100000, "batch_size": 2048,
            "n_threads": 24, "temperature": 2.0, "top_p": 1.0, "repeat_penalty": 2.0,
            "top_k": 200, "min_p": 1.0, "frequency_penalty": 2.0, "presence_penalty": 2.0
        }
    
    def get_all(self): return self.settings.copy()

# Инициализируем настройки  
model_settings = ModelSettings()
MODEL_CONTEXT_SIZE = model_settings.get("context_size")
DEFAULT_OUTPUT_TOKENS = model_settings.get("output_tokens")
VERBOSE_OUTPUT = model_settings.get("verbose")

# Включаем режим микросервисов принудительно
USE_LLM_SVC = True
def initialize_model():
    """Инициализация модели через сетевой сервис  """
    if USE_LLM_SVC:
        logger.info("[SVC] Инициализация связи с llm-service...")
        try:
            # Инициализируем сервис (  логики работы с loop)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(get_llm_service()))
                    future.result()
            else:
                loop.run_until_complete(get_llm_service())
            
            logger.info("[SVC] Связь с сервисом LLM подтверждена")
            return True
        except Exception as e:
            logger.error(f"[SVC] Ошибка инициализации: {e}")
            return False
    else:
        return True

def update_model_settings(new_settings):
    """Обновление настроек """
    global model_settings, MODEL_CONTEXT_SIZE, DEFAULT_OUTPUT_TOKENS, VERBOSE_OUTPUT
    for key, value in new_settings.items():
        model_settings.set(key, value)
    MODEL_CONTEXT_SIZE = model_settings.get("context_size")
    DEFAULT_OUTPUT_TOKENS = model_settings.get("output_tokens")
    VERBOSE_OUTPUT = model_settings.get("verbose")
    return True

# Глобальная переменная для выбранной модели  
_selected_model_name = None

def reload_model_by_path(model_path):
    """Перезагрузка модели с новым файлом модели (через llm-svc)"""
    global _selected_model_name
    
    if USE_LLM_SVC:
        # Проверяем, что путь не является директорией
        if os.path.isdir(model_path):
            logger.warning(f"Передан путь к директории вместо файла модели: {model_path}. Пропускаем загрузку.")
            return False
        
        # Проверяем, является ли путь llm-svc путем
        if model_path.startswith("llm-svc://"):
            # Извлекаем имя модели из пути
            model_name = model_path.replace("llm-svc://", "").strip()
            if not model_name:
                logger.warning("llm-svc: пустое имя модели в пути")
                return False
            global _selected_model_name
            _selected_model_name = model_name
            # Запрашиваем llm-svc реально переключить загруженную модель (веса)
            try:
                async def _load_on_llm_svc():
                    service = await get_llm_service()
                    ok = await service.client.load_model(model_name)
                    if ok:
                        service.model_name = model_name
                        logger.info(f"[llm-svc] Обновлён model_name в бэкенде: {model_name}")
                    return ok
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _load_on_llm_svc())
                        return future.result()
                else:
                    return loop.run_until_complete(_load_on_llm_svc())
            except Exception as e:
                logger.exception(f"Ошибка переключения модели в llm-svc: {e}")
                return False
        
        # Если путь к локальному файлу, но мы используем llm-svc, предупреждаем
        if os.path.exists(model_path) and model_path.endswith('.gguf'):
            logger.warning(f"Передан путь к локальному файлу модели {model_path}, но используется llm-svc. Модель должна быть доступна через llm-svc.")
            return True
        
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
    """Получение информации о модели через API"""
    global _selected_model_name
    if USE_LLM_SVC:
        try:
            async def _get_info():
                service = await get_llm_service()
                health = await service.client.health_check()
                return service, health
            
            # Запуск асинхронки в синхронном контексте  
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    service, health = executor.submit(lambda: asyncio.run(_get_info())).result()
            else:
                service, health = loop.run_until_complete(_get_info())
            
            if health and health.get("status") == "healthy":
                model_name = _selected_model_name or health.get("model_name") or getattr(service, "model_name", "Unknown")
                return {
                    "loaded": health.get("model_loaded", True),
                    "name": model_name,
                    "metadata": {"general.architecture": "Distributed LLM-SVC"},
                    "path": f"llm-svc://{model_name}",
                    "n_ctx": MODEL_CONTEXT_SIZE,
                    "n_gpu_layers": -1
                }
            return {"loaded": False, "error": "llm-svc unreachable"}
        except Exception as e:
            logger.error(f"Error get_model_info: {e}")
            return {"loaded": False, "error": str(e)}
    return {"loaded": True, "name": "Local Mode", "path": "local"}

def prepare_prompt(text, system_prompt=None, history=None, model_path=None, custom_prompt_id=None):
    """Сборка промпта в формате IM  """
    if system_prompt is None:
        if model_path:
            system_prompt = context_prompt_manager.get_effective_prompt(model_path, custom_prompt_id)
        else:
            system_prompt = context_prompt_manager.get_global_prompt()
    
    parts = []
    if system_prompt and system_prompt.strip():
        parts.append(f"<|im_start|>system\n{system_prompt}\n<|im_end|>")
    
    if history:
        for entry in history:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            parts.append(f"<|im_start|>{role}\n{content}\n<|im_end|>")
    
    parts.append(f"<|im_start|>user\n{text.strip()}\n<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)

def ask_agent(prompt, history=None, max_tokens=None, streaming=False, stream_callback=None, 
              model_path=None, custom_prompt_id=None, images=None, system_prompt=None):
    """Главная функция-точка входа для агентов"""
    
    if USE_LLM_SVC:
        logger.info(f"[SVC] Вызов ask_agent, streaming={streaming}")
        if max_tokens is None:
            max_tokens = model_settings.get("output_tokens")
        
        try:
            # Вызываем обертку из llm_client.py
            response = ask_agent_llm_svc(
                prompt=prompt,
                history=history,
                max_tokens=max_tokens,
                streaming=streaming,
                stream_callback=stream_callback,
                model_path=model_path,
                custom_prompt_id=custom_prompt_id,
                images=images,
                system_prompt=system_prompt
            )
            
            if response is None:
                logger.warning("Генерация прервана пользователем")
                return None
            return response
            
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.error(f"Ошибка ask_agent: {e}")
            return f"Извините, произошла ошибка: {str(e)}"
    else:
        logger.warning("Режим локальной работы отключен. Запустите микросервисы.")
        return "Ошибка: llm-service недоступен."

# Логирование загрузки модуля
logger.info("Модуль agent_llm_svc (микросервисная версия) загружен")