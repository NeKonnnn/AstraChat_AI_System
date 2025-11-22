"""
Скрипт для очистки некорректных тегов из базы данных.
Удаляет или переименовывает теги с именами короче 2 символов.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.postgresql.connection import PostgreSQLConnection
from backend.config import settings

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


async def cleanup_invalid_tags(action: str = "rename"):
    """
    Очистка некорректных тегов
    
    Args:
        action: "delete" - удалить теги, "rename" - переименовать (по умолчанию)
    """
    # Создаем подключение к PostgreSQL
    db_connection = PostgreSQLConnection(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD
    )
    
    try:
        await db_connection.connect()
        logger.info("✅ Подключено к PostgreSQL")
        
        async with db_connection.acquire() as conn:
            # Находим все теги с именами короче 2 символов
            invalid_tags = await conn.fetch("""
                SELECT id, name, 
                       (SELECT COUNT(*) FROM prompt_tags WHERE tag_id = tags.id) as usage_count
                FROM tags
                WHERE LENGTH(name) < 2
            """)
            
            if not invalid_tags:
                logger.info("✅ Некорректных тегов не найдено")
                return
            
            logger.info(f"Найдено некорректных тегов: {len(invalid_tags)}")
            
            for tag in invalid_tags:
                tag_id = tag['id']
                tag_name = tag['name']
                usage_count = tag['usage_count']
                
                if action == "delete":
                    # Удаляем тег
                    await conn.execute("DELETE FROM tags WHERE id = $1", tag_id)
                    logger.info(f"🗑️  Удален тег: ID={tag_id}, name='{tag_name}', использований={usage_count}")
                else:
                    # Переименовываем тег
                    new_name = f"tag-{tag_id}"
                    await conn.execute("""
                        UPDATE tags SET name = $1 WHERE id = $2
                    """, new_name, tag_id)
                    logger.info(f"✏️  Переименован тег: '{tag_name}' -> '{new_name}', использований={usage_count}")
            
            logger.info(f"✅ Обработано тегов: {len(invalid_tags)}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке тегов: {e}")
        raise
    finally:
        await db_connection.close()
        logger.info("Подключение к PostgreSQL закрыто")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Очистка некорректных тегов")
    parser.add_argument(
        "--action",
        choices=["delete", "rename"],
        default="rename",
        help="Действие: delete - удалить, rename - переименовать (по умолчанию)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Скрипт очистки некорректных тегов")
    logger.info("=" * 60)
    logger.info(f"Действие: {args.action}")
    
    if args.action == "delete":
        response = input("⚠️  Вы уверены, что хотите УДАЛИТЬ некорректные теги? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Отменено пользователем")
            return
    
    await cleanup_invalid_tags(args.action)
    
    logger.info("=" * 60)
    logger.info("✅ Готово!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

