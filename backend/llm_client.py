"""
LLM Client для взаимодействия с llm-svc сервисом
Обеспечивает совместимость с OpenAI API через llm-svc
"""

import httpx
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from datetime import datetime
import io
import os

# Импортируем конфигурацию
from config import get_config

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для взаимодействия с llm-svc API"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Получаем конфигурацию
        config = get_config()
        llm_svc_config = config.get("microservices", {}).get("llm_svc", {})
        
        # Определяем URL для подключения
        if base_url is None:
            # В Docker используем внутренний URL, в разработке - внешний
            if os.getenv("DOCKER_ENV") == "true":
                self.base_url = llm_svc_config.get("base_url", "http://llm-svc:8000").rstrip('/')
            else:
                self.base_url = llm_svc_config.get("external_url", "http://localhost:8001").rstrip('/')
        else:
            self.base_url = base_url.rstrip('/')
        
        # Проверяем на опечатки в URL (1lm вместо llm)
        if "1lm-svc" in self.base_url or "11m-svc" in self.base_url:
            logger.error(f"ОБНАРУЖЕНА ОПЕЧАТКА В URL: {self.base_url}. Исправляем на llm-svc")
            self.base_url = self.base_url.replace("1lm-svc", "llm-svc").replace("11m-svc", "llm-svc")
            logger.info(f"Исправленный URL: {self.base_url}")
        
        # Логируем используемый URL для отладки
        logger.info(f"LLMClient инициализирован с base_url: {self.base_url}, DOCKER_ENV: {os.getenv('DOCKER_ENV')}")
            
        self.api_key = api_key
        self.timeout = llm_svc_config.get("timeout", 300.0)
        
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния llm-svc"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/health",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья llm-svc: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Получение списка доступных моделей"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-coder-30b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Отправка запроса на генерацию ответа"""
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        logger.info(f"[LLMClient/chat_completion] Отправка запроса к {self.base_url}/v1/chat/completions")
        logger.info(f"[LLMClient/chat_completion] Модель: {model}, max_tokens: {max_tokens}, stream: {stream}")
        logger.info(f"[LLMClient/chat_completion] Timeout: {self.timeout} секунд")
        logger.info(f"[LLMClient/chat_completion] Количество сообщений: {len(messages)}")
        
        try:
            # Увеличиваем timeout для агентного режима (планирование может занять больше времени)
            request_timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout, write=10.0)
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                if stream:
                    # Потоковый запрос
                    logger.info(f"[LLMClient/chat_completion] Потоковый запрос...")
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        headers={**self._get_headers(), "Accept": "text/event-stream"},
                        json=payload
                    ) as response:
                        logger.info(f"[LLMClient/chat_completion] Получен ответ, status: {response.status_code}")
                        response.raise_for_status()
                        return response
                else:
                    # Обычный запрос
                    logger.info(f"[LLMClient/chat_completion] Обычный запрос (не потоковый)...")
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=self._get_headers(),
                        json=payload
                    )
                    logger.info(f"[LLMClient/chat_completion] Получен ответ, status: {response.status_code}")
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"[LLMClient/chat_completion] Ответ распарсен, keys: {list(result.keys()) if isinstance(result, dict) else 'не dict'}")
                    return result
        except httpx.TimeoutException as e:
            logger.error(f"[LLMClient/chat_completion] TIMEOUT при запросе к llm-svc (timeout={self.timeout}): {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLMClient/chat_completion] HTTP ошибка {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[LLMClient/chat_completion] Ошибка запроса к llm-svc: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def transcribe_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "ru"
    ) -> Dict[str, Any]:
        """Транскрибация аудио файла через Vosk"""
        try:
            files = {
                "file": (filename, io.BytesIO(audio_file), "audio/wav")
            }
            data = {
                "language": language
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/transcribe",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка транскрибации аудио: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        language: str = "auto",
        speaker: str = "baya",
        sample_rate: int = 48000,
        speech_rate: float = 1.0
    ) -> bytes:
        """Синтез речи из текста через Silero"""
        try:
            data = {
                "text": text,
                "language": language,
                "speaker": speaker,
                "sample_rate": sample_rate,
                "speech_rate": speech_rate
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/synthesize",
                    data=data,
                    headers={"Accept": "audio/wav"}
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Ошибка синтеза речи: {e}")
            raise
    
    async def get_transcription_health(self) -> Dict[str, Any]:
        """Проверка состояния сервиса транскрипции"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/transcription/health",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка проверки состояния транскрипции: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_tts_health(self) -> Dict[str, Any]:
        """Проверка состояния сервиса TTS"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/tts/health",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка проверки состояния TTS: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def transcribe_audio_whisperx(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        compute_type: str = "float16",
        batch_size: int = 16
    ) -> Dict[str, Any]:
        """Транскрибация аудио файла через WhisperX"""
        try:
            files = {
                "file": (filename, io.BytesIO(audio_file), "audio/wav")
            }
            data = {
                "language": language,
                "compute_type": compute_type,
                "batch_size": batch_size
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/whisperx/transcribe",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка транскрибации WhisperX: {e}")
            raise
    
    async def diarize_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 1.0
    ) -> Dict[str, Any]:
        """Диаризация аудио файла"""
        try:
            files = {
                "file": (filename, io.BytesIO(audio_file), "audio/wav")
            }
            data = {
                "min_speakers": min_speakers,
                "max_speakers": max_speakers,
                "min_duration": min_duration
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/diarize",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка диаризации аудио: {e}")
            raise
    
    async def reload_whisperx_models(self) -> Dict[str, Any]:
        """Принудительная перезагрузка моделей WhisperX"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/whisperx/reload",
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            error_msg = f"Не удалось подключиться к llm-svc по адресу {self.base_url} для перезагрузки моделей."
            logger.error(f"Ошибка подключения к llm-svc: {error_msg}. Детали: {e}")
            raise Exception(error_msg) from e
        except httpx.HTTPStatusError as e:
            error_msg = f"Ошибка HTTP {e.response.status_code} при перезагрузке моделей: {e.response.text}"
            logger.error(f"Ошибка HTTP при перезагрузке моделей: {error_msg}")
            raise Exception(error_msg) from e
        except Exception as e:
            logger.error(f"Ошибка перезагрузки моделей WhisperX: {e}")
            raise
    
    async def transcribe_with_diarization(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 1.0
    ) -> Dict[str, Any]:
        """Комбинированная транскрибация с диаризацией"""
        try:
            # Подготавливаем данные для запроса
            data = {
                "language": language,
                "min_speakers": min_speakers,
                "max_speakers": max_speakers,
                "min_duration": min_duration
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Создаем файл для первого запроса
                files = {
                    "file": (filename, io.BytesIO(audio_file), "audio/wav")
                }
                
                response = await client.post(
                    f"{self.base_url}/v1/transcribe_with_diarization",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                
                # Если получили ошибку 503 с сообщением о незагруженных моделях, пытаемся перезагрузить
                if response.status_code == 503:
                    response_text = response.text
                    if "Модели WhisperX не загружены" in response_text or "WhisperX models not loaded" in response_text:
                        logger.warning("Модели WhisperX не загружены, пытаемся перезагрузить...")
                        try:
                            await self.reload_whisperx_models()
                            logger.info("Модели WhisperX перезагружены, повторяем запрос транскрибации...")
                            # Повторяем запрос после перезагрузки (создаем новый BytesIO)
                            files_retry = {
                                "file": (filename, io.BytesIO(audio_file), "audio/wav")
                            }
                            response = await client.post(
                                f"{self.base_url}/v1/transcribe_with_diarization",
                                files=files_retry,
                                data=data,
                                headers={"Accept": "application/json"}
                            )
                        except Exception as reload_error:
                            logger.error(f"Не удалось перезагрузить модели WhisperX: {reload_error}")
                            # Продолжаем с исходной ошибкой
                
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            error_msg = f"Не удалось подключиться к llm-svc по адресу {self.base_url}. Убедитесь, что сервис запущен и доступен."
            logger.error(f"Ошибка подключения к llm-svc: {error_msg}. Детали: {e}")
            raise Exception(error_msg) from e
        except httpx.HTTPStatusError as e:
            error_msg = f"Ошибка HTTP {e.response.status_code} от llm-svc: {e.response.text}"
            logger.error(f"Ошибка HTTP от llm-svc: {error_msg}")
            raise Exception(error_msg) from e
        except Exception as e:
            logger.error(f"Ошибка комбинированной обработки: {e}")
            raise
    
    async def recognize_text_from_image(
        self,
        image_file: bytes,
        filename: str = "image.jpg",
        languages: str = "ru,en"
    ) -> Dict[str, Any]:
        """Распознавание текста с изображения через Surya OCR"""
        try:
            # Определяем MIME тип на основе расширения файла
            mime_type = "image/jpeg"
            if filename.lower().endswith(".png"):
                mime_type = "image/png"
            elif filename.lower().endswith(".webp"):
                mime_type = "image/webp"
            elif filename.lower().endswith(".bmp"):
                mime_type = "image/bmp"
            elif filename.lower().endswith(".tiff") or filename.lower().endswith(".tif"):
                mime_type = "image/tiff"
            
            files = {
                "file": (filename, io.BytesIO(image_file), mime_type)
            }
            data = {
                "languages": languages
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/ocr",
                    files=files,
                    data=data,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка распознавания текста с изображения: {e}")
            raise
    
    async def get_ocr_health(self) -> Dict[str, Any]:
        """Проверка состояния сервиса OCR"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/ocr/health",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Ошибка проверки состояния OCR: {e}")
            return {"status": "unhealthy", "error": str(e)}

