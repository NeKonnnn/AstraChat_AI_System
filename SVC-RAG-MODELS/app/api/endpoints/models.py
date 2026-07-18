"""Каталог и переключение локальных моделей эмбеддингов / реранкера."""

import os
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.dependencies.rag_models_handler import (
    cleanup_rag_models_handler,
    get_last_rag_models_error,
    get_rag_models_handler,
)
from app.services.models_catalog import (
    config_value_for_path,
    current_model_paths,
    list_models,
    parse_model_path,
)

router = APIRouter()


class RagModelSelectRequest(BaseModel):
    model_type: Literal["embedding", "reranker"] = Field(
        ..., description="Тип модели"
    )
    model_path: str = Field(
        ..., description="Путь вида local/<имя_папки> в RAG_MODELS_DIR"
    )


@router.get("/models")
async def get_models(type: Optional[str] = None):
    kind = None
    if type is not None:
        t = str(type).strip().lower()
        if t not in ("embedding", "reranker"):
            raise HTTPException(
                status_code=400, detail="type должен быть embedding или reranker"
            )
        kind = t  # type: ignore[assignment]
    models = list_models(kind)  # type: ignore[arg-type]
    return {
        "models": models,
        "current": current_model_paths(),
        "offline": True,  # только локальные веса
        "models_dir": settings.rag_models.models_dir,
    }


@router.get("/models/current")
async def get_current_models():
    handler = await get_rag_models_handler()
    current = current_model_paths()
    return {
        "current": current,
        "loaded": handler is not None,
        "offline": True,
        "embedding_dim": (handler or {}).get("embedding_dim"),
    }


@router.post("/models/select")
async def select_model(body: RagModelSelectRequest):
    if not settings.rag_models.enabled:
        raise HTTPException(status_code=503, detail="RAG-модели выключены в конфиге")

    try:
        source, _ = parse_model_path(body.model_path)
        config_value = config_value_for_path(body.model_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if source != "local":
        raise HTTPException(
            status_code=400,
            detail="Допускаются только локальные модели: local/<папка>",
        )

    models_dir = settings.rag_models.models_dir
    local_full = os.path.join(os.path.abspath(models_dir), config_value)
    if not os.path.isdir(local_full):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Папка модели не найдена: {local_full}. "
                f"Положите веса в {models_dir}/{config_value} "
                f"(имя из ConfigMap RAG_*_MODEL*)."
            ),
        )

    await cleanup_rag_models_handler()

    if body.model_type == "embedding":
        settings.rag_models.embedding_model = config_value
    else:
        settings.rag_models.reranker_model = config_value

    handler = await get_rag_models_handler()
    if handler is None:
        err = get_last_rag_models_error() or "Не удалось загрузить модель"
        raise HTTPException(status_code=502, detail=err)

    current = current_model_paths()
    return {
        "success": True,
        "message": "Модель загружена",
        "model_type": body.model_type,
        "model_path": body.model_path,
        "current": current,
        "embedding_dim": handler.get("embedding_dim"),
    }
