"""
Модуль для работы с базами данных
- MongoDB для хранения диалогов
- PostgreSQL + pgvector для RAG системы
"""

# Опциональный импорт MongoDB модулей
try:
    from .mongodb.connection import MongoDBConnection
    from .mongodb.models import Conversation, Message
    mongodb_available = True
except ImportError:
    MongoDBConnection = None
    Conversation = None
    Message = None
    mongodb_available = False

# Опциональный импорт PostgreSQL модулей
try:
    from .postgresql.connection import PostgreSQLConnection
    from .postgresql.models import Document, DocumentVector
    postgresql_available = True
except ImportError:
    PostgreSQLConnection = None
    Document = None
    DocumentVector = None
    postgresql_available = False

__all__ = [
    "MongoDBConnection",
    "PostgreSQLConnection",
    "Conversation",
    "Message",
    "Document",
    "DocumentVector",
    "mongodb_available",
    "postgresql_available",
]














