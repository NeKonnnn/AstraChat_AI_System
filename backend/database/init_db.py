"""
Модуль инициализации подключений к базам данных
"""

import os
import logging
import traceback
from typing import Optional

# Импортируем настройки
try:
    from settings import get_settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Модуль settings недоступен. Используются переменные окружения напрямую.")

logger = logging.getLogger(__name__)

# Попытка импорта MongoDB модулей
try:
    # Проверяем наличие motor и pymongo
    try:
        import motor
        import pymongo
        # Получаем версии (не все модули имеют __version__)
        motor_version = getattr(motor, '__version__', getattr(motor, '_version', 'unknown'))
        pymongo_version = getattr(pymongo, '__version__', 'unknown')
        logger.info(f"motor ({motor_version}) и pymongo ({pymongo_version}) установлены")
    except ImportError as e:
        logger.error(f"motor или pymongo не установлены: {e}")
        logger.error("Установите: pip install motor pymongo")
        raise
    
    from .mongodb.connection import MongoDBConnection
    from .mongodb.repository import ConversationRepository
    mongodb_available = True
    logger.info("MongoDB модули импортированы успешно")
except ImportError as e:
    logger.error(f"MongoDB модули недоступны: {e}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    mongodb_available = False
    MongoDBConnection = None
    ConversationRepository = None

# Попытка импорта PostgreSQL модулей
try:
    from .postgresql.connection import PostgreSQLConnection
    from .postgresql.repository import DocumentRepository, VectorRepository
    from .postgresql.prompt_repository import PromptRepository, TagRepository
    from .postgresql.agent_repository import AgentRepository
    postgresql_available = True
    logger.debug("PostgreSQL модули импортированы успешно")
except ImportError as e:
    logger.warning(f"PostgreSQL модули недоступны: {e}")
    postgresql_available = False
    PostgreSQLConnection = None
    DocumentRepository = None
    VectorRepository = None
    PromptRepository = None
    TagRepository = None
    AgentRepository = None

# Попытка импорта MinIO модулей
try:
    from .minio import get_minio_client
    minio_available = True
    logger.debug("MinIO модули импортированы успешно")
except ImportError as e:
    logger.warning(f"MinIO модули недоступны: {e}")
    minio_available = False

# Глобальные подключения
mongodb_connection: Optional[MongoDBConnection] = None
postgresql_connection: Optional[PostgreSQLConnection] = None

# Глобальные репозитории
conversation_repo: Optional[ConversationRepository] = None
document_repo: Optional[DocumentRepository] = None
vector_repo: Optional[VectorRepository] = None
prompt_repo: Optional[PromptRepository] = None
tag_repo: Optional[TagRepository] = None
agent_repo: Optional[AgentRepository] = None


def get_mongodb_connection_string() -> str:
    """Получение строки подключения к MongoDB из настроек"""
    if not SETTINGS_AVAILABLE:
        raise RuntimeError("Модуль settings недоступен. Убедитесь, что настройки правильно настроены.")
    
    settings = get_settings()
    return settings.mongodb.connection_string


async def init_mongodb() -> bool:
    """Инициализация подключения к MongoDB"""
    global mongodb_connection, conversation_repo
    
    if not mongodb_available:
        logger.warning("MongoDB модули недоступны. Пропускаем инициализацию.")
        return False
    
    if not SETTINGS_AVAILABLE:
        logger.error("Модуль settings недоступен. MongoDB не может быть инициализирован.")
        return False
    
    try:
        # Получаем настройки из settings
        settings = get_settings()
        connection_string = settings.mongodb.connection_string
        database_name = settings.mongodb.database
        
        logger.info(f"Инициализация MongoDB...")
        logger.info(f"  Строка подключения: {connection_string.replace(connection_string.split('@')[-1] if '@' in connection_string else connection_string, '***') if '@' in connection_string else connection_string}")
        logger.info(f"  База данных: {database_name}")
        
        mongodb_connection = MongoDBConnection(connection_string, database_name)
        
        logger.info("Попытка подключения к MongoDB...")
        if await mongodb_connection.connect():
            # Создаем репозиторий
            logger.info("Создание репозитория диалогов...")
            conversation_repo = ConversationRepository(mongodb_connection)
            
            # Создаем индексы
            logger.info("Создание индексов...")
            await conversation_repo.create_indexes()
            
            logger.info("MongoDB успешно инициализирован")
            return True
        else:
            logger.error("Не удалось подключиться к MongoDB")
            logger.error("  Проверьте, что MongoDB запущен и доступен по указанному адресу")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации MongoDB: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


async def init_postgresql() -> bool:
    """Инициализация подключения к PostgreSQL"""
    global postgresql_connection, document_repo, vector_repo, prompt_repo, tag_repo, agent_repo
    
    if not postgresql_available:
        logger.warning("PostgreSQL модули недоступны. Пропускаем инициализацию.")
        return False
    
    if not SETTINGS_AVAILABLE:
        logger.error("Модуль settings недоступен. PostgreSQL не может быть инициализирован.")
        return False
    
    try:
        # Получаем настройки из settings
        settings = get_settings()
        pg_config = settings.postgresql
        postgresql_connection = PostgreSQLConnection(
            host=pg_config.host,
            port=pg_config.port,
            database=pg_config.database,
            user=pg_config.user,
            password=pg_config.password
        )
        embedding_dim = pg_config.embedding_dim
        
        if await postgresql_connection.connect():
            # Создаем репозитории
            document_repo = DocumentRepository(postgresql_connection)
            vector_repo = VectorRepository(postgresql_connection, embedding_dim)
            prompt_repo = PromptRepository(postgresql_connection)
            tag_repo = TagRepository(postgresql_connection)
            agent_repo = AgentRepository(postgresql_connection)
            
            # Создаем таблицы
            await document_repo.create_tables()
            await vector_repo.create_tables()
            await prompt_repo.create_tables()
            await agent_repo.create_tables()
            
            logger.info("PostgreSQL успешно инициализирован")
            return True
        else:
            logger.error("Не удалось подключиться к PostgreSQL")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при инициализации PostgreSQL: {e}")
        return False


def init_minio() -> bool:
    """Инициализация подключения к MinIO"""
    if not minio_available:
        logger.warning("MinIO модули недоступны. Пропускаем инициализацию.")
        return False
    
    try:
        logger.info("Инициализация MinIO...")
        minio_client = get_minio_client()
        if minio_client:
            endpoint = minio_client.endpoint
            bucket_temp = minio_client.bucket_name
            logger.info(f"Endpoint: {endpoint}")
            logger.info(f"Bucket (temp): {bucket_temp}")
            logger.info("MinIO успешно инициализирован")
            return True
        else:
            logger.warning("MinIO клиент недоступен")
            logger.warning("  Будет использоваться локальное хранение файлов")
            return False
    except Exception as e:
        logger.error(f"Ошибка при инициализации MinIO: {e}")
        logger.warning("  Будет использоваться локальное хранение файлов")
        return False


async def init_databases() -> bool:
    """Инициализация всех подключений к базам данных"""
    logger.info("=" * 60)
    logger.info("ИНИЦИАЛИЗАЦИЯ БАЗ ДАННЫХ")
    logger.info("=" * 60)
    
    mongodb_ok = await init_mongodb()
    postgresql_ok = await init_postgresql()
    minio_ok = init_minio()  # MinIO инициализация синхронная
    
    logger.info("=" * 60)
    if mongodb_ok and postgresql_ok and minio_ok:
        logger.info("Все базы данных успешно инициализированы")
        logger.info("=" * 60)
        return True
    else:
        logger.warning("Некоторые базы данных не инициализированы")
        if mongodb_ok:
            logger.info("MongoDB: готов")
        else:
            logger.warning("MongoDB: не инициализирован")
        if postgresql_ok:
            logger.info("PostgreSQL: готов")
        else:
            logger.warning("PostgreSQL: не инициализирован")
        if minio_ok:
            logger.info("MinIO: готов")
        else:
            logger.warning("MinIO: не инициализирован")
        logger.info("=" * 60)
        # Возвращаем True если хотя бы MongoDB инициализирован
        return mongodb_ok


async def close_databases():
    """Закрытие всех подключений к базам данных"""
    global mongodb_connection, postgresql_connection
    
    if mongodb_connection:
        await mongodb_connection.disconnect()
    
    if postgresql_connection:
        await postgresql_connection.disconnect()
    
    logger.info("Все подключения к базам данных закрыты")


def get_mongodb_connection():
    """Получение подключения к MongoDB"""
    global mongodb_connection
    if not mongodb_available:
        raise RuntimeError("MongoDB модули недоступны. Установите motor и pymongo.")
    if mongodb_connection is None:
        raise RuntimeError("MongoDB не инициализирован. Вызовите init_mongodb() сначала.")
    return mongodb_connection


def get_conversation_repository():
    """Получение репозитория диалогов"""
    if not mongodb_available:
        raise RuntimeError("MongoDB модули недоступны. Установите motor и pymongo.")
    if conversation_repo is None:
        raise RuntimeError("MongoDB не инициализирован. Вызовите init_mongodb() сначала.")
    return conversation_repo


def get_document_repository():
    """Получение репозитория документов"""
    if not postgresql_available:
        raise RuntimeError("PostgreSQL модули недоступны. Установите psycopg2.")
    if document_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return document_repo


def get_vector_repository():
    """Получение репозитория векторов"""
    if not postgresql_available:
        raise RuntimeError("PostgreSQL модули недоступны. Установите psycopg2.")
    if vector_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return vector_repo


def get_prompt_repository():
    """Получение репозитория промптов"""
    if not postgresql_available:
        raise RuntimeError("PostgreSQL модули недоступны. Установите psycopg2.")
    if prompt_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return prompt_repo


def get_tag_repository():
    """Получение репозитория тегов"""
    if not postgresql_available:
        raise RuntimeError("PostgreSQL модули недоступны. Установите psycopg2.")
    if tag_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return tag_repo


def get_agent_repository():
    """Получение репозитория агентов"""
    if not postgresql_available:
        raise RuntimeError("PostgreSQL модули недоступны. Установите psycopg2.")
    if agent_repo is None:
        raise RuntimeError("PostgreSQL не инициализирован. Вызовите init_postgresql() сначала.")
    return agent_repo














