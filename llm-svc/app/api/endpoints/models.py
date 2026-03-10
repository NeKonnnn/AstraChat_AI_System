import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import ModelsListResponse, ModelInfoResponse, ModelLoadRequest, ModelLoadResponse
from app.api.dependencies import get_llama_service
from app.services.models_service import LlamaService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    llama_service: LlamaService = Depends(get_llama_service),
):
    """Список доступных моделей. Не требует загруженной модели."""
    logger.info("Models list requested")
    models_dir = "/app/models/llm"
    models_list = []
    if os.path.exists(models_dir):
        try:
            for file in os.listdir(models_dir):
                if file.endswith('.gguf'):
                    file_path = os.path.join(models_dir, file)
                    file_size = os.path.getsize(file_path)
                    model_name = os.path.splitext(file)[0]
                    models_list.append({
                        "id": model_name,
                        "object": "model",
                        "owned_by": "local",
                        "permissions": [],
                        "path": file_path,
                        "size": file_size,
                        "size_mb": round(file_size / (1024 * 1024), 2)
                    })
            logger.info(f"Found {len(models_list)} models in {models_dir}")
        except Exception as e:
            logger.error(f"Error scanning models directory: {e}")
    if not models_list and llama_service.is_loaded and llama_service.model_name:
        models_list.append({
            "id": llama_service.model_name,
            "object": "model",
            "owned_by": "local",
            "permissions": []
        })
    return ModelsListResponse(data=models_list)

@router.get("/models/current", response_model=ModelInfoResponse)
async def get_current_model_info(
    llama_service: LlamaService = Depends(get_llama_service),
):
    """Получить детальную информацию о текущей загруженной модели."""
    logger.info("Current model info requested")
    model_path = llama_service.model_path
    file_exists = os.path.exists(model_path) if model_path else False
    file_size = os.path.getsize(model_path) if file_exists else None
    file_size_mb = round(file_size / (1024 * 1024), 2) if file_size else None
    return ModelInfoResponse(
        model_name=llama_service.model_name if llama_service.is_loaded else None,
        model_path=model_path,
        is_loaded=llama_service.is_loaded,
        context_size=llama_service.n_ctx if llama_service.is_loaded else None,
        gpu_layers=llama_service.n_gpu_layers if llama_service.is_loaded else None,
        file_size=file_size,
        file_size_mb=file_size_mb,
        file_exists=file_exists,
        config_name=settings.model.name
    )

@router.post("/models/load", response_model=ModelLoadResponse)
async def load_model(
    request: ModelLoadRequest,
    llama_service: LlamaService = Depends(get_llama_service),
):
    """Загрузить/переключить модель по имени (имя файла без .gguf) или по полному пути."""
    model_name = (request.model or "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="model name is required")
    try:
        success = await llama_service.load_model(model_name)
        if success:
            return ModelLoadResponse(
                success=True,
                message=f"Model '{llama_service.model_name}' loaded successfully",
                model_name=llama_service.model_name
            )
        return ModelLoadResponse(
            success=False,
            message=f"Failed to load model '{model_name}' (file not found or load error)"
        )
    except Exception as e:
        logger.exception(f"Error loading model {model_name}")
        raise HTTPException(status_code=500, detail=str(e))
