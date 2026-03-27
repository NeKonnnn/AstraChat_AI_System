from fastapi import Depends, HTTPException, status
from app.services.base_llm_handler import BaseLLMHandler
from app.llm_dependencies import get_llm_handler
from app.core.security import verify_api_key

async def get_llama_service(
    llm_handler: BaseLLMHandler = Depends(get_llm_handler),
) -> BaseLLMHandler:
    """Зависимость для получения сервиса LLM."""
    # Пока llama.cpp делает cleanup()+load, is_loaded() кратко False — без ожидания параллельные
    # /health и /chat/completions получали 503. Блокировка смены модели сериализует ожидание.
    lock = getattr(llm_handler, "_model_switch_lock", None)
    if lock is not None:
        async with lock:
            pass
    if not llm_handler.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is not loaded",
        )
    return llm_handler


async def get_llm_handler_without_loaded_gate(
    llm_handler: BaseLLMHandler = Depends(get_llm_handler),
) -> BaseLLMHandler:
    """
    Доступ к handler без требования is_loaded()
    Нужен для POST /v1/models/load (первая загрузка) и GET /v1/models (список .gguf с диска)
    Ожидание той же блокировки смены модели, что и у get_llama_service
    """
    lock = getattr(llm_handler, "_model_switch_lock", None)
    if lock is not None:
        async with lock:
            pass
    return llm_handler


async def require_api_key(api_key_verified: bool = Depends(verify_api_key)):
    """Зависимость для проверки API ключа."""
    return api_key_verified