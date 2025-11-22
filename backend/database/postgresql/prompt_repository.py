"""
Репозиторий для работы с промптами в PostgreSQL
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .prompt_models import (
    Prompt, Tag, PromptWithTags, PromptRating, 
    PromptCreate, PromptUpdate, PromptFilters, TagCreate, PromptStats
)
from .connection import PostgreSQLConnection

logger = logging.getLogger(__name__)


class PromptRepository:
    """Репозиторий для работы с промптами"""
    
    def __init__(self, db_connection: PostgreSQLConnection):
        """
        Инициализация репозитория
        
        Args:
            db_connection: Подключение к PostgreSQL
        """
        self.db_connection = db_connection
    
    async def create_tables(self):
        """Создание таблиц для промптов"""
        try:
            async with self.db_connection.acquire() as conn:
                # Таблица промптов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompts (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        content TEXT NOT NULL,
                        description TEXT,
                        author_id VARCHAR(100) NOT NULL,
                        author_name VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        is_public BOOLEAN DEFAULT true,
                        usage_count INTEGER DEFAULT 0,
                        views_count INTEGER DEFAULT 0
                    )
                """)
                
                # Таблица тегов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tags (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        description TEXT,
                        color VARCHAR(7),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Связь промптов и тегов (many-to-many)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_tags (
                        prompt_id INTEGER REFERENCES prompts(id) ON DELETE CASCADE,
                        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                        PRIMARY KEY (prompt_id, tag_id)
                    )
                """)
                
                # Таблица рейтингов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_ratings (
                        id SERIAL PRIMARY KEY,
                        prompt_id INTEGER REFERENCES prompts(id) ON DELETE CASCADE,
                        user_id VARCHAR(100) NOT NULL,
                        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(prompt_id, user_id)
                    )
                """)
                
                # Таблица закладок
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS prompt_bookmarks (
                        id SERIAL PRIMARY KEY,
                        prompt_id INTEGER REFERENCES prompts(id) ON DELETE CASCADE,
                        user_id VARCHAR(100) NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(prompt_id, user_id)
                    )
                """)
                
                # Индексы для производительности
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_author ON prompts(author_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_created ON prompts(created_at DESC)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_public ON prompts(is_public)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_tags_prompt ON prompt_tags(prompt_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_tags_tag ON prompt_tags(tag_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_prompt ON prompt_ratings(prompt_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_user ON prompt_ratings(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON prompt_bookmarks(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_prompt ON prompt_bookmarks(prompt_id)")
                
                logger.info("Таблицы для галереи промптов созданы")
                
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц промптов: {e}")
            raise
    
    async def create_prompt(self, prompt_data: PromptCreate, author_id: str, author_name: str) -> Optional[int]:
        """
        Создание нового промпта
        
        Args:
            prompt_data: Данные промпта
            author_id: ID автора
            author_name: Имя автора
            
        Returns:
            ID созданного промпта или None в случае ошибки
        """
        try:
            # Нормализуем author_id для консистентности
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with self.db_connection.acquire() as conn:
                # Создаём промпт
                result = await conn.fetchrow("""
                    INSERT INTO prompts (title, content, description, author_id, author_name, is_public)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, 
                    prompt_data.title,
                    prompt_data.content,
                    prompt_data.description,
                    author_id,
                    author_name,
                    prompt_data.is_public
                )
                
                prompt_id = result['id']
                
                # Создаём новые теги (если указаны)
                all_tag_ids = list(prompt_data.tag_ids) if prompt_data.tag_ids else []
                
                if prompt_data.new_tags:
                    for tag_name in prompt_data.new_tags:
                        tag_name = tag_name.strip()
                        # Валидация: минимум 2 символа
                        if not tag_name or len(tag_name) < 2:
                            logger.warning(f"Пропущен тег с некорректным именем (меньше 2 символов): '{tag_name}'")
                            continue
                        
                        # Проверяем, существует ли тег
                        existing_tag = await conn.fetchrow("""
                            SELECT id FROM tags WHERE LOWER(name) = LOWER($1)
                        """, tag_name)
                        
                        if existing_tag:
                            # Тег уже существует, используем его ID
                            all_tag_ids.append(existing_tag['id'])
                        else:
                            # Создаём новый тег
                            new_tag = await conn.fetchrow("""
                                INSERT INTO tags (name)
                                VALUES ($1)
                                RETURNING id
                            """, tag_name)
                            all_tag_ids.append(new_tag['id'])
                            logger.info(f"Создан новый тег: {tag_name}")
                
                # Добавляем все теги к промпту
                for tag_id in set(all_tag_ids):  # set() для удаления дубликатов
                    await conn.execute("""
                        INSERT INTO prompt_tags (prompt_id, tag_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                    """, prompt_id, tag_id)
                
                logger.info(f"Создан промпт: {prompt_data.title} (ID: {prompt_id})")
                return prompt_id
                
        except Exception as e:
            logger.error(f"Ошибка при создании промпта: {e}")
            return None
    
    async def get_prompt(self, prompt_id: int, user_id: Optional[str] = None) -> Optional[PromptWithTags]:
        """
        Получение промпта по ID с тегами и рейтингом
        
        Args:
            prompt_id: ID промпта
            user_id: ID пользователя (для получения его оценки)
            
        Returns:
            Промпт с тегами и рейтингом или None
        """
        try:
            async with self.db_connection.acquire() as conn:
                # Получаем промпт
                prompt_row = await conn.fetchrow("""
                    SELECT p.*, 
                           COALESCE(AVG(pr.rating), 0) as average_rating,
                           COUNT(pr.id) as total_votes
                    FROM prompts p
                    LEFT JOIN prompt_ratings pr ON p.id = pr.prompt_id
                    WHERE p.id = $1
                    GROUP BY p.id
                """, prompt_id)
                
                if not prompt_row:
                    return None
                
                # Получаем теги
                tag_rows = await conn.fetch("""
                    SELECT t.*
                    FROM tags t
                    JOIN prompt_tags pt ON t.id = pt.tag_id
                    WHERE pt.prompt_id = $1
                """, prompt_id)
                
                # Создаем теги с обработкой ошибок валидации
                tags = []
                for row in tag_rows:
                    try:
                        tag = Tag(**dict(row))
                        tags.append(tag)
                    except Exception as e:
                        logger.warning(f"Пропущен некорректный тег (ID: {row.get('id')}, name: {row.get('name')}): {e}")
                        continue
                
                # Получаем оценку пользователя
                user_rating = None
                is_bookmarked = False
                if user_id:
                    # Нормализуем user_id для поиска
                    normalized_user_id = user_id.strip().lower() if user_id else user_id
                    rating_row = await conn.fetchrow("""
                        SELECT rating FROM prompt_ratings
                        WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                    """, prompt_id, normalized_user_id)
                    if rating_row:
                        user_rating = rating_row['rating']
                    
                    # Проверяем, добавлен ли в закладки
                    bookmark_row = await conn.fetchrow("""
                        SELECT id FROM prompt_bookmarks
                        WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                    """, prompt_id, normalized_user_id)
                    is_bookmarked = bookmark_row is not None
                
                # Формируем объект
                prompt = PromptWithTags(
                    id=prompt_row['id'],
                    title=prompt_row['title'],
                    content=prompt_row['content'],
                    description=prompt_row['description'],
                    author_id=prompt_row['author_id'],
                    author_name=prompt_row['author_name'],
                    created_at=prompt_row['created_at'],
                    updated_at=prompt_row['updated_at'],
                    is_public=prompt_row['is_public'],
                    usage_count=prompt_row['usage_count'],
                    views_count=prompt_row['views_count'],
                    tags=tags,
                    average_rating=float(prompt_row['average_rating']),
                    total_votes=prompt_row['total_votes'],
                    user_rating=user_rating,
                    is_bookmarked=is_bookmarked
                )
                
                return prompt
                
        except Exception as e:
            logger.error(f"Ошибка при получении промпта: {e}")
            return None
    
    async def get_prompts(self, filters: PromptFilters, user_id: Optional[str] = None) -> Tuple[List[PromptWithTags], int]:
        """
        Получение списка промптов с фильтрацией
        
        Args:
            filters: Фильтры для поиска
            user_id: ID пользователя (для получения его оценок)
            
        Returns:
            Кортеж (список промптов, общее количество)
        """
        try:
            async with self.db_connection.acquire() as conn:
                # Строим WHERE условие для основного запроса
                where_conditions = ["p.is_public = true"]
                params = []
                param_num = 1
                
                if filters.search_query:
                    search_pattern = f"%{filters.search_query}%"
                    where_conditions.append(f"(p.title ILIKE ${param_num} OR p.description ILIKE ${param_num} OR p.content ILIKE ${param_num})")
                    params.append(search_pattern)
                    param_num += 1
                
                if filters.author_id:
                    where_conditions.append(f"p.author_id = ${param_num}")
                    params.append(filters.author_id)
                    param_num += 1
                
                # Фильтр по тегам
                tag_join = ""
                if filters.tag_ids:
                    tag_join = "JOIN prompt_tags pt ON p.id = pt.prompt_id"
                    placeholders = ", ".join([f"${i}" for i in range(param_num, param_num + len(filters.tag_ids))])
                    where_conditions.append(f"pt.tag_id IN ({placeholders})")
                    params.extend(filters.tag_ids)
                    param_num += len(filters.tag_ids)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # Определяем сортировку
                sort_map = {
                    "rating": "avg_rating",
                    "date": "p.created_at",
                    "views": "p.views_count",
                    "usage": "p.usage_count",
                    "votes": "total_votes"
                }
                sort_field = sort_map.get(filters.sort_by, "avg_rating")
                sort_order = "DESC" if filters.sort_order.lower() == "desc" else "ASC"
                
                # Строим условие для min_rating
                rating_filter = ""
                if filters.min_rating is not None:
                    rating_filter = f" AND COALESCE(agg.avg_rating, 0) >= ${param_num}"
                    params.append(filters.min_rating)
                    param_num += 1
                
                # Добавляем параметры для LIMIT и OFFSET
                limit_param = f"${param_num}"
                offset_param = f"${param_num + 1}"
                params.extend([filters.limit, filters.offset])
                
                # Используем более эффективный подход: сначала агрегация по id, затем джойн
                query = f"""
                    SELECT 
                        p.*,
                        COALESCE(agg.avg_rating, 0) as avg_rating,
                        COALESCE(agg.total_votes, 0) as total_votes
                    FROM prompts p
                    LEFT JOIN (
                        SELECT 
                            pr.prompt_id,
                            AVG(pr.rating) as avg_rating,
                            COUNT(pr.id) as total_votes
                        FROM prompt_ratings pr
                        GROUP BY pr.prompt_id
                    ) agg ON p.id = agg.prompt_id
                    {tag_join}
                    WHERE {where_clause}{rating_filter}
                    ORDER BY {sort_field} {sort_order}, p.id DESC
                    LIMIT {limit_param} OFFSET {offset_param}
                """
                
                # Логируем запрос для отладки
                logger.info(f"=== SQL ЗАПРОС ДЛЯ ПРОМПТОВ ===")
                logger.info(f"Фильтры: sort_by={filters.sort_by}, sort_order={filters.sort_order}, limit={filters.limit}, offset={filters.offset}")
                logger.info(f"SQL: {query[:500]}...")  # Первые 500 символов
                logger.info(f"Параметры: {params}")
                
                # Получаем промпты
                try:
                    prompt_rows = await conn.fetch(query, *params)
                    logger.info(f"Получено строк из БД: {len(prompt_rows)}")
                except Exception as e:
                    logger.error(f"ОШИБКА ВЫПОЛНЕНИЯ SQL: {e}")
                    logger.error(f"Полный запрос: {query}")
                    logger.error(f"Параметры: {params}")
                    raise
                
                # Получаем общее количество
                # Используем ту же структуру запроса, но без LIMIT/OFFSET
                if filters.min_rating is not None:
                    count_params = params[:-2]  # убираем limit и offset
                else:
                    count_params = params[:-2]  # убираем limit и offset
                
                count_query = f"""
                    SELECT COUNT(*)
                    FROM prompts p
                    LEFT JOIN (
                        SELECT 
                            pr.prompt_id,
                            AVG(pr.rating) as avg_rating
                        FROM prompt_ratings pr
                        GROUP BY pr.prompt_id
                    ) agg ON p.id = agg.prompt_id
                    {tag_join}
                    WHERE {where_clause}{rating_filter}
                """
                total_count = await conn.fetchval(count_query, *count_params)
                
                # Формируем результат
                prompts = []
                for row in prompt_rows:
                    # Получаем теги для каждого промпта
                    tag_rows = await conn.fetch("""
                        SELECT t.*
                        FROM tags t
                        JOIN prompt_tags pt ON t.id = pt.tag_id
                        WHERE pt.prompt_id = $1
                    """, row['id'])
                    
                    # Создаем теги с обработкой ошибок валидации
                    tags = []
                    for tag_row in tag_rows:
                        try:
                            tag = Tag(**dict(tag_row))
                            tags.append(tag)
                        except Exception as e:
                            logger.warning(f"Пропущен некорректный тег (ID: {tag_row.get('id')}, name: {tag_row.get('name')}) для промпта {row['id']}: {e}")
                            continue
                    
                    # Получаем оценку пользователя и статус закладки
                    user_rating = None
                    is_bookmarked = False
                    if user_id:
                        # Нормализуем user_id для поиска
                        normalized_user_id = user_id.strip().lower() if user_id else user_id
                        rating_row = await conn.fetchrow("""
                            SELECT rating FROM prompt_ratings
                            WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                        """, row['id'], normalized_user_id)
                        if rating_row:
                            user_rating = rating_row['rating']
                        
                        # Проверяем, добавлен ли в закладки
                        bookmark_row = await conn.fetchrow("""
                            SELECT id FROM prompt_bookmarks
                            WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                        """, row['id'], normalized_user_id)
                        is_bookmarked = bookmark_row is not None
                    
                    prompt = PromptWithTags(
                        id=row['id'],
                        title=row['title'],
                        content=row['content'],
                        description=row['description'],
                        author_id=row['author_id'],
                        author_name=row['author_name'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        is_public=row['is_public'],
                        usage_count=row['usage_count'],
                        views_count=row['views_count'],
                        tags=tags,
                        average_rating=float(row['avg_rating']),
                        total_votes=row['total_votes'],
                        user_rating=user_rating,
                        is_bookmarked=is_bookmarked
                    )
                    prompts.append(prompt)
                
                return prompts, total_count
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка промптов: {e}")
            return [], 0
    
    async def update_prompt(self, prompt_id: int, prompt_data: PromptUpdate, author_id: str) -> bool:
        """
        Обновление промпта (только автор может редактировать)
        
        Args:
            prompt_id: ID промпта
            prompt_data: Новые данные
            author_id: ID автора (для проверки прав)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем author_id для сравнения
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with self.db_connection.acquire() as conn:
                # Проверяем, что пользователь - автор (используем нормализованное сравнение)
                author_check = await conn.fetchval("""
                    SELECT LOWER(TRIM(author_id)) FROM prompts WHERE id = $1
                """, prompt_id)
                
                if author_check != author_id:
                    logger.warning(f"Попытка редактирования чужого промпта: user={author_id}, prompt={prompt_id}")
                    return False
                
                # Обновляем поля
                update_fields = []
                params = []
                param_num = 1
                
                if prompt_data.title is not None:
                    update_fields.append(f"title = ${param_num}")
                    params.append(prompt_data.title)
                    param_num += 1
                
                if prompt_data.content is not None:
                    update_fields.append(f"content = ${param_num}")
                    params.append(prompt_data.content)
                    param_num += 1
                
                if prompt_data.description is not None:
                    update_fields.append(f"description = ${param_num}")
                    params.append(prompt_data.description)
                    param_num += 1
                
                if prompt_data.is_public is not None:
                    update_fields.append(f"is_public = ${param_num}")
                    params.append(prompt_data.is_public)
                    param_num += 1
                
                update_fields.append(f"updated_at = ${param_num}")
                params.append(datetime.utcnow())
                param_num += 1
                
                if update_fields:
                    params.append(prompt_id)
                    query = f"""
                        UPDATE prompts 
                        SET {', '.join(update_fields)}
                        WHERE id = ${param_num}
                    """
                    await conn.execute(query, *params)
                
                # Обновляем теги
                if prompt_data.tag_ids is not None or prompt_data.new_tags is not None:
                    await conn.execute("DELETE FROM prompt_tags WHERE prompt_id = $1", prompt_id)
                    
                    all_tag_ids = list(prompt_data.tag_ids) if prompt_data.tag_ids else []
                    
                    # Создаём новые теги (если указаны)
                    if prompt_data.new_tags:
                        for tag_name in prompt_data.new_tags:
                            tag_name = tag_name.strip()
                            # Валидация: минимум 2 символа
                            if not tag_name or len(tag_name) < 2:
                                logger.warning(f"Пропущен тег с некорректным именем (меньше 2 символов): '{tag_name}'")
                                continue
                            
                            # Проверяем, существует ли тег
                            existing_tag = await conn.fetchrow("""
                                SELECT id FROM tags WHERE LOWER(name) = LOWER($1)
                            """, tag_name)
                            
                            if existing_tag:
                                all_tag_ids.append(existing_tag['id'])
                            else:
                                # Создаём новый тег
                                new_tag = await conn.fetchrow("""
                                    INSERT INTO tags (name)
                                    VALUES ($1)
                                    RETURNING id
                                """, tag_name)
                                all_tag_ids.append(new_tag['id'])
                                logger.info(f"Создан новый тег: {tag_name}")
                    
                    # Добавляем все теги
                    for tag_id in set(all_tag_ids):
                        await conn.execute("""
                            INSERT INTO prompt_tags (prompt_id, tag_id)
                            VALUES ($1, $2)
                            ON CONFLICT DO NOTHING
                        """, prompt_id, tag_id)
                
                logger.info(f"Обновлён промпт: {prompt_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении промпта: {e}")
            return False
    
    async def delete_prompt(self, prompt_id: int, author_id: str) -> bool:
        """
        Удаление промпта (только автор может удалить)
        
        Args:
            prompt_id: ID промпта
            author_id: ID автора (для проверки прав)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем author_id для сравнения
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with self.db_connection.acquire() as conn:
                # Проверяем, что пользователь - автор (используем нормализованное сравнение)
                author_check = await conn.fetchval("""
                    SELECT LOWER(TRIM(author_id)) FROM prompts WHERE id = $1
                """, prompt_id)
                
                if author_check != author_id:
                    logger.warning(f"Попытка удаления чужого промпта: user={author_id}, prompt={prompt_id}")
                    return False
                
                await conn.execute("DELETE FROM prompts WHERE id = $1", prompt_id)
                logger.info(f"Удалён промпт: {prompt_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при удалении промпта: {e}")
            return False
    
    async def rate_prompt(self, prompt_id: int, user_id: str, rating: int) -> bool:
        """
        Оценка промпта пользователем
        
        Args:
            prompt_id: ID промпта
            user_id: ID пользователя
            rating: Оценка (1-5)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем user_id (убираем пробелы, приводим к нижнему регистру для консистентности)
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with self.db_connection.acquire() as conn:
                # Проверяем, существует ли промпт
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM prompts WHERE id = $1)", prompt_id)
                if not exists:
                    logger.warning(f"Попытка оценить несуществующий промпт: {prompt_id}")
                    return False
                
                # Проверяем, не голосовал ли уже пользователь (используем нормализованный user_id)
                existing_rating = await conn.fetchrow("""
                    SELECT rating, id FROM prompt_ratings 
                    WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                """, prompt_id, user_id)
                
                if existing_rating:
                    # Обновляем существующую оценку (используем нормализованный user_id)
                    await conn.execute("""
                        UPDATE prompt_ratings 
                        SET rating = $1, updated_at = NOW()
                        WHERE prompt_id = $2 AND LOWER(TRIM(user_id)) = LOWER(TRIM($3))
                    """, rating, prompt_id, user_id)
                    logger.info(f"Пользователь {user_id} обновил оценку промпта {prompt_id} с {existing_rating['rating']} на {rating}")
                else:
                    # Вставляем новую оценку (используем нормализованный user_id)
                    await conn.execute("""
                        INSERT INTO prompt_ratings (prompt_id, user_id, rating)
                        VALUES ($1, $2, $3)
                    """, prompt_id, user_id, rating)  # user_id уже нормализован выше
                    logger.info(f"Пользователь {user_id} впервые оценил промпт {prompt_id} на {rating}")
                
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при оценке промпта: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def increment_views(self, prompt_id: int) -> bool:
        """Увеличить счётчик просмотров"""
        try:
            async with self.db_connection.acquire() as conn:
                # Сначала получаем текущее значение для логирования
                current_views = await conn.fetchval("""
                    SELECT views_count FROM prompts WHERE id = $1
                """, prompt_id)
                
                if current_views is None:
                    logger.warning(f"Промпт с ID {prompt_id} не найден")
                    return False
                
                # Увеличиваем счетчик
                await conn.execute("""
                    UPDATE prompts SET views_count = views_count + 1
                    WHERE id = $1
                """, prompt_id)
                
                # Проверяем, что значение действительно увеличилось
                new_views = await conn.fetchval("""
                    SELECT views_count FROM prompts WHERE id = $1
                """, prompt_id)
                
                logger.info(f"Промпт {prompt_id}: просмотры {current_views} -> {new_views}")
                return True
        except Exception as e:
            logger.error(f"Ошибка при увеличении просмотров для промпта {prompt_id}: {e}", exc_info=True)
            return False
    
    async def increment_usage(self, prompt_id: int) -> bool:
        """Увеличить счётчик использований"""
        try:
            async with self.db_connection.acquire() as conn:
                await conn.execute("""
                    UPDATE prompts SET usage_count = usage_count + 1
                    WHERE id = $1
                """, prompt_id)
                return True
        except Exception as e:
            logger.error(f"Ошибка при увеличении использований: {e}")
            return False
    
    async def get_prompt_stats(self, prompt_id: int) -> Optional[PromptStats]:
        """Получить статистику промпта"""
        try:
            async with self.db_connection.acquire() as conn:
                # Основная статистика
                row = await conn.fetchrow("""
                    SELECT 
                        p.views_count,
                        p.usage_count,
                        COALESCE(AVG(pr.rating), 0) as average_rating,
                        COUNT(pr.id) as total_votes
                    FROM prompts p
                    LEFT JOIN prompt_ratings pr ON p.id = pr.prompt_id
                    WHERE p.id = $1
                    GROUP BY p.id, p.views_count, p.usage_count
                """, prompt_id)
                
                if not row:
                    return None
                
                # Распределение оценок
                distribution_rows = await conn.fetch("""
                    SELECT rating, COUNT(*) as count
                    FROM prompt_ratings
                    WHERE prompt_id = $1
                    GROUP BY rating
                """, prompt_id)
                
                rating_distribution = {row['rating']: row['count'] for row in distribution_rows}
                
                return PromptStats(
                    prompt_id=prompt_id,
                    views_count=row['views_count'],
                    usage_count=row['usage_count'],
                    average_rating=float(row['average_rating']),
                    total_votes=row['total_votes'],
                    rating_distribution=rating_distribution
                )
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return None
    
    async def add_bookmark(self, prompt_id: int, user_id: str) -> bool:
        """Добавить промпт в закладки"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with self.db_connection.acquire() as conn:
                # Проверяем, существует ли промпт
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM prompts WHERE id = $1)", prompt_id)
                if not exists:
                    logger.warning(f"Попытка добавить в закладки несуществующий промпт: {prompt_id}")
                    return False
                
                # Добавляем в закладки (или игнорируем, если уже есть)
                await conn.execute("""
                    INSERT INTO prompt_bookmarks (prompt_id, user_id)
                    VALUES ($1, $2)
                    ON CONFLICT (prompt_id, user_id) DO NOTHING
                """, prompt_id, user_id)
                
                logger.info(f"Пользователь {user_id} добавил промпт {prompt_id} в закладки")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении в закладки: {e}")
            return False
    
    async def remove_bookmark(self, prompt_id: int, user_id: str) -> bool:
        """Удалить промпт из закладок"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with self.db_connection.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM prompt_bookmarks
                    WHERE prompt_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                """, prompt_id, user_id)
                
                logger.info(f"Пользователь {user_id} удалил промпт {prompt_id} из закладок")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при удалении из закладок: {e}")
            return False
    
    async def get_user_bookmarks(self, user_id: str, limit: int = 100, offset: int = 0) -> Tuple[List[int], int]:
        """Получить список ID промптов в закладках пользователя"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with self.db_connection.acquire() as conn:
                # Получаем ID промптов
                rows = await conn.fetch("""
                    SELECT prompt_id
                    FROM prompt_bookmarks
                    WHERE LOWER(TRIM(user_id)) = LOWER(TRIM($1))
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """, user_id, limit, offset)
                
                # Получаем общее количество
                total = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM prompt_bookmarks
                    WHERE LOWER(TRIM(user_id)) = LOWER(TRIM($1))
                """, user_id)
                
                prompt_ids = [row['prompt_id'] for row in rows]
                return prompt_ids, total
                
        except Exception as e:
            logger.error(f"Ошибка при получении закладок: {e}")
            return [], 0


