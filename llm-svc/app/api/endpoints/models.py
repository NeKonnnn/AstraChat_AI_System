import logging
from fastapi import APIRouter, Depends
from app.models.schemas import ModelsListResponse
from app.services.llama_handler import LlamaHandler
from app.api.dependencies import get_llama_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    llama_service: LlamaHandler = Depends(get_llama_service),
):
    """Список доступных моделей."""
    logger.info("Models list requested")
    return ModelsListResponse(
        data=[
            {
                "id": llama_service.model_name,
                "object": "model",
                "owned_by": "local",
                "permissions": []
            }
        ]
    )