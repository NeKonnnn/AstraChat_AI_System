"""
API endpoints для галереи промптов
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.database.postgresql.prompt_models import (
    PromptWithTags, PromptCreate, PromptUpdate, PromptFilters, 
    Tag, TagCreate, PromptStats
)
from backend.database.init_db import get_prompt_repository, get_tag_repository
from backend.auth.jwt_handler import get_current_user, get_optional_user

logger = logging.getLogger(__name__)

# Создаём роутер
router = APIRouter(prefix="/api/prompts", tags=["prompts"])


# ===================================
# ПРОМПТЫ - CRUD ОПЕРАЦИИ
# ===================================

@router.post("/", response_model=dict, status_code=201)
async def create_prompt(
    prompt_data: PromptCreate,
    current_user: dict = Depends(get_current_user)
):
    """Создание нового промпта"""
    try:
        prompt_repo = get_prompt_repository()
        
        prompt_id = await prompt_repo.create_prompt(
            prompt_data=prompt_data,
            author_id=current_user["user_id"],
            author_name=current_user.get("username", "Anonymous")
        )
        
        if prompt_id:
            return {"success": True, "prompt_id": prompt_id, "message": "Промпт успешно создан"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при создании промпта")
            
    except Exception as e:
        logger.error(f"Ошибка создания промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# ПРОСМОТРЫ И ИСПОЛЬЗОВАНИЕ (должны быть определены до /{prompt_id})
# ===================================

@router.post("/{prompt_id}/view", response_model=dict)
async def view_prompt(
    prompt_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Увеличить счетчик просмотров промпта (публичный доступ)"""
    try:
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.increment_views(prompt_id)
        
        if success:
            return {"success": True, "message": "Просмотр учтён"}
        else:
            raise HTTPException(status_code=404, detail="Промпт не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка учёта просмотра: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}", response_model=PromptWithTags)