class TagRepository:
    """Репозиторий для работы с тегами"""
    
    def __init__(self, db_connection: PostgreSQLConnection):
        self.db_connection = db_connection
    
    async def create_tag(self, tag_data: TagCreate) -> Optional[int]:
        """Создание тега"""
        try:
            async with self.db_connection.acquire() as conn:
                result = await conn.fetchrow("""
                    INSERT INTO tags (name, description, color)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (name) DO UPDATE SET name = tags.name
                    RETURNING id
                """, tag_data.name, tag_data.description, tag_data.color)
                
                return result['id']
                
        except Exception as e:
            logger.error(f"Ошибка при создании тега: {e}")
            return None
    
    async def get_all_tags(self) -> List[Tag]:
        """Получить все теги"""
        try:
            async with self.db_connection.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM tags ORDER BY name")
                tags = []
                for row in rows:
                    try:
                        tag = Tag(**dict(row))
                        tags.append(tag)
                    except Exception as e:
                        logger.warning(f"Пропущен некорректный тег (ID: {row.get('id')}, name: {row.get('name')}): {e}")
                        continue
                return tags
        except Exception as e:
            logger.error(f"Ошибка при получении тегов: {e}")
            return []
    
    async def get_popular_tags(self, limit: int = 20) -> List[Tuple[Tag, int]]:
        """Получить популярные теги с количеством промптов"""
        try:
            async with self.db_connection.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT t.*, COUNT(pt.prompt_id) as prompt_count
                    FROM tags t
                    LEFT JOIN prompt_tags pt ON t.id = pt.tag_id
                    GROUP BY t.id
                    ORDER BY prompt_count DESC, t.name
                    LIMIT $1
                """, limit)
                
                result = []
                for row in rows:
                    try:
                        tag = Tag(**dict(row))
                        result.append((tag, row['prompt_count']))
                    except Exception as e:
                        logger.warning(f"Пропущен некорректный тег (ID: {row.get('id')}, name: {row.get('name')}): {e}")
                        continue
                return result
        except Exception as e:
            logger.error(f"Ошибка при получении популярных тегов: {e}")
            return []

