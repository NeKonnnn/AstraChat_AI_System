"""
Модуль инициализации подключений к базам данных
"""

import os
import logging
from typing import Optional
from .mongodb.connection import MongoDBConnection
from .postgresql.connection import PostgreSQLConnection
from .mongodb.repository import ConversationRepository
from .postgresql.repository import DocumentRepository, VectorRepository

logger = logging.getLogger(__name__)

# Глобальные подключения
mongodb_connection: Optional[MongoDBConnection] = None
postgresql_connection: Optional[PostgreSQLConnection] = None

# Глобальные репозитории
conversation_repo: Optional[ConversationRepository] = None
document_repo: Optional[DocumentRepository] = None
vector_repo: Optional[VectorRepository] = None


def get_mongodb_connection_string() -> str:
    """Получение строки подключения к MongoDB из переменных окружения"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    user = os.getenv("MONGODB_USER", "admin")
    password = os.getenv("MONGODB_PASSWORD", "password")
    
    # Формируем строку подключения
    if user and password:
        return f"mongodb://{user}:{password}@{host}:{port}/"
    else:
        return f"mongodb://{host}:{port}/"


async def init_mongodb() -> bool:
    """Инициализация подключения к MongoDB"""
    global mongodb_connection, conversation_repo
    
    try:
        connection_string = get_mongodb_connection_string()
        database_name = os.getenv("MONGODB_DATABASE", "memoai")
        
        mongodb_connection = MongoDBConnection(connection_string, database_name)
        
        if await mongodb_connection.connect():
            # Создаем репозиторий
            conversation_repo = ConversationRepository(mongodb_connection)
            
            # Создаем индексы
            await conversation_repo.create_indexes()
            
            logger.info("MongoDB успешно инициализирован")
            return True
        else:
            logger.error("Не удалось подключиться к MongoDB")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации MongoDB: {e}")
        return False


async def init_postgresql() -> bool:
    """Инициализация подключения к PostgreSQL"""
    global postgresql_connection, document_repo, vector_repo
    
    try:
        postgresql_connection = PostgreSQLConnection(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "memoai"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD", "password")
        )
        
        if await postgresql_connection.connect():
            # Создаем репозитории
            document_repo = DocumentRepository(postgresql_connection)
            embedding_dim = int(os.getenv("EMBEDDING_DIM", "384"))  # Размерность векторов
            vector_repo = VectorRepository(postgresql_connection, embedding_dim)
            
            # Создаем таблицы
            await document_repo.create_tables()
            await vector_repo.create_tables()
            
            logger.info("PostgreSQL успешно инициализирован")
            return True
        else:
            logger.error("Не удалось подключиться к PostgreSQL")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации PostgreSQL: {e}")
        return False


async def init_databases() -> bool:
    """Инициализация всех подключений к базам данных"""
    mongodb_ok = await init_mongodb()
    postgresql_ok = await init_postgresql()
    
    if mongodb_ok and postgresql_ok:
        logger.info("Все базы данных успешно инициализированы")
        return True
    else:
        logger.warning("Некоторые базы данных не инициализированы")
        return False


async def close_databases():
    """Закрытие всех подключений к базам данных"""
    global mongodb_connection, postgresql_connection
    
    if mongodb_connection:
        await mongodb_connection.disconnect()
    
    if postgresql_connection:
        await postgresql_connection.disconnect()
    
    logger.info("Все подключения к базам данных закрыты")


def get_conversation_repository() -> ConversationRepository:
    """Получение репозитория диалогов"""
    if conversation_repo is None:
        raise RuntimeError("MongoDB не инициализирован. Вызовите init_mongodb() сначала.")
    return conversation_repo


def get_document_repository() -> DocumentRepository:
    """Получение репозитория документов"""
    if document_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return document_repo


def get_vector_repository() -> VectorRepository:
    """Получение репозитория векторов"""
    if vector_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return vector_repo








