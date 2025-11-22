"""
PostgreSQL + pgvector модуль для RAG системы и галереи промптов
"""

from .connection import PostgreSQLConnection
from .models import Document, DocumentVector
from .repository import DocumentRepository, VectorRepository
from .prompt_models import (
    Prompt, Tag, PromptWithTags, PromptRating,
    PromptCreate, PromptUpdate, PromptFilters, TagCreate, PromptStats
)
from .prompt_repository import PromptRepository, TagRepository

__all__ = [
    "PostgreSQLConnection",
    "Document",
    "DocumentVector",
    "DocumentRepository",
    "VectorRepository",
    # Prompt gallery
    "Prompt",
    "Tag",
    "PromptWithTags",
    "PromptRating",
    "PromptCreate",
    "PromptUpdate",
    "PromptFilters",
    "TagCreate",
    "PromptStats",
    "PromptRepository",
    "TagRepository",
]



























