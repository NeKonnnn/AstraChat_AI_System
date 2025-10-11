from fastapi import Depends, HTTPException, status
from app.services.llama_handler import LlamaHandler
from app.dependencies import get_llama_handler
from app.core.security import verify_api_key

async def get_llama_service(
    llama_handler: LlamaHandler = Depends(get_llama_handler),
) -> LlamaHandler:
    """Зависимость для получения сервиса LLM."""
    if not llama_handler.is_loaded():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is not loaded",
        )
    return llama_handler


async def require_api_key(api_key_verified: bool = Depends(verify_api_key)):
    """Зависимость для проверки API ключа."""
    return api_key_verified