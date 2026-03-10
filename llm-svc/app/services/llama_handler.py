from llama_cpp import Llama
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator, Union
import os
import json
import asyncio
import time
import logging

from app.models.schemas import ChatResponse, ChatChoice, Message, UsageInfo, AssistantMessage
from app.utils import convert_to_dict_messages, convert_to_chat_completion_messages
from app.core.config import settings
from app.services.base_llm_handler import BaseLLMHandler

logger = logging.getLogger(__name__)

# Таймаут загрузки модели (сек). Большие модели на CPU при нехватке RAM могут "зависать" навсегда.
# 30B Q8 на CPU без GPU требует ~32GB RAM; при свопе процесс выглядит зависшим.
MODEL_LOAD_TIMEOUT = int(os.environ.get("LLM_MODEL_LOAD_TIMEOUT", "600"))


class LlamaHandler(BaseLLMHandler):
    _instance = None

    def __init__(self):
        self.model: Optional[Llama] = None
        self.model_path = settings.model.path
        self.model_name = settings.model.name
        self.n_ctx = settings.model.ctx_size
        self.n_gpu_layers = settings.model.gpu_layers
        self.verbose = settings.model.verbose
        self.is_initialized = False

    @classmethod
    def get_instance(cls):
        """Получение экземпляра синглтона."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """Асинхронная инициализация модели."""
        if self.is_initialized:
            return

        try:
            print("=" * 80)
            print("🚀 INITIALIZING LLAMA.CPP BACKEND")
            print("=" * 80)
            print(f"📁 Model path: {self.model_path}")
            print(f"📝 Model name: {self.model_name}")
            print(f"💾 Context size: {self.n_ctx} tokens")
            print(f"🎮 GPU layers: {self.n_gpu_layers}")
            print(f"🔊 Verbose: {self.verbose}")
            print("-" * 80)
            print("⏳ Loading model...")
            logger.info(f"Loading model from {self.model_path} (timeout={MODEL_LOAD_TIMEOUT}s)")

            loop = asyncio.get_event_loop()
            load_task = loop.run_in_executor(
                None,
                lambda: Llama(
                    model_path=self.model_path,
                    n_threads=7,
                    n_threads_batch=7,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=True,  # при загрузке всегда verbose — видно прогресс или зависание
                )
            )
            try:
                self.model = await asyncio.wait_for(load_task, timeout=MODEL_LOAD_TIMEOUT)
            except asyncio.TimeoutError:
                load_task.cancel()
                msg = (
                    f"Загрузка модели не завершилась за {MODEL_LOAD_TIMEOUT} с. "
                    "Чаще всего это нехватка RAM: модель 30B Q8 требует ~32 ГБ. "
                    "Проверьте: docker stats (память контейнера), включите GPU (gpu_layers: -1 в конфиге), "
                    "или используйте модель меньше (например 7B–8B). Таймаут задаётся переменной LLM_MODEL_LOAD_TIMEOUT."
                )
                logger.error(msg)
                print("❌ " + msg)
                raise RuntimeError(msg)

            self.is_initialized = True
            print("✅ llama.cpp model loaded successfully!")
            print("=" * 80)
            logger.info("Model loaded successfully")
        except Exception as e:
            print("❌ Failed to load llama.cpp model!")
            print(f"   Error: {str(e)}")
            print("=" * 80)
            logger.error(f"Failed to load model: {str(e)}")
            raise

    async def _run_in_executor(self, func: Callable):
        """Утилита для запуска блокирующих операций в executor'е."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func)

    def is_loaded(self) -> bool:
        """Проверка, загружена ли модель."""
        return self.is_initialized and self.model is not None

    async def _try_create_completion(self, messages: List[Message],
                                     temperature: float, max_tokens: int,
                                     stream: bool) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
        """Попытка создания завершения чата с обработкой разных форматов сообщений."""

        # Создаем функцию для создания completion
        def create_completion(messages_formatter: Callable):
            formatted_messages = messages_formatter(messages)
            return self.model.create_chat_completion(
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

        try:
            # Пробуем использовать формат словарей
            return await self._run_in_executor(lambda: create_completion(convert_to_dict_messages))
        except TypeError as e:
            if "Expected type" in str(e) and "got 'list[dict" in str(e):
                # Если возникает ошибка типа, пробуем использовать правильные типы сообщений
                logger.info("Falling back to typed messages for chat completion")
                return await self._run_in_executor(lambda: create_completion(convert_to_chat_completion_messages))
            else:
                raise e

    async def generate_response(self, messages: List[Message],
                                temperature: Optional[float] = None,
                                max_tokens: Optional[int] = None,
                                stream: bool = False) -> Union[ChatResponse, AsyncGenerator[str, None]]:
        """Универсальный метод для генерации ответа, поддерживающий оба режима."""
        if not self.is_loaded():
            raise ValueError("Model not loaded")

        # Используем значения по умолчанию из конфига, если не указаны
        temperature = temperature or settings.generation.default_temperature
        max_tokens = max_tokens or settings.generation.default_max_tokens

        start_time = time.time()

        if stream:
            # Потоковый режим - возвращаем асинхронный генератор
            stream_result = await self._try_create_completion(
                messages, temperature, max_tokens, stream=True
            )

            async def stream_generator():
                try:
                    # Асинхронно итерируемся по потоку
                    while True:
                        # Получаем следующий chunk из потока
                        chunk = await self._run_in_executor(lambda: next(stream_result, None))
                        if chunk is None:
                            break

                        # Форматируем chunk в строку SSE
                        yield f"data: {json.dumps(chunk)}\n\n"
                except StopIteration:
                    pass
                finally:
                    # Завершаем поток
                    yield "data: [DONE]\n\n"

            processing_time = time.time() - start_time
            logger.info(f"Stream response generated in {processing_time:.2f}s")
            return stream_generator()
        else:
            # Обычный режим - возвращаем готовый ответ
            response = await self._try_create_completion(
                messages, temperature, max_tokens, stream=False
            )

            processing_time = time.time() - start_time
            logger.info(f"Response generated in {processing_time:.2f}s")

            return self._format_response(response)

    def _format_response(self, raw_response: Dict[str, Any]) -> ChatResponse:
        """Форматирование ответа в совместимый с OpenAI формат."""
        choice = raw_response["choices"][0]
        message = choice["message"]

        return ChatResponse(
            id=f"chatcmpl-{int(time.time())}",
            created=int(time.time()),
            model=self.model_name,
            choices=[
                ChatChoice(
                    index=0,
                    message=AssistantMessage(content=message.get("content") or ""),
                    finish_reason=choice.get("finish_reason", "stop")
                )
            ],
            usage=UsageInfo(
                prompt_tokens=raw_response.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=raw_response.get("usage", {}).get("completion_tokens", 0),
                total_tokens=raw_response.get("usage", {}).get("total_tokens", 0)
            )
        )

    async def cleanup(self):
        """Очистка ресурсов модели."""
        if self.model:
            del self.model
        self.model = None
        self.is_initialized = False
        logger.info("Model resources cleaned up")

    async def load_model_by_name(self, model_name: str) -> bool:
        """
        Переключение на другую модель по имени (имя файла без .gguf).
        Путь к файлу: /app/models/llm/{model_name}.gguf
        """
        # Санитизация: только базовое имя, без пути и без .gguf
        model_name = os.path.basename(model_name).strip()
        if model_name.lower().endswith(".gguf"):
            model_name = model_name[:-5]
        if not model_name:
            logger.error("load_model_by_name: пустое имя модели")
            return False
        models_dir = "/app/models/llm"
        model_path = os.path.join(models_dir, f"{model_name}.gguf")
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False
        if self.model_name == model_name and self.is_loaded():
            logger.info(f"Model {model_name} already loaded")
            return True
        try:
            await self.cleanup()
            self.model_path = model_path
            self.model_name = model_name
            await self.initialize()
            logger.info(f"Switched to model: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            # Восстанавливаем предыдущую модель из конфига, чтобы сервис не оставался в 503
            try:
                self.model_path = settings.model.path
                self.model_name = settings.model.name
                await self.initialize()
                logger.info(f"Restored default model: {self.model_name}")
            except Exception as restore_e:
                logger.error(f"Failed to restore default model: {restore_e}")
            return False