class LLMService:
    """Сервис для работы с LLM через llm-svc"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.client = LLMClient(base_url, api_key)
        
        # Получаем настройки модели из конфигурации
        config = get_config()
        llm_svc_config = config.get("microservices", {}).get("llm_svc", {})
        models_config = llm_svc_config.get("models", {})
        
        self.model_name = models_config.get("default", "qwen-coder-30b")
        self.fallback_model = models_config.get("fallback", "deepseek-coder-6.7b")
        self.auto_select = models_config.get("auto_select", True)
        
    async def initialize(self) -> bool:
        """Инициализация сервиса"""
        try:
            health = await self.client.health_check()
            if health.get("status") == "healthy":
                logger.info("llm-svc сервис доступен")
                
                # Получаем список моделей
                models = await self.client.get_models()
                if models:
                    self.model_name = models[0]["id"]
                    logger.info(f"Используется модель: {self.model_name}")
                
                return True
            else:
                logger.error(f"llm-svc недоступен: {health}")
                return False
        except Exception as e:
            logger.error(f"Ошибка инициализации llm-svc: {e}")
            return False
    
    def prepare_messages(self, prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                        system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """Подготовка сообщений в формате OpenAI API"""
        messages = []
        
        # Добавляем системный промпт
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        elif history and len(history) > 0:
            # Если нет custom промпта, но есть история - добавляем информацию о доступности истории
            system_prompt_with_history = """Ты - полезный AI ассистент. У тебя есть доступ к полной истории диалога с пользователем.       
            Важные возможности:
            - Ты МОЖЕШЬ обращаться к предыдущим сообщениям в диалоге
            - Ты МОЖЕШЬ подсчитать количество токенов и сообщений в истории
            - Ты ВИДИШЬ все предыдущие сообщения в этом диалоге
            - Ты МОЖЕШЬ ссылаться на информацию из предыдущих сообщений

            Когда пользователь спрашивает о предыдущих сообщениях или токенах - используй доступную историю для ответа."""
            messages.append({"role": "system", "content": system_prompt_with_history})
        
        # Добавляем историю диалога
        if history:
            for entry in history:
                role = entry.get("role", "user")
                content = entry.get("content", "")
                if role in ["user", "assistant", "system"]:
                    # Фильтруем пустые сообщения ассистента (они сбивают LLM)
                    if role == "assistant" and not content.strip():
                        logger.debug(f"Пропускаем пустое сообщение ассистента из истории")
                        continue
                    messages.append({"role": role, "content": content})
        
        # Добавляем текущий запрос
        messages.append({"role": "user", "content": prompt})
        
        return messages
    
    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        streaming: bool = False,
        stream_callback: Optional[Callable[[str, str], bool]] = None,
        images: Optional[List[str]] = None,
        model_path: Optional[str] = None
    ) -> str:
        """Генерация ответа через llm-svc"""
        
        try:
            # Логируем информацию об истории
            if history:
                logger.info(f"История диалога: {len(history)} сообщений передается в LLM")
                # Подсчитываем примерное количество токенов (грубая оценка: ~1 токен = 4 символа для русского)
                total_chars = sum(len(msg.get("content", "")) for msg in history)
                estimated_tokens = total_chars // 4
                logger.info(f"Примерное количество токенов в истории: {estimated_tokens}")
            else:
                logger.info("История диалога пуста или не передана")
            
            # Подготавливаем сообщения
            messages = self.prepare_messages(prompt, history, system_prompt)
            
            # Логируем общее количество сообщений, отправляемых в LLM
            logger.info(f"Всего сообщений для LLM: {len(messages)} (включая system prompt и текущий запрос)")
            
            # Если есть изображения, добавляем их к последнему сообщению пользователя
            if images:
                logger.info(f"Добавление {len(images)} изображений к запросу")
                # Находим последнее сообщение пользователя
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        # Преобразуем содержимое в мультимодальный формат
                        content = msg.get("content", "")
                        msg["content"] = [
                            {"type": "text", "text": content}
                        ]
                        # Добавляем изображения
                        for image_path in images:
                            msg["content"].append({
                                "type": "image_url",
                                "image_url": {"url": f"file://{image_path}"}
                            })
                        break
            
            # Определяем модель для использования
            if model_path and model_path.startswith("llm-svc://"):
                # Извлекаем имя модели из пути llm-svc://
                model_to_use = model_path.replace("llm-svc://", "")
            else:
                # Используем сохраненную модель или модель по умолчанию
                model_to_use = self.model_name
            
            if streaming and stream_callback:
                # Потоковая генерация
                return await self._stream_generation(
                    messages, temperature, max_tokens, stream_callback, model_to_use
                )
            else:
                # Обычная генерация
                logger.info(f"[generate_response] Отправляем запрос к llm-svc, модель: {model_to_use}, max_tokens: {max_tokens}")
                logger.info(f"[generate_response] Количество сообщений: {len(messages)}")
                
                try:
                    response = await self.client.chat_completion(
                        messages=messages,
                        model=model_to_use,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False
                    )
                    logger.info(f"[generate_response] Получен ответ от llm-svc, keys: {list(response.keys()) if isinstance(response, dict) else 'не dict'}")
                    
                    if "choices" in response and len(response["choices"]) > 0:
                        content = response["choices"][0]["message"]["content"]
                        logger.info(f"[generate_response] Извлечен контент, длина: {len(content)} символов")
                        return content
                    else:
                        logger.error(f"[generate_response] Неожиданный формат ответа от llm-svc: {response}")
                        return "Ошибка генерации ответа"
                except asyncio.TimeoutError as e:
                    logger.error(f"[generate_response] TimeoutError при запросе к llm-svc: {e}")
                    raise
                except Exception as e:
                    logger.error(f"[generate_response] Исключение при запросе к llm-svc: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
                    
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return f"Извините, произошла ошибка при генерации ответа: {str(e)}"
    
    async def _stream_generation(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream_callback: Callable[[str, str], bool],
        model_name: Optional[str] = None
    ) -> str:
        """Потоковая генерация с колбэком"""
        
        accumulated_text = ""
        
        try:
            logger.info(f"[_stream_generation] Начало потоковой генерации, model={model_name or self.model_name}")
            logger.info(f"[_stream_generation] Отправка запроса на {self.client.base_url}/v1/chat/completions")
            
            # Увеличиваем таймаут для потоковой генерации (особенно для агентного режима)
            stream_timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=10.0)
            
            async with httpx.AsyncClient(timeout=stream_timeout) as http_client:
                logger.info(f"[_stream_generation] HTTP клиент создан, отправляем POST запрос...")
                async with http_client.stream(
                    "POST",
                    f"{self.client.base_url}/v1/chat/completions",
                    headers={**self.client._get_headers(), "Accept": "text/event-stream"},
                    json={
                        "model": model_name or self.model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True
                    }
                ) as response:
                    logger.info(f"[_stream_generation] Получен ответ, status={response.status_code}")
                    response.raise_for_status()
                    
                    line_count = 0
                    async for line in response.aiter_lines():
                        line_count += 1
                        if line_count <= 3:  # Логируем первые 3 строки для диагностики
                            logger.info(f"[_stream_generation] Строка {line_count}: {line[:200]}")
                        
                        if line.startswith("data: "):
                            data_str = line[6:]  # Убираем "data: "
                            
                            if data_str.strip() == "[DONE]":
                                logger.info(f"[_stream_generation] Получен сигнал [DONE], всего строк обработано: {line_count}")
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        chunk = delta["content"]
                                        accumulated_text += chunk
                                        
                                        # Вызываем колбэк
                                        try:
                                            # logger.info(f"[_stream_generation] Вызываем stream_callback: chunk_len={len(chunk)}, acc_len={len(accumulated_text)}")
                                            should_continue = stream_callback(chunk, accumulated_text)
                                            # logger.info(f"[_stream_generation] stream_callback вернул: {should_continue}")
                                            if should_continue is False:  # Явная проверка на False
                                                # logger.info("[_stream_generation] Генерация остановлена по сигналу колбэка")
                                                return None  # Возвращаем None при отмене
                                        except Exception as callback_error:
                                            logger.error(f"[_stream_generation] Ошибка в stream_callback: {callback_error}")
                                            import traceback
                                            logger.error(traceback.format_exc())
                                            # Продолжаем генерацию при ошибке в callback
                            except json.JSONDecodeError:
                                continue
                    
                    logger.info(f"[_stream_generation] Генерация завершена, получено {len(accumulated_text)} символов")
                    logger.info(f"[_stream_generation] Всего строк обработано: {line_count}")
                    return accumulated_text
                
        except httpx.ConnectError as e:
            logger.error(f"[_stream_generation] Ошибка подключения к llm-svc: {e}")
            return "Ошибка: не удалось подключиться к сервису LLM. Проверьте, что llm-svc запущен."
        except httpx.TimeoutException as e:
            logger.error(f"[_stream_generation] Timeout при подключении к llm-svc: {e}")
            return "Ошибка: превышено время ожидания ответа от llm-svc. Модель может быть занята или не загружена."
        except Exception as e:
            logger.error(f"[_stream_generation] Ошибка потоковой генерации: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Ошибка потоковой генерации: {str(e)}"
    
    async def transcribe_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "ru"
    ) -> str:
        """Транскрибация аудио файла"""
        try:
            result = await self.client.transcribe_audio(audio_file, filename, language)
            if result.get("success"):
                return result.get("text", "")
            else:
                logger.error(f"Ошибка транскрибации: {result.get('error', 'Unknown error')}")
                return ""
        except Exception as e:
            logger.error(f"Ошибка транскрибации аудио: {e}")
            return ""
    
    async def synthesize_speech(
        self,
        text: str,
        language: str = "auto",
        speaker: str = "baya",
        sample_rate: int = 48000,
        speech_rate: float = 1.0
    ) -> bytes:
        """Синтез речи из текста"""
        try:
            return await self.client.synthesize_speech(
                text, language, speaker, sample_rate, speech_rate
            )
        except Exception as e:
            logger.error(f"Ошибка синтеза речи: {e}")
            return b""
    
    async def transcribe_audio_whisperx(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        compute_type: str = "float16",
        batch_size: int = 16
    ) -> str:
        """Транскрибация аудио файла через WhisperX"""
        try:
            result = await self.client.transcribe_audio_whisperx(
                audio_file, filename, language, compute_type, batch_size
            )
            if result.get("success"):
                return result.get("text", "")
            else:
                logger.error(f"Ошибка транскрибации WhisperX: {result.get('error', 'Unknown error')}")
                return ""
        except Exception as e:
            logger.error(f"Ошибка транскрибации WhisperX: {e}")
            return ""
    
    async def diarize_audio(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 1.0
    ) -> Dict[str, Any]:
        """Диаризация аудио файла"""
        try:
            return await self.client.diarize_audio(
                audio_file, filename, min_speakers, max_speakers, min_duration
            )
        except Exception as e:
            logger.error(f"Ошибка диаризации аудио: {e}")
            return {"success": False, "error": str(e)}
    
    async def transcribe_with_diarization(
        self,
        audio_file: bytes,
        filename: str = "audio.wav",
        language: str = "auto",
        min_speakers: int = 1,
        max_speakers: int = 10,
        min_duration: float = 1.0
    ) -> Dict[str, Any]:
        """Комбинированная транскрибация с диаризацией"""
        try:
            return await self.client.transcribe_with_diarization(
                audio_file, filename, language, min_speakers, max_speakers, min_duration
            )
        except Exception as e:
            logger.error(f"Ошибка комбинированной обработки: {e}")
            return {"success": False, "error": str(e)}
    
    async def recognize_text_from_image(
        self,
        image_file: bytes,
        filename: str = "image.jpg",
        languages: str = "ru,en"
    ) -> Dict[str, Any]:
        """Распознавание текста с изображения"""
        try:
            return await self.client.recognize_text_from_image(image_file, filename, languages)
        except httpx.HTTPStatusError as e:
            error_detail = "Неизвестная ошибка"
            try:
                error_response = e.response.json()
                error_detail = error_response.get("detail", str(e))
            except:
                error_detail = str(e)
            logger.error(f"Ошибка распознавания текста с изображения (HTTP {e.response.status_code}): {error_detail}")
            return {"success": False, "error": error_detail}
        except Exception as e:
            logger.error(f"Ошибка распознавания текста с изображения: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    async def get_audio_services_health(self) -> Dict[str, Any]:
        """Проверка состояния аудио сервисов"""
        try:
            transcription_health = await self.client.get_transcription_health()
            tts_health = await self.client.get_tts_health()
            
            return {
                "transcription": transcription_health,
                "tts": tts_health,
                "overall": "healthy" if (
                    transcription_health.get("status") == "healthy" and 
                    tts_health.get("status") == "healthy"
                ) else "unhealthy"
            }
        except Exception as e:
            logger.error(f"Ошибка проверки состояния аудио сервисов: {e}")
            return {"overall": "unhealthy", "error": str(e)}

# Глобальный экземпляр сервиса
llm_service = None

async def get_llm_service() -> LLMService:
    """Получение глобального экземпляра LLM сервиса"""
    global llm_service
    if llm_service is None:
        # Настройки из конфигурации
        config = get_config()
        llm_svc_config = config.get("microservices", {}).get("llm_svc", {})
        
        base_url = None  # Будет определено в LLMService
        api_key = None  # Можно добавить в конфиг в будущем
        
        llm_service = LLMService(base_url, api_key)
        await llm_service.initialize()
    
    return llm_service

# Синхронные обертки для совместимости с существующим кодом
def ask_agent_llm_svc(prompt: str, history: Optional[List[Dict[str, str]]] = None, 
                     max_tokens: Optional[int] = None, streaming: bool = False,
                     stream_callback: Optional[Callable[[str, str], bool]] = None,
                     model_path: Optional[str] = None, custom_prompt_id: Optional[str] = None,
                     images: Optional[List[str]] = None) -> str:
    """Синхронная обертка для ask_agent через llm-svc"""
    
    async def _async_generate():
        service = await get_llm_service()
        # Извлекаем имя модели из model_path, если он передан
        model_name_for_request = None
        if model_path and model_path.startswith("llm-svc://"):
            model_name_for_request = model_path.replace("llm-svc://", "")
        
        logger.info(f"[ask_agent_llm_svc] Вызов service.generate_response со стримингом: {streaming}")
        logger.info(f"[ask_agent_llm_svc] stream_callback: {'есть' if stream_callback else 'НЕТ'}")
        logger.info(f"[ask_agent_llm_svc] prompt длина: {len(prompt)} символов")
        logger.info(f"[ask_agent_llm_svc] max_tokens: {max_tokens or 1024}")
        
        try:
            logger.info(f"[ask_agent_llm_svc] Начинаем вызов service.generate_response...")
            result = await service.generate_response(
                prompt=prompt,
                history=history,
                system_prompt=None,  # Можно добавить поддержку custom_prompt_id
                temperature=0.7,
                max_tokens=max_tokens or 1024,
                streaming=streaming,
                stream_callback=stream_callback,
                images=images,
                model_path=model_path if model_path and model_path.startswith("llm-svc://") else None
            )
            logger.info(f"[ask_agent_llm_svc] service.generate_response завершён, результат: {len(result) if result else 0} символов")
            return result
        except asyncio.TimeoutError as e:
            logger.error(f"[ask_agent_llm_svc] TimeoutError в generate_response: {e}")
            raise
        except Exception as e:
            logger.error(f"[ask_agent_llm_svc] Исключение в generate_response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    # ИСПРАВЛЕНИЕ: Проверяем, есть ли запущенный loop в текущем потоке
    try:
        # Пытаемся получить текущий запущенный loop
        loop = asyncio.get_running_loop()
        # Если получили - значит мы в async контексте, но ask_agent_llm_svc - синхронная функция
        # Значит вызываем через run_coroutine_threadsafe из другого потока
        logger.info("[ask_agent_llm_svc] Обнаружен запущенный loop, используем run_coroutine_threadsafe")
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(_async_generate()))
            try:
                return future.result(timeout=120)
            except concurrent.futures.TimeoutError:
                logger.error(f"[ask_agent_llm_svc] TIMEOUT при ожидании ответа от llm-svc (120 сек)")
                future.cancel()
                return "Извините, превышено время ожидания ответа от модели."
            except concurrent.futures.CancelledError:
                logger.warning(f"[ask_agent_llm_svc] Генерация была отменена")
                return None
    except RuntimeError:
        # Нет запущенного loop - можем использовать asyncio.run напрямую
        logger.info("[ask_agent_llm_svc] Нет запущенного loop, используем asyncio.run")
        return asyncio.run(_async_generate())
    except asyncio.CancelledError:
        logger.warning(f"[ask_agent_llm_svc] Генерация была отменена (asyncio.CancelledError)")
        return None  # Возвращаем None при отмене
    except Exception as e:
        logger.error(f"[ask_agent_llm_svc] Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Произошла ошибка при обращении к модели: {str(e)}"

# Синхронные обертки для аудио функций
def transcribe_audio_llm_svc(audio_file: bytes, filename: str = "audio.wav", language: str = "ru") -> str:
    """Синхронная обертка для транскрибации аудио через llm-svc"""
    
    async def _async_transcribe():
        service = await get_llm_service()
        return await service.transcribe_audio(audio_file, filename, language)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_transcribe())
                return future.result()
        else:
            return loop.run_until_complete(_async_transcribe())
    except RuntimeError:
        return asyncio.run(_async_transcribe())

def synthesize_speech_llm_svc(text: str, language: str = "auto", speaker: str = "baya", 
                             sample_rate: int = 48000, speech_rate: float = 1.0) -> bytes:
    """Синхронная обертка для синтеза речи через llm-svc"""
    
    async def _async_synthesize():
        service = await get_llm_service()
        return await service.synthesize_speech(text, language, speaker, sample_rate, speech_rate)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_synthesize())
                return future.result()
        else:
            return loop.run_until_complete(_async_synthesize())
    except RuntimeError:
        return asyncio.run(_async_synthesize())

def transcribe_audio_whisperx_llm_svc(audio_file: bytes, filename: str = "audio.wav", 
                                     language: str = "auto", compute_type: str = "float16", 
                                     batch_size: int = 16) -> str:
    """Синхронная обертка для транскрибации WhisperX через llm-svc"""
    
    async def _async_transcribe():
        service = await get_llm_service()
        return await service.transcribe_audio_whisperx(audio_file, filename, language, compute_type, batch_size)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_transcribe())
                return future.result()
        else:
            return loop.run_until_complete(_async_transcribe())
    except RuntimeError:
        return asyncio.run(_async_transcribe())

def diarize_audio_llm_svc(audio_file: bytes, filename: str = "audio.wav", 
                         min_speakers: int = 1, max_speakers: int = 10, 
                         min_duration: float = 1.0) -> Dict[str, Any]:
    """Синхронная обертка для диаризации через llm-svc"""
    
    async def _async_diarize():
        service = await get_llm_service()
        return await service.diarize_audio(audio_file, filename, min_speakers, max_speakers, min_duration)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_diarize())
                return future.result()
        else:
            return loop.run_until_complete(_async_diarize())
    except RuntimeError:
        return asyncio.run(_async_diarize())

def transcribe_with_diarization_llm_svc(audio_file: bytes, filename: str = "audio.wav", 
                                       language: str = "auto", min_speakers: int = 1, 
                                       max_speakers: int = 10, min_duration: float = 1.0) -> Dict[str, Any]:
    """Синхронная обертка для комбинированной обработки через llm-svc"""
    
    async def _async_transcribe_diarize():
        service = await get_llm_service()
        return await service.transcribe_with_diarization(
            audio_file, filename, language, min_speakers, max_speakers, min_duration
        )
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_transcribe_diarize())
                return future.result()
        else:
            return loop.run_until_complete(_async_transcribe_diarize())
    except RuntimeError:
        return asyncio.run(_async_transcribe_diarize())

def recognize_text_from_image_llm_svc(image_file: bytes, filename: str = "image.jpg", 
                                     languages: str = "ru,en") -> Dict[str, Any]:
    """Синхронная обертка для распознавания текста с изображения через llm-svc"""
    
    async def _async_recognize():
        service = await get_llm_service()
        return await service.recognize_text_from_image(image_file, filename, languages)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _async_recognize())
                return future.result()
        else:
            return loop.run_until_complete(_async_recognize())
    except RuntimeError:
        return asyncio.run(_async_recognize())
