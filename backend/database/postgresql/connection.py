"""
Модуль подключения к PostgreSQL с pgvector
"""

import logging
from typing import Optional
import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import ConnectionDoesNotExistError, PostgresError

logger = logging.getLogger(__name__)


class PostgreSQLConnection:
    """Класс для управления подключением к PostgreSQL"""
    
    def __init__(
        self, 
        host: str = "localhost",
        port: int = 5432,
        database: str = "memoai",
        user: str = "memoai_user",
        password: str = "password"
    ):
        """
        Инициализация подключения к PostgreSQL
        
        Args:
            host: Хост PostgreSQL
            port: Порт PostgreSQL
            database: Имя базы данных
            user: Имя пользователя
            password: Пароль
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool: Optional[Pool] = None
    
    async def connect(self, min_size: int = 5, max_size: int = 20):
        """
        Подключение к PostgreSQL и создание пула соединений
        
        Args:
            min_size: Минимальный размер пула
            max_size: Максимальный размер пула
        """
        try:
            logger.info(f"Попытка подключения к PostgreSQL: {self.user}@{self.host}:{self.port}/{self.database}")
            
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=min_size,
                max_size=max_size
            )
            
            # Проверка подключения и pgvector расширения
            async with self.pool.acquire() as conn:
                await conn.execute("SELECT 1")
                # Проверяем наличие расширения pgvector
                result = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                )
                if not result:
                    logger.warning("Расширение pgvector не установлено. Пытаемся установить...")
                    try:
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                        logger.info("Расширение pgvector успешно установлено")
                    except Exception as e:
                        logger.error(f"Не удалось установить pgvector: {e}")
                        logger.error("Для работы RAG системы необходимо установить pgvector")
            
            logger.info(f"Успешное подключение к PostgreSQL. База данных: {self.database}")
            return True
            
        except asyncpg.exceptions.InvalidPasswordError:
            logger.error("ОШИБКА: Неверный пароль для пользователя PostgreSQL!")
            logger.error(f"Пользователь: {self.user}")
            logger.error("Проверьте POSTGRES_PASSWORD в .env файле")
            return False
            
        except asyncpg.exceptions.InvalidCatalogNameError:
            logger.error(f"ОШИБКА: База данных '{self.database}' не существует!")
            logger.error(f"Создайте базу данных:")
            logger.error(f"CREATE DATABASE {self.database};")
            logger.error("Или используйте скрипт test_postgres_connection.py для автоматического создания")
            return False
            
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.error(f"ОШИБКА: Пользователь '{self.user}' не существует или нет прав доступа!")
            logger.error(f"Создайте пользователя:")
            logger.error(f"CREATE USER {self.user} WITH PASSWORD '{self.password}';")
            logger.error(f"GRANT ALL PRIVILEGES ON DATABASE {self.database} TO {self.user};")
            return False
            
        except ConnectionRefusedError:
            logger.error(f"ОШИБКА: Не удалось подключиться к {self.host}:{self.port}")
            logger.error("Проверьте:")
            logger.error("1. PostgreSQL запущен")
            logger.error("2. Хост и порт правильные (для локальной БД используйте localhost, а не postgresql)")
            logger.error("3. Firewall не блокирует подключение")
            logger.error(f"4. В .env файле POSTGRES_HOST=localhost (не postgresql)")
            return False
            
        except OSError as e:
            if "No connection could be made" in str(e) or "не удается установить соединение" in str(e):
                logger.error(f"ОШИБКА: Не удалось установить соединение с {self.host}:{self.port}")
                logger.error("Проверьте:")
                logger.error("1. PostgreSQL запущен")
                logger.error("2. Хост и порт правильные")
                logger.error(f"3. В .env файле POSTGRES_HOST=localhost (не postgresql для локальной БД)")
            else:
                logger.error(f"ОШИБКА подключения: {e}")
            return False
            
        except Exception as e:
            error_type = type(e).__name__
            logger.error(f"ОШИБКА при подключении к PostgreSQL ({error_type}): {e}")
            logger.error(f"Параметры подключения:")
            logger.error(f"Host: {self.host}")
            logger.error(f"Port: {self.port}")
            logger.error(f"Database: {self.database}")
            logger.error(f"User: {self.user}")
            logger.error("Проверьте настройки в .env файле")
            return False
    
    async def disconnect(self):
        """Закрытие пула соединений"""
        if self.pool:
            await self.pool.close()
            logger.info("Отключение от PostgreSQL")
    
    async def health_check(self) -> bool:
        """Проверка здоровья подключения"""
        try:
            if self.pool:
                async with self.pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке здоровья PostgreSQL: {e}")
            return False
    
    def acquire(self):
        """Получение соединения из пула (контекстный менеджер)"""
        if not self.pool:
            raise RuntimeError("Пул соединений не создан. Вызовите connect() сначала.")
        return self.pool.acquire()
    
    async def release(self, conn: Connection):
        """Освобождение соединения обратно в пул"""
        await self.pool.release(conn)
    
    async def execute(self, query: str, *args):
        """Выполнение запроса"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Выполнение запроса с возвратом всех строк"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Выполнение запроса с возвратом одной строки"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Выполнение запроса с возвратом одного значения"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)




























