"""
Модуль инициализации подключений к базам данных
"""

import os
import logging
import traceback
from typing import Optional

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


def get_mongodb_connection_string() -> str:
    """Получение строки подключения к MongoDB из переменных окружения"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    # Получаем пользователя и пароль, удаляем пробелы
    user = os.getenv("MONGODB_USER", "").strip()
    password = os.getenv("MONGODB_PASSWORD", "").strip()
    
    # Игнорируем значения, которые начинаются с '#' (это комментарии, попавшие в значения)
    if user.startswith('#'):
        logger.warning(f"MongoDB: MONGODB_USER начинается с '#', игнорируем (вероятно, комментарий попал в значение): '{user}'")
        user = ""
    if password.startswith('#'):
        logger.warning(f"MongoDB: MONGODB_PASSWORD начинается с '#', игнорируем (вероятно, комментарий попал в значение)")
        password = ""
    
    # Детальное логирование для отладки
    logger.debug(f"MongoDB: user='{user}' (len={len(user)}), password='{'*' * len(password) if password else ''}' (len={len(password)})")
    
    # Формируем строку подключения
    # Используем аутентификацию только если И пользователь И пароль указаны (не пустые)
    if user and password:
        logger.info(f"MongoDB: подключение с аутентификацией - пользователь: {user}")
        connection_string = f"mongodb://{user}:{password}@{host}:{port}/"
        logger.debug(f"MongoDB: строка подключения: mongodb://{user}:***@{host}:{port}/")
        return connection_string
    else:
        logger.info(f"MongoDB: подключение без аутентификации - {host}:{port}")
        connection_string = f"mongodb://{host}:{port}/"
        logger.debug(f"MongoDB: строка подключения: {connection_string}")
        return connection_string


async def init_mongodb() -> bool:
    """Инициализация подключения к MongoDB"""
    global mongodb_connection, conversation_repo
    
    if not mongodb_available:
        logger.warning("MongoDB модули недоступны. Пропускаем инициализацию.")
        return False
    
    try:
        connection_string = get_mongodb_connection_string()
        database_name = os.getenv("MONGODB_DATABASE", "memoai")
        
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
    global postgresql_connection, document_repo, vector_repo, prompt_repo, tag_repo
    
    if not postgresql_available:
        logger.warning("PostgreSQL модули недоступны. Пропускаем инициализацию.")
        return False
    
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
            prompt_repo = PromptRepository(postgresql_connection)
            tag_repo = TagRepository(postgresql_connection)
            
            # Создаем таблицы
            await document_repo.create_tables()
            await vector_repo.create_tables()
            await prompt_repo.create_tables()
            
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
            logger.info(f"  Endpoint: {endpoint}")
            logger.info(f"  Bucket (temp): {bucket_temp}")
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














