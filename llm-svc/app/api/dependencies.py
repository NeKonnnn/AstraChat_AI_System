from fastapi import Depends, HTTPException, status
from app.services.models_service import LlamaService
from app.dependencies import get_llama_service
from app.core.security import verify_api_key
import logging
logger = logging.getLogger(__name__)
async def get_llama_service_handler_non_connection_pool(
        llama_service: LlamaService = Depends(get_llama_service),
) -> LlamaService:
    """Зависимость для проверки доступности сервиса LLM."""
    if not llama_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is not loaded",
        )
    return llama_service
async def get_llama_service_handler(
        llama_service: LlamaService = Depends(get_llama_service),
) -> LlamaService:
    """Зависимость для проверки доступности сервиса LLM."""
    if not llama_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM model is not loaded",
        )
    # Проверяем, есть ли свободные инстансы для обработки запроса
    pool = llama_service.model_pool
    if pool.available_count <= 0:
        # Если все контексты заняты - 503; если активных 0, но нет свободных - ждём переинициализации
        if pool.active_requests_count >= pool.max_concurrent_requests:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service is busy. Maximum concurrent requests: {pool.max_concurrent_requests}, "
                       f"Current active requests: {pool.active_requests_count}, "
                       f"Total instances: {pool.total_count}"
            )
        if pool.active_requests_count == 0 and pool.total_count > 0:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service is reinitializing. Please retry in a few seconds."
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No model instances available."
        )
    # Дополнительная проверка: если сервис почти перегружен, предупреждаем
    if llama_service.model_pool.active_requests_count >= llama_service.model_pool.max_concurrent_requests:
        logger.warning(
            f"Service near capacity: {llama_service.model_pool.active_requests_count}/"
            f"{llama_service.model_pool.max_concurrent_requests} active requests"
        )
    return llama_service
async def require_api_key_handler(
    api_key_verified: bool = Depends(verify_api_key)
) -> bool:
    """Зависимость для проверки API ключа."""
    if not api_key_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return True
