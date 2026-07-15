"""Админ-эндпоинты схемы RAG (размерность векторов)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import ensure_embedding_dim

router = APIRouter()


class EmbeddingDimRequest(BaseModel):
    embedding_dim: int = Field(..., ge=1, le=8192, description="Размерность текущей embedding-модели")


@router.post("/embedding-dim")
async def set_embedding_dim(body: EmbeddingDimRequest):
    """Привести колонки vector(*) к размерности выбранной модели.

    Старые векторы другой размерности очищаются — документы нужно переиндексировать.
    """
    try:
        result = await ensure_embedding_dim(body.embedding_dim)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось мигрировать schema: {e}") from e
    return {"success": True, **result}
