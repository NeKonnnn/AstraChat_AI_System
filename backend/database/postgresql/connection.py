"""
Модуль подключения к PostgreSQL с pgvector
"""

import logging
from typing import Optional
import asyncio
import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import ConnectionDoesNotExistError, PostgresError

logger = logging.getLogger(__name__)


class _ConnectionContextManager:
    """Обертка для context manager соединения"""
    def __init__(self, cm):
        self._cm = cm
    
    async def __aenter__(self):
        return await self._cm.__aenter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self._cm.__aexit__(exc_type, exc_val, exc_tb)


class PostgreSQLConnection:
    """Класс для управления подключением к PostgreSQL"""
    
    def __init__(
        self, 
        host: str = "localhost",
        port: int = 5432,
        database: str = "astrachat",
        user: str = "astrachat_user",
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
                        # Пытаемся установить расширение
                        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                        # Проверяем, что расширение установлено
                        check_result = await conn.fetchval(
                            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                        )
                        if check_result:
                            logger.info("Расширение pgvector успешно установлено")
                        else:
                            logger.error("Расширение pgvector не установлено после попытки создания")
                            logger.error("   Возможно, у пользователя нет прав на создание расширений")
                            logger.error("   Выполните вручную: CREATE EXTENSION vector;")
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Не удалось установить pgvector: {error_msg}")
                        if "permission denied" in error_msg.lower() or "права" in error_msg.lower():
                            logger.error("   У пользователя PostgreSQL нет прав на создание расширений")
                            logger.error("   Решение:")
                            logger.error("   1. Подключитесь к PostgreSQL как суперпользователь (postgres)")
                            logger.error("   2. Выполните: CREATE EXTENSION vector;")
                            logger.error("   3. Или дайте права пользователю: ALTER USER admin WITH SUPERUSER;")
                        elif "does not exist" in error_msg.lower() or "не существует" in error_msg.lower():
                            logger.error("   Расширение pgvector не найдено в PostgreSQL")
                            logger.error("   Убедитесь, что используется образ pgvector/pgvector:pg17 в docker-compose.yml")
                        else:
                            logger.error("   Для работы RAG системы необходимо установить pgvector")
            
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
    
    async def ensure_pool(self):
        """Обеспечивает, что пул создан в текущем event loop"""
        try:
            current_loop = asyncio.get_running_loop()
            
            # Если пул не создан или создан в другом loop, пересоздаем
            if not self.pool or (hasattr(self.pool, '_loop') and self.pool._loop is not current_loop):
                if self.pool:
                    logger.info("Пул соединений создан в другом event loop, пересоздаем в текущем...")
                    try:
                        await self.pool.close()
                    except:
                        pass
                
                # Создаем новый пул в текущем loop
                await self.connect()
        except RuntimeError:
            # Нет запущенного loop, используем существующий пул или создаем новый
            if not self.pool:
                await self.connect()
    
    async def acquire(self):
        """Получение соединения из пула (async context manager)"""
        # Убеждаемся, что пул создан в текущем event loop
        await self.ensure_pool()
        if not self.pool:
            raise RuntimeError("Пул соединений не создан. Вызовите connect() или ensure_pool() сначала.")
        return _ConnectionContextManager(self.pool.acquire())
    
    async def release(self, conn: Connection):
        """Освобождение соединения обратно в пул"""
        await self.pool.release(conn)
    
    async def execute(self, query: str, *args):
        """Выполнение запроса"""
        async with await self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Выполнение запроса с возвратом всех строк"""
        async with await self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Выполнение запроса с возвратом одной строки"""
        async with await self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Выполнение запроса с возвратом одного значения"""
        async with await self.acquire() as conn:
            return await conn.fetchval(query, *args)
