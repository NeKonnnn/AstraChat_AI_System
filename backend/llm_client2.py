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
from urllib.parse import urlparse
import io
import os

# Импортируем настройки
from settings import get_settings

logger = logging.getLogger(__name__)

class LLMClient:
    """Клиент для взаимодействия с llm-svc API"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        # Получаем настройки
        settings = get_settings()
        llm_svc_config = settings.llm_service
        
        # Определяем URL для подключения
        if base_url is None:
            # Используем метод get_llm_service_url, который автоматически определяет окружение
            self.base_url = settings.get_llm_service_url().rstrip('/')
        else:
            self.base_url = base_url.rstrip('/')
        
        # Проверяем на опечатки в URL (1lm вместо llm)
        if "1lm-svc" in self.base_url or "11m-svc" in self.base_url:
            logger.error(f"ОБНАРУЖЕНА ОПЕЧАТКА В URL: {self.base_url}. Исправляем на llm-svc")
            self.base_url = self.base_url.replace("1lm-svc", "llm-svc").replace("11m-svc", "llm-svc")
            logger.info(f"Исправленный URL: {self.base_url}")
        
        # Логируем используемый URL и порт для отладки (чтобы видеть, не уехал ли на 80 вместо 8000)
        try:
            parsed = urlparse(self.base_url)
            host = parsed.hostname or parsed.netloc
            port = parsed.port or (80 if parsed.scheme == "http" else 443)
            logger.info(f"LLMClient инициализирован: base_url={self.base_url}, host={host}, port={port}")
        except Exception:
            logger.info(f"LLMClient инициализирован с base_url: {self.base_url}")
        
        # API Key: приоритет явно переданного значения, затем из конфигурации
        if api_key is not None:
            self.api_key = api_key
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
            logger.info(f"[LLMClient] API Key передан явно в конструктор: {masked_key}")
        else:
            self.api_key = llm_svc_config.api_key
            if self.api_key:
                masked_key = f"{self.api_key[:8]}...{self.api_key[-4:]}" if len(self.api_key) > 12 else "***"
                logger.info(f"[LLMClient] API Key взят из конфигурации: {masked_key}")
            else:
                logger.warning("[LLMClient] API Key не найден в конфигурации (будет None)")
        
        # Use auth: берем из конфигурации
        self.use_auth = llm_svc_config.use_auth
        logger.info(f"[LLMClient] Use auth: {self.use_auth}")
        
        # Логируем итоговую конфигурацию авторизации
        if self.use_auth and self.api_key:
            logger.info("[LLMClient] ✓ Авторизация включена и API Key установлен - Bearer токен будет использоваться")
        elif self.use_auth and not self.api_key:
            logger.warning("[LLMClient] ⚠ Авторизация включена, но API Key отсутствует - запросы могут не пройти!")
        elif not self.use_auth:
            logger.info("[LLMClient] Авторизация отключена - Bearer токен не будет использоваться")
        
        self.timeout = llm_svc_config.timeout
        # verify_ssl из settings: уже разрешён с приоритетом NEXUS_CERT_PATH > LLM_VERIFY_SSL > YAML
        self.verify_ssl = getattr(llm_svc_config, "verify_ssl", True)
        if isinstance(self.verify_ssl, str):
            # Путь к CA bundle (пришёл из NEXUS_CERT_PATH или LLM_CA_BUNDLE)
            if os.path.isfile(self.verify_ssl):
                self._verify = self.verify_ssl
                logger.info(f"[LLMClient] SSL CA bundle: {self._verify}")
            else:
                logger.warning(f"[LLMClient] CA bundle не найден по пути: {self.verify_ssl}, используется verify=True")
                self._verify = True
        else:
            self._verify = self.verify_ssl
            if not self.verify_ssl:
                logger.warning("[LLMClient] Проверка SSL отключена (verify_ssl=false)")
        
    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков для запросов (JSON)"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Добавляем Authorization: Bearer токен, если включена авторизация
        if self.use_auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_auth_header(self) -> Dict[str, str]:
        """Получение только Authorization заголовка (для multipart/form-data запросов с files=)"""
        if self.use_auth and self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка состояния (vLLM: /health, llm-svc: /v1/health)"""
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=10.0) as client:
                headers = self._get_headers()
                # vLLM использует /health, llm-svc — /v1/health
                for path in ("/health", "/v1/health"):
                    try:
                        response = await client.get(f"{self.base_url}{path}", headers=headers)
                        response.raise_for_status()
                        result = response.json() if response.content else {"status": "healthy"}
                        logger.info(f"health_check: path={path}, status_code={response.status_code}, result={result}")
                        return result
                    except httpx.HTTPStatusError as e:
                        logger.debug(f"health_check: path={path} -> {e.response.status_code}, пробуем следующий path")
                        continue
                unhealthy = {"status": "unhealthy", "error": "health check failed on /health and /v1/health"}
                logger.warning(f"health_check: ни один path не ответил OK, result={unhealthy}")
                return unhealthy
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья llm-svc: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """Получение списка доступных моделей (vLLM/OpenAI-совместимый endpoint /v1/models)"""
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/models",
                    headers=self._get_headers()
                )
                if response.status_code >= 400:
                    logger.error(
                        f"get_models: HTTP {response.status_code}, url={response.url}, "
                        f"body={response.text[:400] if response.text else '(empty)'}"
                    )
                response.raise_for_status()
                data = response.json()
                # vLLM/OpenAI: список моделей в data.data или в корне
                return data.get("data", data if isinstance(data, list) else [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Ошибка получения списка моделей: {e.response.status_code} {e.response.text[:300]}")
            return []
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    @staticmethod
    def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
        """Собирает промпт из списка сообщений для /inference/v1/generate."""
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    x.get("text", "") for x in content if isinstance(x, dict)
                )
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts) + "\nassistant: "

    def _normalize_generate_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Приводит ответ /inference/v1/generate (choices[0].text) к формату chat (choices[0].message.content)."""
        if not isinstance(result, dict) or "choices" not in result or not result["choices"]:
            return result
        choice = result["choices"][0]
        if "message" in choice:
            return result
        text = choice.get("text", "")
        result["choices"][0] = {"message": {"role": "assistant", "content": text}, "index": 0}
        return result

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen-coder-30b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Отправка запроса на генерацию ответа. Пробует vLLM эндпоинты: /v1/chat/completions, /v1/messages, /inference/v1/generate."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        # vLLM: чат — /v1/chat/completions или /v1/messages; генерация — /inference/v1/generate
        endpoints_nonstream = [
            ("/v1/chat/completions", payload, None),
            ("/v1/messages", payload, None),
            ("/inference/v1/generate", {
                "model": model,
                "prompt": self._messages_to_prompt(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }, "_normalize"),
        ]
        logger.info(f"[LLMClient/chat_completion] Модель: {model}, max_tokens: {max_tokens}, stream: {stream}, messages: {len(messages)}")
        request_timeout = httpx.Timeout(self.timeout, connect=10.0, read=self.timeout, write=10.0)
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=request_timeout) as client:
                if stream:
                    for path in ("/v1/chat/completions", "/v1/messages"):
                        try:
                            stream_ctx = client.stream(
                                "POST",
                                f"{self.base_url}{path}",
                                headers={**self._get_headers(), "Accept": "text/event-stream"},
                                json=payload
                            )
                            async with stream_ctx as r:
                                r.raise_for_status()
                                logger.info(f"[LLMClient/chat_completion] stream OK: {path}")
                                return r
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                continue
                            raise
                    raise RuntimeError("chat_completion stream: ни один эндпоинт не доступен")
                for path, body, normalize in endpoints_nonstream:
                    try:
                        response = await client.post(
                            f"{self.base_url}{path}",
                            headers=self._get_headers(),
                            json=body
                        )
                        response.raise_for_status()
                        result = response.json()
                        if normalize == "_normalize":
                            result = self._normalize_generate_response(result)
                        logger.info(f"[LLMClient/chat_completion] OK path={path}, keys={list(result.keys()) if isinstance(result, dict) else 'n/a'}")
                        return result
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 404:
                            continue
                        raise
            raise RuntimeError("chat_completion: ни один эндпоинт не ответил успешно")
        except httpx.TimeoutException as e:
            logger.error(f"[LLMClient/chat_completion] TIMEOUT (timeout={self.timeout}): {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLMClient/chat_completion] HTTP {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[LLMClient/chat_completion] Ошибка: {e}")
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
            
            # Увеличенный таймаут для обычной транскрипции (до 15 минут)
            transcribe_timeout = httpx.Timeout(900.0, connect=10.0, read=900.0, write=60.0)
            async with httpx.AsyncClient(verify=self._verify, timeout=transcribe_timeout) as client:
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
            
            async with httpx.AsyncClient(verify=self._verify, timeout=300.0) as client:
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
            async with httpx.AsyncClient(verify=self._verify, timeout=10.0) as client:
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
            async with httpx.AsyncClient(verify=self._verify, timeout=10.0) as client:
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
            
            # Увеличенный таймаут для WhisperX транскрипции больших файлов (до 30 минут)
            whisperx_timeout = httpx.Timeout(1800.0, connect=10.0, read=1800.0, write=60.0)
            async with httpx.AsyncClient(verify=self._verify, timeout=whisperx_timeout) as client:
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
            
            # Увеличенный таймаут для диаризации больших файлов (до 60 минут)
            diarize_timeout = httpx.Timeout(3600.0, connect=10.0, read=3600.0, write=60.0)
            async with httpx.AsyncClient(verify=self._verify, timeout=diarize_timeout) as client:
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
            async with httpx.AsyncClient(verify=self._verify, timeout=60.0) as client:
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
            
            # Увеличенный таймаут для больших файлов с диаризацией (до 60 минут)
            transcribe_timeout = httpx.Timeout(3600.0, connect=10.0, read=3600.0, write=60.0)
            async with httpx.AsyncClient(verify=self._verify, timeout=transcribe_timeout) as client:
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
            files = {"file": (filename, io.BytesIO(image_file), mime_type)}
            data = {"languages": languages}
            async with httpx.AsyncClient(verify=self._verify, timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/ocr",
                    files=files,
                    data=data,
                    headers={**self._get_auth_header(), "Accept": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"recognize_text_from_image: HTTP {e.response.status_code}: {e.response.text[:300]}")
            raise
        except Exception as e:
            logger.error(f"Ошибка OCR распознавания изображения: {e}")
            raise

    async def get_response(self, response_id: str) -> Dict[str, Any]:
        """Получение ответа по ID (vLLM: GET /v1/responses/{response_id})."""
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/responses/{response_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"get_response({response_id}): HTTP {e.response.status_code}: {e.response.text[:300]}")
            raise
        except Exception as e:
            logger.error(f"Ошибка получения ответа {response_id}: {e}")
            raise

    async def cancel_response(self, response_id: str) -> Dict[str, Any]:
        """Отмена ответа по ID (vLLM: POST /v1/responses/{response_id}/cancel)."""
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/responses/{response_id}/cancel",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error(f"cancel_response({response_id}): HTTP {e.response.status_code}: {e.response.text[:300]}")
            raise
        except Exception as e:
            logger.error(f"Ошибка отмены ответа {response_id}: {e}")
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
        settings = get_settings()
        llm_svc_config = settings.llm_service
        
        self.model_name = llm_svc_config.default_model
        self.fallback_model = llm_svc_config.fallback_model
        self.auto_select = llm_svc_config.auto_select
        
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
                        choice = response["choices"][0]
                        msg = choice.get("message", {})
                        text = msg.get("content", "") if msg else choice.get("text", "")
                        return text or ""
                    return ""
                except Exception as e:
                    logger.error(f"[generate_response] Ошибка: {e}")
                    raise

    async def _stream_generation(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        stream_callback: Callable[[str, str], bool],
        model_name: Optional[str] = None
    ) -> Optional[str]:
        """Потоковая генерация. Пробует /v1/chat/completions, затем /v1/messages (vLLM)."""
        accumulated_text = ""
        payload = {
            "model": model_name or self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        stream_timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=10.0)
        logger.info(f"[_stream_generation] Начало, model={model_name or self.model_name}")
        try:
            for path in ("/v1/chat/completions", "/v1/messages"):
                try:
                    async with httpx.AsyncClient(verify=self.client._verify, timeout=stream_timeout) as http_client:
                        async with http_client.stream(
                            "POST",
                            f"{self.client.base_url}{path}",
                            headers={**self.client._get_headers(), "Accept": "text/event-stream"},
                            json=payload
                        ) as response:
                            response.raise_for_status()
                            logger.info(f"[_stream_generation] stream OK: {path}")
                            async for line in response.aiter_lines():
                                if not line.startswith("data: "):
                                    continue
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                if "choices" not in data or not data["choices"]:
                                    continue
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})
                                chunk = delta.get("content") or choice.get("text") or ""
                                if chunk:
                                    accumulated_text += chunk
                                    try:
                                        if stream_callback(chunk, accumulated_text) is False:
                                            return None
                                    except Exception as callback_error:
                                        logger.error(f"[_stream_generation] stream_callback: {callback_error}")
                            logger.info(f"[_stream_generation] Завершено, символов: {len(accumulated_text)}")
                            return accumulated_text
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        continue
                    raise
            return "Ошибка: ни один stream-эндпоинт не доступен (/v1/chat/completions, /v1/messages)."
        except httpx.ConnectError as e:
            logger.error(f"[_stream_generation] Ошибка подключения: {e}")
            return "Ошибка: не удалось подключиться к сервису LLM. Проверьте, что llm-svc запущен."
        except httpx.TimeoutException as e:
            logger.error(f"[_stream_generation] Timeout: {e}")
            return "Ошибка: превышено время ожидания ответа от llm-svc. Модель может быть занята или не загружена."
        except Exception as e:
            logger.error(f"[_stream_generation] Ошибка: {e}")
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
        settings = get_settings()
        llm_svc_config = settings.llm_service
        
        base_url = None  # Будет определено в LLMService
        api_key = llm_svc_config.api_key  # Берем из конфигурации
        
        # Логируем информацию о api_key для отладки
        if api_key:
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
            logger.info(f"[get_llm_service] API Key получен из конфигурации: {masked_key}")
        else:
            logger.warning("[get_llm_service] API Key не найден в конфигурации (будет None)")
        
        logger.info(f"[get_llm_service] Создание LLMService с use_auth={llm_svc_config.use_auth}")
        llm_service = LLMService(base_url, api_key)
        logger.info("[get_llm_service] Инициализация LLMService...")
        await llm_service.initialize()
        logger.info("[get_llm_service] LLMService успешно инициализирован")
    else:
        logger.debug("[get_llm_service] Используется существующий экземпляр LLMService")
    
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