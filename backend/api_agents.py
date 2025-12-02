"""
API endpoints для галереи агентов
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.database.postgresql.agent_models import (
    AgentWithTags, AgentCreate, AgentUpdate, AgentFilters, 
    AgentStats
)
from backend.database.init_db import get_agent_repository, get_tag_repository
from backend.auth.jwt_handler import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

# Создаём роутер
router = APIRouter(prefix="/api/agents", tags=["agents"])


# ===================================
# АГЕНТЫ - CRUD ОПЕРАЦИИ
# ===================================

@router.post("/", response_model=dict, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Создание нового агента"""
    try:
        agent_repo = get_agent_repository()
        
        agent_id = await agent_repo.create_agent(
            agent_data=agent_data,
            author_id=current_user["user_id"],
            author_name=current_user.get("username", "Anonymous")
        )
        
        if agent_id:
            return {"success": True, "agent_id": agent_id, "message": "Агент успешно создан"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при создании агента")
            
    except Exception as e:
        logger.error(f"Ошибка создания агента: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# ПРОСМОТРЫ И ИСПОЛЬЗОВАНИЕ
# ===================================

@router.post("/{agent_id}/view", response_model=dict)
async def view_agent(
    agent_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Увеличить счетчик просмотров агента (публичный доступ)"""
    try:
        agent_repo = get_agent_repository()
        
        success = await agent_repo.increment_views(agent_id)
        
        if success:
            return {"success": True, "message": "Просмотр учтён"}
        else:
            raise HTTPException(status_code=404, detail="Агент не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка учёта просмотра: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=AgentWithTags)
async def get_agent(
    agent_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение агента по ID (публичный доступ)"""
    try:
        agent_repo = get_agent_repository()
        
        user_id = current_user["user_id"] if current_user else None
        agent = await agent_repo.get_agent(agent_id, user_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Агент не найден")
        
        # Увеличиваем счётчик просмотров
        await agent_repo.increment_views(agent_id)
        
        return agent
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения агента: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AgentsResponse(BaseModel):
    """Ответ со списком агентов"""
    agents: List[AgentWithTags]
    total: int
    page: int
    pages: int


@router.get("/", response_model=AgentsResponse)
async def get_agents(
    search: Optional[str] = Query(None, description="Поисковый запрос"),
    tags: Optional[str] = Query(None, description="ID тегов через запятую"),
    author_id: Optional[str] = Query(None, description="ID автора"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Минимальный рейтинг"),
    sort_by: str = Query("rating", description="Поле сортировки (rating, date, views, usage, votes)"),
    sort_order: str = Query("desc", description="Порядок сортировки (asc/desc)"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    limit: int = Query(20, ge=1, le=100, description="Количество на странице"),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение списка агентов с фильтрацией (публичный доступ)"""
    try:
        logger.info(f"Запрос списка агентов: page={page}, limit={limit}, sort_by={sort_by}, sort_order={sort_order}")
        agent_repo = get_agent_repository()
        
        # Парсим теги
        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат тегов")
        
        # Создаём фильтры
        filters = AgentFilters(
            search_query=search,
            tag_ids=tag_ids,
            author_id=author_id,
            min_rating=min_rating,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=(page - 1) * limit
        )
        
        user_id = current_user["user_id"] if current_user else None
        agents, total = await agent_repo.get_agents(filters, user_id)
        
        logger.info(f"Получено агентов: {len(agents)}, всего: {total}")
        
        pages = (total + limit - 1) // limit  # Округление вверх
        
        return AgentsResponse(
            agents=agents,
            total=total,
            page=page,
            pages=pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения списка агентов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}", response_model=dict)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Обновление агента (только автор)"""
    try:
        agent_repo = get_agent_repository()
        
        success = await agent_repo.update_agent(
            agent_id=agent_id,
            agent_data=agent_data,
            author_id=current_user["user_id"]
        )
        
        if success:
            return {"success": True, "message": "Агент успешно обновлён"}
        else:
            raise HTTPException(
                status_code=403, 
                detail="Недостаточно прав для редактирования этого агента"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления агента: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}", response_model=dict)
async def delete_agent(
    agent_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Удаление агента (только автор)"""
    try:
        agent_repo = get_agent_repository()
        
        success = await agent_repo.delete_agent(
            agent_id=agent_id,
            author_id=current_user["user_id"]
        )
        
        if success:
            return {"success": True, "message": "Агент успешно удалён"}
        else:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для удаления этого агента"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления агента: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# РЕЙТИНГИ И СТАТИСТИКА
# ===================================

class RatingRequest(BaseModel):
    """Запрос на оценку агента"""
    rating: int


@router.post("/{agent_id}/rate", response_model=dict)
async def rate_agent(
    agent_id: int,
    rating_request: RatingRequest,
    current_user: dict = Depends(get_current_user)
):
    """Оценка агента пользователем"""
    try:
        if rating_request.rating < 1 or rating_request.rating > 5:
            raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")
        
        agent_repo = get_agent_repository()
        
        success = await agent_repo.rate_agent(
            agent_id=agent_id,
            user_id=current_user["user_id"],
            rating=rating_request.rating
        )
        
        if success:
            return {"success": True, "message": "Оценка сохранена"}
        else:
            raise HTTPException(status_code=404, detail="Агент не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка оценки агента: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/use", response_model=dict)
async def use_agent(
    agent_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Отметить использование агента"""
    try:
        agent_repo = get_agent_repository()
        
        # Увеличиваем счетчик использований
        usage_success = await agent_repo.increment_usage(agent_id)
        
        if usage_success:
            return {"success": True, "message": "Использование учтено"}
        else:
            raise HTTPException(status_code=404, detail="Агент не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка учёта использования: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/stats", response_model=AgentStats)
async def get_agent_stats(
    agent_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение статистики агента (публичный доступ)"""
    try:
        agent_repo = get_agent_repository()
        
        stats = await agent_repo.get_agent_stats(agent_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Агент не найден")
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# ЗАКЛАДКИ
# ===================================

@router.post("/{agent_id}/bookmark", response_model=dict)
async def add_bookmark(
    agent_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Добавить агента в закладки"""
    try:
        agent_repo = get_agent_repository()
        
        success = await agent_repo.add_bookmark(agent_id, current_user["user_id"])
        
        if success:
            return {"success": True, "message": "Добавлено в закладки"}
        else:
            raise HTTPException(status_code=404, detail="Агент не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления в закладки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/bookmark", response_model=dict)
async def remove_bookmark(
    agent_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Удалить агента из закладок"""
    try:
        agent_repo = get_agent_repository()
        
        success = await agent_repo.remove_bookmark(agent_id, current_user["user_id"])
        
        if success:
            return {"success": True, "message": "Удалено из закладок"}
        else:
            raise HTTPException(status_code=404, detail="Агент не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления из закладок: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my/bookmarks", response_model=AgentsResponse)
async def get_my_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Получение закладок текущего пользователя"""
    try:
        logger.info(f"Запрос закладок пользователя: {current_user.get('user_id', 'unknown')}, page={page}, limit={limit}")
        
        agent_repo = get_agent_repository()
        
        # Получаем ID агентов в закладках
        bookmark_ids, total = await agent_repo.get_user_bookmarks(
            current_user["user_id"],
            limit=limit,
            offset=(page - 1) * limit
        )
        
        logger.info(f"Найдено закладок: {total}, IDs: {bookmark_ids}")
        
        if not bookmark_ids:
            logger.info("У пользователя нет закладок")
            return AgentsResponse(
                agents=[],
                total=0,
                page=page,
                pages=0
            )
        
        # Получаем полные данные агентов
        agents = []
        for agent_id in bookmark_ids:
            agent = await agent_repo.get_agent(agent_id, current_user["user_id"])
            if agent:
                agents.append(agent)
        
        pages = (total + limit - 1) // limit
        
        logger.info(f"Возвращаем {len(agents)} агентов из закладок")
        
        return AgentsResponse(
            agents=agents,
            total=total,
            page=page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения закладок: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# МОИ АГЕНТЫ
# ===================================

@router.get("/my/agents", response_model=AgentsResponse)
async def get_my_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Получение агентов текущего пользователя"""
    try:
        agent_repo = get_agent_repository()
        
        filters = AgentFilters(
            author_id=current_user["user_id"],
            sort_by="date",
            sort_order="desc",
            limit=limit,
            offset=(page - 1) * limit
        )
        
        agents, total = await agent_repo.get_agents(filters, current_user["user_id"])
        
        pages = (total + limit - 1) // limit
        
        return AgentsResponse(
            agents=agents,
            total=total,
            page=page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения моих агентов: {e}")
        raise HTTPException(status_code=500, detail=str(e))








