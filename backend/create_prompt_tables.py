"""
Скрипт для создания таблиц галереи промптов в PostgreSQL
Запустите этот скрипт, если таблицы не создались автоматически
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.postgresql.connection import PostgreSQLConnection
from backend.database.postgresql.prompt_repository import PromptRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_tables():
    """Создание всех таблиц для галереи промптов"""
    
    # Получаем параметры подключения из переменных окружения
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    database = os.getenv("POSTGRES_DB", "memoai")
    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    
    logger.info("=" * 60)
    logger.info("СОЗДАНИЕ ТАБЛИЦ ГАЛЕРЕИ ПРОМПТОВ")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Database: {database}")
    logger.info(f"User: {user}")
    logger.info("=" * 60)
    
    try:
        # Создаем подключение
        connection = PostgreSQLConnection(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        logger.info("Подключение к PostgreSQL...")
        if not await connection.connect():
            logger.error("Не удалось подключиться к PostgreSQL!")
            logger.error("Проверьте:")
            logger.error("  1. PostgreSQL запущен")
            logger.error("  2. База данных 'memoai' существует")
            logger.error("  3. Параметры подключения в .env правильные")
            return False
        
        logger.info("Подключение установлено")
        
        # Создаем репозиторий и таблицы
        prompt_repo = PromptRepository(connection)
        
        logger.info("Создание таблиц...")
        await prompt_repo.create_tables()
        
        logger.info("=" * 60)
        logger.info("ВСЕ ТАБЛИЦЫ УСПЕШНО СОЗДАНЫ!")
        logger.info("=" * 60)
        logger.info("Созданные таблицы:")
        logger.info("  - prompts (промпты)")
        logger.info("  - tags (теги)")
        logger.info("  - prompt_tags (связь промптов и тегов)")
        logger.info("  - prompt_ratings (рейтинги промптов)")
        logger.info("  - prompt_bookmarks (закладки пользователей)")
        logger.info("=" * 60)
        
        # Закрываем подключение
        await connection.disconnect()
        
        return True
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ОШИБКА: {e}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())
        return False


# Функция add_initial_tags() удалена
# Теги теперь создаются только пользователями через интерфейс галереи промптов


async def main():
    """Главная функция"""
    
    logger.info("")
    logger.info("Скрипт создания таблиц галереи промптов")
    logger.info("")
    
    # Создаем таблицы
    if not await create_tables():
        logger.error("Не удалось создать таблицы")
        return 1
    
    logger.info("")
    logger.info("ГОТОВО! Теперь можно запускать backend.")
    logger.info("Примечание: Теги создаются пользователями через интерфейс галереи промптов.")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


