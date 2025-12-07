import logging
from fastapi import APIRouter, Depends
from app.models.schemas import HealthResponse
from app.services.llama_handler import LlamaHandler
from app.api.dependencies import get_llama_service


logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check(
    llama_service: LlamaHandler = Depends(get_llama_service),
):
    """Проверка статуса сервиса и загрузки модели."""
    logger.info("Health requested")
    model_name = llama_service.model_name if llama_service.is_loaded() else None
    if model_name:
        logger.info(f"Health check: Model '{model_name}' is {'loaded' if llama_service.is_loaded() else 'not loaded'}")
    return HealthResponse(
        status="healthy",
        model_loaded=llama_service.is_loaded(),
        model_name=model_name,
    )