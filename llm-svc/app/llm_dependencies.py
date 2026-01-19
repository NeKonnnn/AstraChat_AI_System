from app.services.llama_handler import LlamaHandler
from app.services.base_llm_handler import BaseLLMHandler
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Глобальный экземпляр обработчика LLM
_llm_handler = None

async def get_llm_handler() -> BaseLLMHandler:
    """Получение глобального экземпляра обработчика LLM на основе конфигурации."""
    global _llm_handler
    if _llm_handler is None:
        backend = settings.model.backend.lower()
        
        print("=" * 80)
        print("🔧 LLM BACKEND SELECTION")
        print("=" * 80)
        print(f"📋 Configured backend: {settings.model.backend}")
        
        if backend == "vllm":
            try:
                from app.services.vllm_handler import VLLMHandler
                print("✅ Selected backend: vLLM")
                print("   - High performance inference engine")
                print("   - Optimized for GPU acceleration")
                print("   - Supports continuous batching")
                _llm_handler = VLLMHandler.get_instance()
            except ImportError as e:
                print("❌ vLLM import failed, falling back to llama.cpp")
                print(f"   Error: {str(e)}")
                logger.error(f"Failed to import VLLMHandler: {str(e)}")
                logger.warning("Falling back to llama.cpp backend")
                print("✅ Selected backend: llama.cpp (fallback)")
                _llm_handler = LlamaHandler.get_instance()
        elif backend == "llama.cpp" or backend == "llamacpp":
            print("✅ Selected backend: llama.cpp")
            print("   - GGUF model format support")
            print("   - CPU and GPU support")
            print("   - Memory efficient quantization")
            _llm_handler = LlamaHandler.get_instance()
        else:
            # По умолчанию используем llama.cpp
            print(f"⚠️  Unknown backend '{backend}', falling back to llama.cpp")
            print("✅ Selected backend: llama.cpp (default)")
            logger.warning(f"Unknown backend '{backend}', falling back to llama.cpp")
            _llm_handler = LlamaHandler.get_instance()
        
        print("=" * 80)
        
        try:
            await _llm_handler.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize LLM handler: {str(e)}")
            # Если vLLM не удалось инициализировать, пробуем llama.cpp
            if backend == "vllm" and not isinstance(_llm_handler, LlamaHandler):
                print("=" * 80)
                print("❌ vLLM initialization failed, falling back to llama.cpp")
                print(f"   Error: {str(e)}")
                print("=" * 80)
                logger.warning("vLLM initialization failed, falling back to llama.cpp")
                _llm_handler = LlamaHandler.get_instance()
                await _llm_handler.initialize()
            else:
                raise
    return _llm_handler

# Обратная совместимость
async def get_llama_handler() -> BaseLLMHandler:
    """Получение глобального экземпляра обработчика LLM (обратная совместимость)."""
    return await get_llm_handler()

async def cleanup_llm_handler():
    """Очистка глобального экземпляра обработчика LLM."""
    global _llm_handler
    if _llm_handler is not None:
        await _llm_handler.cleanup()
        _llm_handler = None

# Обратная совместимость
async def cleanup_llama_handler():
    """Очистка глобального экземпляра обработчика LLM (обратная совместимость)."""
    await cleanup_llm_handler()