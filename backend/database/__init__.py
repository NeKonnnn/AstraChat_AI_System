"""
Модуль для работы с базами данных
- MongoDB для хранения диалогов
- PostgreSQL + pgvector для RAG системы
"""

from .mongodb.connection import MongoDBConnection
from .postgresql.connection import PostgreSQLConnection
from .mongodb.models import Conversation, Message
from .postgresql.models import Document, DocumentVector

__all__ = [
    "MongoDBConnection",
    "PostgreSQLConnection",
    "Conversation",
    "Message",
    "Document",
    "DocumentVector",
]








