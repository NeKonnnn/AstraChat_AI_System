"""
Репозиторий для работы с агентами в PostgreSQL
"""

import logging
import json
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

from .agent_models import (
    Agent, AgentWithTags, AgentRating, 
    AgentCreate, AgentUpdate, AgentFilters, AgentStats
)
from .connection import PostgreSQLConnection
from .prompt_models import Tag

logger = logging.getLogger(__name__)


class AgentRepository:
    """Репозиторий для работы с агентами"""
    
    def __init__(self, db_connection: PostgreSQLConnection):
        """
        Инициализация репозитория
        
        Args:
            db_connection: Подключение к PostgreSQL
        """
        self.db_connection = db_connection
    
    async def create_tables(self):
        """Создание таблиц для агентов"""
        try:
            async with await self.db_connection.acquire() as conn:
                # Таблица агентов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS agents (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        system_prompt TEXT NOT NULL,
                        config JSONB DEFAULT '{}'::jsonb,
                        tools JSONB DEFAULT '[]'::jsonb,
                        author_id VARCHAR(100) NOT NULL,
                        author_name VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        is_public BOOLEAN DEFAULT true,
                        usage_count INTEGER DEFAULT 0,
                        views_count INTEGER DEFAULT 0
                    )
                """)
                
                # Связь агентов и тегов (many-to-many) - используем те же теги, что и для промптов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_tags (
                        agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
                        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                        PRIMARY KEY (agent_id, tag_id)
                    )
                """)
                
                # Таблица рейтингов агентов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_ratings (
                        id SERIAL PRIMARY KEY,
                        agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
                        user_id VARCHAR(100) NOT NULL,
                        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(agent_id, user_id)
                    )
                """)
                
                # Таблица закладок агентов
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS agent_bookmarks (
                        id SERIAL PRIMARY KEY,
                        agent_id INTEGER REFERENCES agents(id) ON DELETE CASCADE,
                        user_id VARCHAR(100) NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(agent_id, user_id)
                    )
                """)
                
                # Индексы для производительности
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_author ON agents(author_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_created ON agents(created_at DESC)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agents_public ON agents(is_public)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_tags_agent ON agent_tags(agent_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_tags_tag ON agent_tags(tag_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_ratings_agent ON agent_ratings(agent_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_ratings_user ON agent_ratings(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_bookmarks_user ON agent_bookmarks(user_id)")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_bookmarks_agent ON agent_bookmarks(agent_id)")
                
                logger.info("Таблицы для галереи агентов созданы")
                
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц агентов: {e}")
            raise
    
    async def create_agent(self, agent_data: AgentCreate, author_id: str, author_name: str) -> Optional[int]:
        """
        Создание нового агента
        
        Args:
            agent_data: Данные агента
            author_id: ID автора
            author_name: Имя автора
            
        Returns:
            ID созданного агента или None в случае ошибки
        """
        try:
            # Нормализуем author_id для консистентности
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with await self.db_connection.acquire() as conn:
                # Преобразуем config и tools в JSON
                config_json = json.dumps(agent_data.config or {})
                tools_json = json.dumps(agent_data.tools or [])
                
                # Создаём агента
                result = await conn.fetchrow("""
                    INSERT INTO agents (name, description, system_prompt, config, tools, author_id, author_name, is_public)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8)
                    RETURNING id
                """, 
                    agent_data.name,
                    agent_data.description,
                    agent_data.system_prompt,
                    config_json,
                    tools_json,
                    author_id,
                    author_name,
                    agent_data.is_public
                )
                
                agent_id = result['id']
                
                # Создаём новые теги (если указаны)
                all_tag_ids = list(agent_data.tag_ids) if agent_data.tag_ids else []
                
                if agent_data.new_tags:
                    for tag_name in agent_data.new_tags:
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
                
                # Добавляем все теги к агенту
                for tag_id in set(all_tag_ids):  # set() для удаления дубликатов
                    await conn.execute("""
                        INSERT INTO agent_tags (agent_id, tag_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                    """, agent_id, tag_id)
                
                logger.info(f"Создан агент: {agent_data.name} (ID: {agent_id})")
                return agent_id
                
        except Exception as e:
            logger.error(f"Ошибка при создании агента: {e}")
            return None
    
    async def get_agent(self, agent_id: int, user_id: Optional[str] = None) -> Optional[AgentWithTags]:
        """
        Получение агента по ID с тегами и рейтингом
        
        Args:
            agent_id: ID агента
            user_id: ID пользователя (для получения его оценки)
            
        Returns:
            Агент с тегами и рейтингом или None
        """
        try:
            async with await self.db_connection.acquire() as conn:
                # Получаем агента
                agent_row = await conn.fetchrow("""
                    SELECT a.*, 
                           COALESCE(AVG(ar.rating), 0) as average_rating,
                           COUNT(ar.id) as total_votes
                    FROM agents a
                    LEFT JOIN agent_ratings ar ON a.id = ar.agent_id
                    WHERE a.id = $1
                    GROUP BY a.id
                """, agent_id)
                
                if not agent_row:
                    return None
                
                # Получаем теги
                tag_rows = await conn.fetch("""
                    SELECT t.*
                    FROM tags t
                    JOIN agent_tags at ON t.id = at.tag_id
                    WHERE at.agent_id = $1
                """, agent_id)
                
                # Создаем теги с обработкой ошибок валидации
                tags = []
                for row in tag_rows:
                    try:
                        tag = Tag(**dict(row))
                        tags.append(tag.dict())
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
                        SELECT rating FROM agent_ratings
                        WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                    """, agent_id, normalized_user_id)
                    if rating_row:
                        user_rating = rating_row['rating']
                    
                    # Проверяем, добавлен ли в закладки
                    bookmark_row = await conn.fetchrow("""
                        SELECT id FROM agent_bookmarks
                        WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                    """, agent_id, normalized_user_id)
                    is_bookmarked = bookmark_row is not None
                
                # Парсим JSON поля
                config = agent_row['config'] if isinstance(agent_row['config'], dict) else json.loads(agent_row['config'] or '{}')
                tools = agent_row['tools'] if isinstance(agent_row['tools'], list) else json.loads(agent_row['tools'] or '[]')
                
                # Формируем объект
                agent = AgentWithTags(
                    id=agent_row['id'],
                    name=agent_row['name'],
                    description=agent_row['description'],
                    system_prompt=agent_row['system_prompt'],
                    config=config,
                    tools=tools,
                    author_id=agent_row['author_id'],
                    author_name=agent_row['author_name'],
                    created_at=agent_row['created_at'],
                    updated_at=agent_row['updated_at'],
                    is_public=agent_row['is_public'],
                    usage_count=agent_row['usage_count'],
                    views_count=agent_row['views_count'],
                    tags=tags,
                    average_rating=float(agent_row['average_rating']),
                    total_votes=agent_row['total_votes'],
                    user_rating=user_rating,
                    is_bookmarked=is_bookmarked
                )
                
                return agent
                
        except Exception as e:
            logger.error(f"Ошибка при получении агента: {e}")
            return None
    
    async def get_agents(self, filters: AgentFilters, user_id: Optional[str] = None) -> Tuple[List[AgentWithTags], int]:
        """
        Получение списка агентов с фильтрацией
        
        Args:
            filters: Фильтры для поиска
            user_id: ID пользователя (для получения его оценок)
            
        Returns:
            Кортеж (список агентов, общее количество)
        """
        try:
            async with await self.db_connection.acquire() as conn:
                # Строим WHERE условие для основного запроса
                where_conditions = ["a.is_public = true"]
                params = []
                param_num = 1
                
                if filters.search_query:
                    search_pattern = f"%{filters.search_query}%"
                    where_conditions.append(f"(a.name ILIKE ${param_num} OR a.description ILIKE ${param_num} OR a.system_prompt ILIKE ${param_num})")
                    params.append(search_pattern)
                    param_num += 1
                
                if filters.author_id:
                    where_conditions.append(f"a.author_id = ${param_num}")
                    params.append(filters.author_id)
                    param_num += 1
                
                # Фильтр по тегам
                tag_join = ""
                if filters.tag_ids:
                    tag_join = "JOIN agent_tags at ON a.id = at.agent_id"
                    placeholders = ", ".join([f"${i}" for i in range(param_num, param_num + len(filters.tag_ids))])
                    where_conditions.append(f"at.tag_id IN ({placeholders})")
                    params.extend(filters.tag_ids)
                    param_num += len(filters.tag_ids)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                # Определяем сортировку
                sort_map = {
                    "rating": "avg_rating",
                    "date": "a.created_at",
                    "views": "a.views_count",
                    "usage": "a.usage_count",
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
                
                # Запрос для получения агентов
                query = f"""
                    SELECT 
                        a.*,
                        COALESCE(agg.avg_rating, 0) as avg_rating,
                        COALESCE(agg.total_votes, 0) as total_votes
                    FROM agents a
                    LEFT JOIN (
                        SELECT 
                            ar.agent_id,
                            AVG(ar.rating) as avg_rating,
                            COUNT(ar.id) as total_votes
                        FROM agent_ratings ar
                        GROUP BY ar.agent_id
                    ) agg ON a.id = agg.agent_id
                    {tag_join}
                    WHERE {where_clause}{rating_filter}
                    ORDER BY {sort_field} {sort_order}, a.id DESC
                    LIMIT {limit_param} OFFSET {offset_param}
                """
                
                # Получаем агентов
                agent_rows = await conn.fetch(query, *params)
                
                # Получаем общее количество
                count_params = params[:-2]  # убираем limit и offset
                count_query = f"""
                    SELECT COUNT(*)
                    FROM agents a
                    LEFT JOIN (
                        SELECT 
                            ar.agent_id,
                            AVG(ar.rating) as avg_rating
                        FROM agent_ratings ar
                        GROUP BY ar.agent_id
                    ) agg ON a.id = agg.agent_id
                    {tag_join}
                    WHERE {where_clause}{rating_filter}
                """
                total_count = await conn.fetchval(count_query, *count_params)
                
                # Формируем результат
                agents = []
                for row in agent_rows:
                    # Получаем теги для каждого агента
                    tag_rows = await conn.fetch("""
                        SELECT t.*
                        FROM tags t
                        JOIN agent_tags at ON t.id = at.tag_id
                        WHERE at.agent_id = $1
                    """, row['id'])
                    
                    # Создаем теги
                    tags = []
                    for tag_row in tag_rows:
                        try:
                            tag = Tag(**dict(tag_row))
                            tags.append(tag.dict())
                        except Exception as e:
                            logger.warning(f"Пропущен некорректный тег для агента {row['id']}: {e}")
                            continue
                    
                    # Получаем оценку пользователя и статус закладки
                    user_rating = None
                    is_bookmarked = False
                    if user_id:
                        normalized_user_id = user_id.strip().lower() if user_id else user_id
                        rating_row = await conn.fetchrow("""
                            SELECT rating FROM agent_ratings
                            WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                        """, row['id'], normalized_user_id)
                        if rating_row:
                            user_rating = rating_row['rating']
                        
                        bookmark_row = await conn.fetchrow("""
                            SELECT id FROM agent_bookmarks
                            WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                        """, row['id'], normalized_user_id)
                        is_bookmarked = bookmark_row is not None
                    
                    # Парсим JSON поля
                    config = row['config'] if isinstance(row['config'], dict) else json.loads(row['config'] or '{}')
                    tools = row['tools'] if isinstance(row['tools'], list) else json.loads(row['tools'] or '[]')
                    
                    agent = AgentWithTags(
                        id=row['id'],
                        name=row['name'],
                        description=row['description'],
                        system_prompt=row['system_prompt'],
                        config=config,
                        tools=tools,
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
                    agents.append(agent)
                
                return agents, total_count
                
        except Exception as e:
            logger.error(f"Ошибка при получении списка агентов: {e}")
            return [], 0
    
    async def update_agent(self, agent_id: int, agent_data: AgentUpdate, author_id: str) -> bool:
        """
        Обновление агента (только автор может редактировать)
        
        Args:
            agent_id: ID агента
            agent_data: Новые данные
            author_id: ID автора (для проверки прав)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем author_id для сравнения
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with await self.db_connection.acquire() as conn:
                # Проверяем, что пользователь - автор
                author_check = await conn.fetchval("""
                    SELECT LOWER(TRIM(author_id)) FROM agents WHERE id = $1
                """, agent_id)
                
                if author_check != author_id:
                    logger.warning(f"Попытка редактирования чужого агента: user={author_id}, agent={agent_id}")
                    return False
                
                # Обновляем поля
                update_fields = []
                params = []
                param_num = 1
                
                if agent_data.name is not None:
                    update_fields.append(f"name = ${param_num}")
                    params.append(agent_data.name)
                    param_num += 1
                
                if agent_data.description is not None:
                    update_fields.append(f"description = ${param_num}")
                    params.append(agent_data.description)
                    param_num += 1
                
                if agent_data.system_prompt is not None:
                    update_fields.append(f"system_prompt = ${param_num}")
                    params.append(agent_data.system_prompt)
                    param_num += 1
                
                if agent_data.config is not None:
                    update_fields.append(f"config = ${param_num}::jsonb")
                    params.append(json.dumps(agent_data.config))
                    param_num += 1
                
                if agent_data.tools is not None:
                    update_fields.append(f"tools = ${param_num}::jsonb")
                    params.append(json.dumps(agent_data.tools))
                    param_num += 1
                
                if agent_data.is_public is not None:
                    update_fields.append(f"is_public = ${param_num}")
                    params.append(agent_data.is_public)
                    param_num += 1
                
                update_fields.append(f"updated_at = ${param_num}")
                params.append(datetime.utcnow())
                param_num += 1
                
                if update_fields:
                    params.append(agent_id)
                    query = f"""
                        UPDATE agents 
                        SET {', '.join(update_fields)}
                        WHERE id = ${param_num}
                    """
                    await conn.execute(query, *params)
                
                # Обновляем теги
                if agent_data.tag_ids is not None or agent_data.new_tags is not None:
                    await conn.execute("DELETE FROM agent_tags WHERE agent_id = $1", agent_id)
                    
                    all_tag_ids = list(agent_data.tag_ids) if agent_data.tag_ids else []
                    
                    # Создаём новые теги (если указаны)
                    if agent_data.new_tags:
                        for tag_name in agent_data.new_tags:
                            tag_name = tag_name.strip()
                            if not tag_name or len(tag_name) < 2:
                                logger.warning(f"Пропущен тег с некорректным именем: '{tag_name}'")
                                continue
                            
                            existing_tag = await conn.fetchrow("""
                                SELECT id FROM tags WHERE LOWER(name) = LOWER($1)
                            """, tag_name)
                            
                            if existing_tag:
                                all_tag_ids.append(existing_tag['id'])
                            else:
                                new_tag = await conn.fetchrow("""
                                    INSERT INTO tags (name)
                                    VALUES ($1)
                                    RETURNING id
                                """, tag_name)
                                all_tag_ids.append(new_tag['id'])
                    
                    # Добавляем все теги
                    for tag_id in set(all_tag_ids):
                        await conn.execute("""
                            INSERT INTO agent_tags (agent_id, tag_id)
                            VALUES ($1, $2)
                            ON CONFLICT DO NOTHING
                        """, agent_id, tag_id)
                
                logger.info(f"Обновлён агент: {agent_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении агента: {e}")
            return False
    
    async def delete_agent(self, agent_id: int, author_id: str) -> bool:
        """
        Удаление агента (только автор может удалить)
        
        Args:
            agent_id: ID агента
            author_id: ID автора (для проверки прав)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем author_id для сравнения
            author_id = author_id.strip().lower() if author_id else author_id
            
            async with await self.db_connection.acquire() as conn:
                # Проверяем, что пользователь - автор
                author_check = await conn.fetchval("""
                    SELECT LOWER(TRIM(author_id)) FROM agents WHERE id = $1
                """, agent_id)
                
                if author_check != author_id:
                    logger.warning(f"Попытка удаления чужого агента: user={author_id}, agent={agent_id}")
                    return False
                
                await conn.execute("DELETE FROM agents WHERE id = $1", agent_id)
                logger.info(f"Удалён агент: {agent_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при удалении агента: {e}")
            return False
    
    async def rate_agent(self, agent_id: int, user_id: str, rating: int) -> bool:
        """
        Оценка агента пользователем
        
        Args:
            agent_id: ID агента
            user_id: ID пользователя
            rating: Оценка (1-5)
            
        Returns:
            True если успешно, False в случае ошибки
        """
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with await self.db_connection.acquire() as conn:
                # Проверяем, существует ли агент
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM agents WHERE id = $1)", agent_id)
                if not exists:
                    logger.warning(f"Попытка оценить несуществующий агент: {agent_id}")
                    return False
                
                # Проверяем, не голосовал ли уже пользователь
                existing_rating = await conn.fetchrow("""
                    SELECT rating, id FROM agent_ratings 
                    WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                """, agent_id, user_id)
                
                if existing_rating:
                    # Обновляем существующую оценку
                    await conn.execute("""
                        UPDATE agent_ratings 
                        SET rating = $1, updated_at = NOW()
                        WHERE agent_id = $2 AND LOWER(TRIM(user_id)) = LOWER(TRIM($3))
                    """, rating, agent_id, user_id)
                    logger.info(f"Пользователь {user_id} обновил оценку агента {agent_id} с {existing_rating['rating']} на {rating}")
                else:
                    # Вставляем новую оценку
                    await conn.execute("""
                        INSERT INTO agent_ratings (agent_id, user_id, rating)
                        VALUES ($1, $2, $3)
                    """, agent_id, user_id, rating)
                    logger.info(f"Пользователь {user_id} впервые оценил агента {agent_id} на {rating}")
                
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при оценке агента: {e}")
            return False
    
    async def increment_views(self, agent_id: int) -> bool:
        """Увеличить счётчик просмотров"""
        try:
            async with await self.db_connection.acquire() as conn:
                current_views = await conn.fetchval("""
                    SELECT views_count FROM agents WHERE id = $1
                """, agent_id)
                
                if current_views is None:
                    logger.warning(f"Агент с ID {agent_id} не найден")
                    return False
                
                await conn.execute("""
                    UPDATE agents SET views_count = views_count + 1
                    WHERE id = $1
                """, agent_id)
                
                logger.info(f"Агент {agent_id}: просмотры {current_views} -> {current_views + 1}")
                return True
        except Exception as e:
            logger.error(f"Ошибка при увеличении просмотров для агента {agent_id}: {e}")
            return False
    
    async def increment_usage(self, agent_id: int) -> bool:
        """Увеличить счётчик использований"""
        try:
            async with await self.db_connection.acquire() as conn:
                await conn.execute("""
                    UPDATE agents SET usage_count = usage_count + 1
                    WHERE id = $1
                """, agent_id)
                return True
        except Exception as e:
            logger.error(f"Ошибка при увеличении использований: {e}")
            return False
    
    async def get_agent_stats(self, agent_id: int) -> Optional[AgentStats]:
        """Получить статистику агента"""
        try:
            async with await self.db_connection.acquire() as conn:
                # Основная статистика
                row = await conn.fetchrow("""
                    SELECT 
                        a.views_count,
                        a.usage_count,
                        COALESCE(AVG(ar.rating), 0) as average_rating,
                        COUNT(ar.id) as total_votes
                    FROM agents a
                    LEFT JOIN agent_ratings ar ON a.id = ar.agent_id
                    WHERE a.id = $1
                    GROUP BY a.id, a.views_count, a.usage_count
                """, agent_id)
                
                if not row:
                    return None
                
                # Распределение оценок
                distribution_rows = await conn.fetch("""
                    SELECT rating, COUNT(*) as count
                    FROM agent_ratings
                    WHERE agent_id = $1
                    GROUP BY rating
                """, agent_id)
                
                rating_distribution = {row['rating']: row['count'] for row in distribution_rows}
                
                return AgentStats(
                    agent_id=agent_id,
                    views_count=row['views_count'],
                    usage_count=row['usage_count'],
                    average_rating=float(row['average_rating']),
                    total_votes=row['total_votes'],
                    rating_distribution=rating_distribution
                )
                
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return None
    
    async def add_bookmark(self, agent_id: int, user_id: str) -> bool:
        """Добавить агента в закладки"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with await self.db_connection.acquire() as conn:
                # Проверяем, существует ли агент
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM agents WHERE id = $1)", agent_id)
                if not exists:
                    logger.warning(f"Попытка добавить в закладки несуществующий агент: {agent_id}")
                    return False
                
                # Добавляем в закладки
                await conn.execute("""
                    INSERT INTO agent_bookmarks (agent_id, user_id)
                    VALUES ($1, $2)
                    ON CONFLICT (agent_id, user_id) DO NOTHING
                """, agent_id, user_id)
                
                logger.info(f"Пользователь {user_id} добавил агента {agent_id} в закладки")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении в закладки: {e}")
            return False
    
    async def remove_bookmark(self, agent_id: int, user_id: str) -> bool:
        """Удалить агента из закладок"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with await self.db_connection.acquire() as conn:
                await conn.execute("""
                    DELETE FROM agent_bookmarks
                    WHERE agent_id = $1 AND LOWER(TRIM(user_id)) = LOWER(TRIM($2))
                """, agent_id, user_id)
                
                logger.info(f"Пользователь {user_id} удалил агента {agent_id} из закладок")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка при удалении из закладок: {e}")
            return False
    
    async def get_user_bookmarks(self, user_id: str, limit: int = 100, offset: int = 0) -> Tuple[List[int], int]:
        """Получить список ID агентов в закладках пользователя"""
        try:
            # Нормализуем user_id
            user_id = user_id.strip().lower() if user_id else user_id
            
            async with await self.db_connection.acquire() as conn:
                # Получаем ID агентов
                rows = await conn.fetch("""
                    SELECT agent_id
                    FROM agent_bookmarks
                    WHERE LOWER(TRIM(user_id)) = LOWER(TRIM($1))
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                """, user_id, limit, offset)
                
                # Получаем общее количество
                total = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM agent_bookmarks
                    WHERE LOWER(TRIM(user_id)) = LOWER(TRIM($1))
                """, user_id)
                
                agent_ids = [row['agent_id'] for row in rows]
                return agent_ids, total
                
        except Exception as e:
            logger.error(f"Ошибка при получении закладок: {e}")
            return [], 0

