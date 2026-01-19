from typing import List, Dict, Any, Optional, AsyncGenerator, Union
import json
import asyncio
import time
import logging

try:
    from vllm import LLM, SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    LLM = None
    SamplingParams = None
    AsyncEngineArgs = None
    AsyncLLMEngine = None
    logging.warning("vLLM is not available. Install it with: pip install vllm")

from app.models.schemas import ChatResponse, ChatChoice, Message, UsageInfo
from app.services.base_llm_handler import BaseLLMHandler
from app.core.config import settings
from app.utils import convert_to_dict_messages

logger = logging.getLogger(__name__)


class VLLMHandler(BaseLLMHandler):
    """Handler для работы с vLLM."""
    
    _instance = None

    def __init__(self):
        super().__init__()
        if not VLLM_AVAILABLE:
            error_msg = "vLLM is not available. Please install it with: pip install vllm"
            logger.error(error_msg)
            raise ImportError(error_msg)
        
        self.engine: Optional[AsyncLLMEngine] = None
        self.model_path = settings.model.path
        self.model_name = settings.model.name
        self.max_model_len = settings.model.ctx_size
        self.tensor_parallel_size = getattr(settings.model, 'tensor_parallel_size', 1)
        self.gpu_memory_utilization = getattr(settings.model, 'gpu_memory_utilization', 0.9)
        self.trust_remote_code = getattr(settings.model, 'trust_remote_code', False)
        self.quantization = getattr(settings.model, 'quantization', None)

    @classmethod
    def get_instance(cls):
        """Получение экземпляра синглтона."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """Асинхронная инициализация модели vLLM."""
        if self.is_initialized:
            return

        if not VLLM_AVAILABLE:
            raise ImportError("vLLM is not available. Please install it with: pip install vllm")

        try:
            print("=" * 80)
            print("🚀 INITIALIZING VLLM BACKEND")
            print("=" * 80)
            print(f"📁 Model path: {self.model_path}")
            print(f"📝 Model name: {self.model_name}")
            print(f"💾 Max model length: {self.max_model_len} tokens")
            print(f"🔀 Tensor parallel size: {self.tensor_parallel_size} GPU(s)")
            print(f"💿 GPU memory utilization: {self.gpu_memory_utilization * 100:.0f}%")
            print(f"🔐 Trust remote code: {self.trust_remote_code}")
            if self.quantization:
                print(f"⚡ Quantization: {self.quantization}")
            print("-" * 80)
            print("⏳ Loading vLLM model (this may take a while)...")
            
            logger.info(f"Loading vLLM model from {self.model_path}")
            
            # Создаем аргументы для асинхронного движка
            # ВАЖНО: vLLM автоматически определяет устройство (CUDA), параметр device не нужен
            engine_args_dict = {
                "model": self.model_path,
                "max_model_len": self.max_model_len,
                "tensor_parallel_size": self.tensor_parallel_size,
                "gpu_memory_utilization": self.gpu_memory_utilization,
                "trust_remote_code": self.trust_remote_code,
            }
            
            # Добавляем параметр quantization, если указан
            if self.quantization:
                engine_args_dict["quantization"] = self.quantization
            
            engine_args = AsyncEngineArgs(**engine_args_dict)
            
            # Создаем асинхронный движок
            self.engine = AsyncLLMEngine.from_engine_args(engine_args)
            
            self.is_initialized = True
            print("✅ vLLM model loaded successfully!")
            print("=" * 80)
            logger.info("vLLM model loaded successfully")
        except Exception as e:
            print("❌ Failed to load vLLM model!")
            print(f"   Error: {str(e)}")
            print("=" * 80)
            logger.error(f"Failed to load vLLM model: {str(e)}")
            raise

    def is_loaded(self) -> bool:
        """Проверка, загружена ли модель."""
        return self.is_initialized and self.engine is not None

    def _format_messages_for_vllm(self, messages: List[Message]) -> str:
        """Форматирование сообщений для vLLM (конвертация в промпт).
        
        vLLM автоматически применяет chat template модели, если он доступен.
        Для моделей Qwen используем правильный формат с токенами <|im_start|> и <|im_end|>.
        Для других моделей используем универсальный формат.
        """
        # Конвертируем сообщения в словари для удобства
        msg_dicts = []
        for msg in messages:
            if isinstance(msg, Message):
                msg_dicts.append({"role": msg.role, "content": msg.content})
            else:
                msg_dicts.append(msg)
        
        # Проверяем, является ли модель Qwen (по имени модели или пути)
        is_qwen = "qwen" in self.model_name.lower() or "qwen" in self.model_path.lower()
        
        if is_qwen:
            # Формат для Qwen моделей
            formatted_parts = []
            for msg in msg_dicts:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Qwen использует специальные токены
                formatted_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
            
            # Добавляем начало ответа ассистента
            formatted_parts.append("<|im_start|>assistant\n")
            return "".join(formatted_parts)
        else:
            # Универсальный формат для других моделей
            # vLLM автоматически применит chat template, если он доступен
            formatted_parts = []
            for msg in msg_dicts:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    formatted_parts.append(f"System: {content}\n")
                elif role == "user":
                    formatted_parts.append(f"User: {content}\n")
                elif role == "assistant":
                    formatted_parts.append(f"Assistant: {content}\n")
            
            # Добавляем префикс для ответа ассистента
            formatted_parts.append("Assistant:")
            return "".join(formatted_parts)

    async def generate_response(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[ChatResponse, AsyncGenerator[str, None]]:
        """Универсальный метод для генерации ответа через vLLM."""
        if not self.is_loaded():
            raise ValueError("Model not loaded")

        # Используем значения по умолчанию из конфига, если не указаны
        temperature = temperature or settings.generation.default_temperature
        max_tokens = max_tokens or settings.generation.default_max_tokens

        # Форматируем сообщения в промпт
        prompt = self._format_messages_for_vllm(messages)

        # Создаем параметры сэмплирования
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
        )

        start_time = time.time()

        if stream:
            # Потоковый режим
            async def stream_generator():
                try:
                    import uuid
                    request_id = str(uuid.uuid4())
                    prev_text = ""
                    
                    async for request_output in self.engine.generate(prompt, sampling_params, request_id):
                        # Получаем сгенерированный текст
                        for output in request_output.outputs:
                            current_text = output.text
                            # Вычисляем только новый текст (delta)
                            new_text = current_text[len(prev_text):]
                            prev_text = current_text
                            
                            if new_text:
                                # Форматируем chunk в формат OpenAI SSE
                                chunk = {
                                    "id": f"chatcmpl-{request_id}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": self.model_name,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {"content": new_text},
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                            
                            # Проверяем, завершена ли генерация
                            if output.finish_reason is not None:
                                # Финальный chunk
                                final_chunk = {
                                    "id": f"chatcmpl-{request_id}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": self.model_name,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": output.finish_reason
                                    }]
                                }
                                yield f"data: {json.dumps(final_chunk)}\n\n"
                except Exception as e:
                    logger.error(f"Error in stream generation: {str(e)}")
                    raise
                finally:
                    yield "data: [DONE]\n\n"

            processing_time = time.time() - start_time
            logger.info(f"Stream response generated in {processing_time:.2f}s")
            return stream_generator()
        else:
            # Обычный режим
            import uuid
            request_id = str(uuid.uuid4())
            final_output = None
            
            async for request_output in self.engine.generate(prompt, sampling_params, request_id):
                final_output = request_output
            
            if final_output is None or not final_output.outputs:
                raise ValueError("No output generated")
            
            # Получаем полный текст ответа
            output = final_output.outputs[0]
            generated_text = output.text
            finish_reason = output.finish_reason or "stop"

            processing_time = time.time() - start_time
            logger.info(f"Response generated in {processing_time:.2f}s")

            # Получаем метрики использования токенов
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(final_output, 'metrics'):
                metrics = final_output.metrics
                prompt_tokens = getattr(metrics, 'num_prompt_tokens', 0)
                completion_tokens = getattr(metrics, 'num_generated_tokens', 0)

            # Форматируем ответ
            return ChatResponse(
                id=f"chatcmpl-{request_id}",
                created=int(time.time()),
                model=self.model_name,
                choices=[
                    ChatChoice(
                        index=0,
                        message=Message(
                            role="assistant",
                            content=generated_text
                        ),
                        finish_reason=finish_reason
                    )
                ],
                usage=UsageInfo(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
            )

    async def cleanup(self):
        """Очистка ресурсов модели."""
        if self.engine:
            # vLLM автоматически управляет ресурсами через AsyncLLMEngine
            # Можно добавить явную очистку, если необходимо
            pass
        self.engine = None
        self.is_initialized = False
        logger.info("vLLM model resources cleaned up")