async def get_prompt(
    prompt_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение промпта по ID (публичный доступ)"""
    try:
        prompt_repo = get_prompt_repository()
        
        user_id = current_user["user_id"] if current_user else None
        prompt = await prompt_repo.get_prompt(prompt_id, user_id)
        
        if not prompt:
            raise HTTPException(status_code=404, detail="Промпт не найден")
        
        # Увеличиваем счётчик просмотров
        await prompt_repo.increment_views(prompt_id)
        
        return prompt
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PromptsResponse(BaseModel):
    """Ответ со списком промптов"""
    prompts: List[PromptWithTags]
    total: int
    page: int
    pages: int


@router.get("/", response_model=PromptsResponse)
async def get_prompts(
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
    """Получение списка промптов с фильтрацией (публичный доступ)"""
    try:
        logger.info(f"Запрос списка промптов: page={page}, limit={limit}, sort_by={sort_by}, sort_order={sort_order}")
        prompt_repo = get_prompt_repository()
        
        # Парсим теги
        tag_ids = None
        if tags:
            try:
                tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат тегов")
        
        # Создаём фильтры
        filters = PromptFilters(
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
        prompts, total = await prompt_repo.get_prompts(filters, user_id)
        
        logger.info(f"Получено промптов: {len(prompts)}, всего: {total}")
        
        pages = (total + limit - 1) // limit  # Округление вверх
        
        return PromptsResponse(
            prompts=prompts,
            total=total,
            page=page,
            pages=pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения списка промптов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{prompt_id}", response_model=dict)
async def update_prompt(
    prompt_id: int,
    prompt_data: PromptUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Обновление промпта (только автор)"""
    try:
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.update_prompt(
            prompt_id=prompt_id,
            prompt_data=prompt_data,
            author_id=current_user["user_id"]
        )
        
        if success:
            return {"success": True, "message": "Промпт успешно обновлён"}
        else:
            raise HTTPException(
                status_code=403, 
                detail="Недостаточно прав для редактирования этого промпта"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prompt_id}", response_model=dict)
async def delete_prompt(
    prompt_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Удаление промпта (только автор)"""
    try:
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.delete_prompt(
            prompt_id=prompt_id,
            author_id=current_user["user_id"]
        )
        
        if success:
            return {"success": True, "message": "Промпт успешно удалён"}
        else:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для удаления этого промпта"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# РЕЙТИНГИ И СТАТИСТИКА
# ===================================

class RatingRequest(BaseModel):
    """Запрос на оценку промпта"""
    rating: int


@router.post("/{prompt_id}/rate", response_model=dict)
async def rate_prompt(
    prompt_id: int,
    rating_request: RatingRequest,
    current_user: dict = Depends(get_current_user)
):
    """Оценка промпта пользователем"""
    try:
        if rating_request.rating < 1 or rating_request.rating > 5:
            raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")
        
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.rate_prompt(
            prompt_id=prompt_id,
            user_id=current_user["user_id"],
            rating=rating_request.rating
        )
        
        if success:
            return {"success": True, "message": "Оценка сохранена"}
        else:
            raise HTTPException(status_code=404, detail="Промпт не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка оценки промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prompt_id}/use", response_model=dict)
async def use_prompt(
    prompt_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Отметить использование промпта"""
    try:
        prompt_repo = get_prompt_repository()
        
        # Увеличиваем счетчик использований
        usage_success = await prompt_repo.increment_usage(prompt_id)
        
        if usage_success:
            return {"success": True, "message": "Использование учтено"}
        else:
            raise HTTPException(status_code=404, detail="Промпт не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка учёта использования: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}/stats", response_model=PromptStats)
async def get_prompt_stats(
    prompt_id: int,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение статистики промпта (публичный доступ)"""
    try:
        prompt_repo = get_prompt_repository()
        
        stats = await prompt_repo.get_prompt_stats(prompt_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Промпт не найден")
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# ЗАКЛАДКИ
# ===================================

@router.post("/{prompt_id}/bookmark", response_model=dict)
async def add_bookmark(
    prompt_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Добавить промпт в закладки"""
    try:
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.add_bookmark(prompt_id, current_user["user_id"])
        
        if success:
            return {"success": True, "message": "Добавлено в закладки"}
        else:
            raise HTTPException(status_code=404, detail="Промпт не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления в закладки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{prompt_id}/bookmark", response_model=dict)
async def remove_bookmark(
    prompt_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Удалить промпт из закладок"""
    try:
        prompt_repo = get_prompt_repository()
        
        success = await prompt_repo.remove_bookmark(prompt_id, current_user["user_id"])
        
        if success:
            return {"success": True, "message": "Удалено из закладок"}
        else:
            raise HTTPException(status_code=404, detail="Промпт не найден")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления из закладок: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my/bookmarks", response_model=PromptsResponse)
async def get_my_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Получение закладок текущего пользователя"""
    try:
        logger.info(f"Запрос закладок пользователя: {current_user.get('user_id', 'unknown')}, page={page}, limit={limit}")
        
        prompt_repo = get_prompt_repository()
        
        # Получаем ID промптов в закладках
        bookmark_ids, total = await prompt_repo.get_user_bookmarks(
            current_user["user_id"],
            limit=limit,
            offset=(page - 1) * limit
        )
        
        logger.info(f"Найдено закладок: {total}, IDs: {bookmark_ids}")
        
        if not bookmark_ids:
            logger.info("У пользователя нет закладок")
            return PromptsResponse(
                prompts=[],
                total=0,
                page=page,
                pages=0
            )
        
        # Получаем полные данные промптов
        prompts = []
        for prompt_id in bookmark_ids:
            prompt = await prompt_repo.get_prompt(prompt_id, current_user["user_id"])
            if prompt:
                prompts.append(prompt)
        
        pages = (total + limit - 1) // limit
        
        logger.info(f"Возвращаем {len(prompts)} промптов из закладок")
        
        return PromptsResponse(
            prompts=prompts,
            total=total,
            page=page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения закладок: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# ТЕГИ
# ===================================

@router.get("/tags/all", response_model=List[Tag])
async def get_all_tags(current_user: Optional[dict] = Depends(get_optional_user)):
    """Получение всех тегов (публичный доступ)"""
    try:
        tag_repo = get_tag_repository()
        tags = await tag_repo.get_all_tags()
        return tags
        
    except Exception as e:
        logger.error(f"Ошибка получения тегов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TagWithCount(BaseModel):
    """Тег с количеством промптов"""
    tag: Tag
    count: int


@router.get("/tags/popular", response_model=List[TagWithCount])
async def get_popular_tags(
    limit: int = Query(20, ge=1, le=50, description="Количество тегов"),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """Получение популярных тегов (публичный доступ)"""
    try:
        tag_repo = get_tag_repository()
        tags_with_counts = await tag_repo.get_popular_tags(limit)
        
        return [
            TagWithCount(tag=tag, count=count)
            for tag, count in tags_with_counts
        ]
        
    except Exception as e:
        logger.error(f"Ошибка получения популярных тегов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tags/", response_model=dict, status_code=201)
async def create_tag(
    tag_data: TagCreate,
    current_user: dict = Depends(get_current_user)
):
    """Создание нового тега"""
    try:
        tag_repo = get_tag_repository()
        
        tag_id = await tag_repo.create_tag(tag_data)
        
        if tag_id:
            return {"success": True, "tag_id": tag_id, "message": "Тег успешно создан"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при создании тега")
            
    except Exception as e:
        logger.error(f"Ошибка создания тега: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================
# МОИ ПРОМПТЫ
# ===================================

@router.get("/my/prompts", response_model=PromptsResponse)
async def get_my_prompts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Получение промптов текущего пользователя"""
    try:
        prompt_repo = get_prompt_repository()
        
        filters = PromptFilters(
            author_id=current_user["user_id"],
            sort_by="date",
            sort_order="desc",
            limit=limit,
            offset=(page - 1) * limit
        )
        
        prompts, total = await prompt_repo.get_prompts(filters, current_user["user_id"])
        
        pages = (total + limit - 1) // limit
        
        return PromptsResponse(
            prompts=prompts,
            total=total,
            page=page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения моих промптов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

