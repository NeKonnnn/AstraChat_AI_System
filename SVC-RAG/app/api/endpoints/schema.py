"""Админ-эндпоинты схемы RAG (размерность векторов)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.dependencies import ensure_embedding_dim

router = APIRouter()

class EmbeddingDimRequest(BaseModel):
    embedding_dim: int = Field(
        ..., ge=1, le=8192, description="Размерность текущей embedding-модели"
    )

@router.post("/embedding-dim")
async def set_embedding_dim(body: EmbeddingDimRequest):
    """Привести колонки vector(*) к размерности выбранной модели.
    Старые векторы другой размерности очищаются - документы нужно переиндексировать.
    """
    try:
        result = await ensure_embedding_dim(body.embedding_dim)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Не удалось мигрировать schema: {e}"
        ) from e
    return {"success": True, **result}

class ModelsProviderRequest(BaseModel):
    model_type: Literal["embedding", "reranker"] = Field(..., description="Тип модели")
    provider: str = Field(
        ..., min_length=1, description="native или id из rag_models.providers"
    )
    model: Optional[str] = Field(
        None, description="id модели у провайдера (для native не нужен)"
    )

@router.post("/models-provider")
async def set_models_provider(body: ModelsProviderRequest):
    """Переключить источник моделей одного типа (native / Phoenix) на лету.

    НЕ мигрирует размерность БД: для внешнего эмбеддера возвращает
    embedding_dim (probe), решение о миграции - за backend
    """
    from app.dependencies import set_rag_models_provider

    try:
        result = await set_rag_models_provider(
            body.model_type, body.provider, body.model
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Не удалось переключить провайдера: {e}"
        ) from e
    return {"success": True, **result}