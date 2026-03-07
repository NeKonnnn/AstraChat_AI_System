from fastapi import Depends, HTTPException, status
from app.services.base_llm_handler import BaseLLMHandler
from app.llm_dependencies import get_llm_handler
from app.core.security import verify_api_key

async def get_llama_service(
    llm_handler: BaseLLMHandler = Depends(get_llm_handler),
) -> BaseLLMHandler:
    """Зависимость для получения сервиса LLM."""
    if not llm_handler.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is not loaded",
        )
    return llm_handler


async def require_api_key(api_key_verified: bool = Depends(verify_api_key)):
    """Зависимость для проверки API ключа."""
    return api_key_verified