from app.services.llama_handler import LlamaHandler

# Глобальный экземпляр обработчика LLM
_llama_handler = None

async def get_llama_handler() -> LlamaHandler:
    """Получение глобального экземпляра обработчика LLM."""
    global _llama_handler
    if _llama_handler is None:
        _llama_handler = LlamaHandler.get_instance()
        await _llama_handler.initialize()
    return _llama_handler

async def cleanup_llama_handler():
    """Очистка глобального экземпляра обработчика LLM."""
    global _llama_handler
    if _llama_handler is not None:
        await _llama_handler.cleanup()
        _llama_handler = None