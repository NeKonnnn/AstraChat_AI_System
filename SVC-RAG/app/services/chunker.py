# Разбиение текста на чанки для RAG
import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def split_into_chunks(text: str) -> List[str]:
    """Разбивает текст на чанки. Размер и перекрытие из конфига."""
    if not text or not text.strip():
        return []
    cfg = get_settings().rag
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text.strip())
