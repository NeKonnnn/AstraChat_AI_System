import logging
from fastapi import APIRouter, Depends
from app.models.schemas import HealthResponse
from app.services.models_service import LlamaService
from app.api.dependencies import get_llama_service_handler_non_connection_pool
logger = logging.getLogger(__name__)
router = APIRouter()
@router.get("/health", response_model=HealthResponse)
async def health_check(
    llama_service: LlamaService = Depends(get_llama_service_handler_non_connection_pool)
):
    """Проверка статуса сервиса и загрузки модели."""
    logger.info("Health requested")
    return HealthResponse(
        status="healthy",
        model_loaded=llama_service.is_loaded,
        model_name=llama_service.model_name if llama_service.is_loaded else None,
    )
