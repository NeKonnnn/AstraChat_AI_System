import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends
from app.models.schemas import ModelsListResponse
from app.services.llama_handler import LlamaHandler
from app.api.dependencies import get_llama_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/models", response_model=ModelsListResponse)
async def list_models(
    llama_service: LlamaHandler = Depends(get_llama_service),
):
    """Список доступных моделей."""
    logger.info("Models list requested")
    
    # Сканируем директорию с моделями
    models_dir = "/app/models/llm"
    models_list = []
    
    # Если директория существует, сканируем .gguf файлы
    if os.path.exists(models_dir):
        try:
            for file in os.listdir(models_dir):
                if file.endswith('.gguf'):
                    file_path = os.path.join(models_dir, file)
                    file_size = os.path.getsize(file_path)
                    # Извлекаем имя модели из имени файла (без расширения)
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
    
    # Если модели не найдены, но есть загруженная модель, добавляем её
    if not models_list and llama_service.model_name:
        models_list.append({
            "id": llama_service.model_name,
            "object": "model",
            "owned_by": "local",
            "permissions": []
        })
    
    return ModelsListResponse(data=models_list)