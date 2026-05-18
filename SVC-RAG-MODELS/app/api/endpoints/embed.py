import asyncio
import logging
from typing import List, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies.rag_models_handler import get_rag_models_handler
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class EmbedRequest(BaseModel):
    text: Union[str, None] = None
    texts: Union[List[str], None] = None

    def get_texts(self) -> List[str]:
        if self.texts:
            return self.texts
        if self.text is not None:
            return [self.text]
        return []


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    embedding_dim: int


def _encode_texts(model, texts: List[str], batch_size: int):
    return model.encode(
        texts,
        convert_to_numpy=True,
        batch_size=batch_size,
        show_progress_bar=len(texts) > batch_size,
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed_texts(request: EmbedRequest):
    if not settings.rag_models.enabled:
        raise HTTPException(status_code=503, detail="Сервис RAG-моделей выключен")
    texts = request.get_texts()
    if not texts:
        raise HTTPException(status_code=400, detail="Нужно передать text или texts в теле запроса")
    handler = await get_rag_models_handler()
    if handler is None:
        raise HTTPException(status_code=503, detail="Эмбеддинг-модель не загружена")

    model = handler["embedding_model"]
    batch_size = max(1, int(settings.rag_models.embed_batch_size))
    if len(texts) > 1:
        logger.info("Embed: %s текстов, batch_size=%s", len(texts), batch_size)

    embeddings = await asyncio.to_thread(_encode_texts, model, texts, batch_size)
    if hasattr(embeddings, "ndim") and embeddings.ndim == 1:
        embeddings = [embeddings.tolist()]
    else:
        embeddings = embeddings.tolist()
    dim = handler.get("embedding_dim", len(embeddings[0]) if embeddings else 384)
    return EmbedResponse(embeddings=embeddings, embedding_dim=int(dim))
