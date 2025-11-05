"""
Модуль подключения к MongoDB
"""

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ConfigurationError

logger = logging.getLogger(__name__)


class MongoDBConnection:
    """Класс для управления подключением к MongoDB"""
    
    def __init__(self, connection_string: str, database_name: str = "memoai"):
        """
        Инициализация подключения к MongoDB
        
        Args:
            connection_string: Строка подключения к MongoDB
            database_name: Имя базы данных
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Подключение к MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            
            # Проверка подключения
            await self.client.admin.command('ping')
            
            self.db = self.client[self.database_name]
            
            logger.info(f"Успешное подключение к MongoDB. База данных: {self.database_name}")
            return True
            
        except ConnectionFailure as e:
            logger.error(f"Ошибка подключения к MongoDB: {e}")
            return False
        except ConfigurationError as e:
            logger.error(f"Ошибка конфигурации MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при подключении к MongoDB: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Отключение от MongoDB")
    
    async def health_check(self) -> bool:
        """Проверка здоровья подключения"""
        try:
            if self.client:
                await self.client.admin.command('ping')
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке здоровья MongoDB: {e}")
            return False
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Получение объекта базы данных"""
        if not self.db:
            raise RuntimeError("База данных не подключена. Вызовите connect() сначала.")
        return self.db
    
    def get_collection(self, collection_name: str):
        """Получение коллекции"""
        return self.get_database()[collection_name]








