"""
Модели данных для галереи промптов в PostgreSQL
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Prompt(BaseModel):
    """Модель промпта"""
    
    id: Optional[int] = Field(None, description="ID промпта (автоинкремент)")
    title: str = Field(..., description="Название промпта", min_length=3, max_length=255)
    content: str = Field(..., description="Текст промпта", min_length=10)
    description: Optional[str] = Field(None, description="Описание промпта", max_length=1000)
    author_id: str = Field(..., description="ID пользователя-автора")
    author_name: str = Field(..., description="Имя автора")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    is_public: bool = Field(True, description="Публичный/приватный")
    usage_count: int = Field(0, description="Количество использований")
    views_count: int = Field(0, description="Количество просмотров")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Анализ бизнес-метрик",
                "content": "Ты - эксперт по бизнес-аналитике. Проанализируй следующие данные...",
                "description": "Промпт для глубокого анализа бизнес-показателей",
                "author_id": "user123",
                "author_name": "Иван Иванов",
                "is_public": True
            }
        }


class Tag(BaseModel):
    """Модель тега"""
    
    id: Optional[int] = Field(None, description="ID тега (автоинкремент)")
    name: str = Field(..., description="Название тега", min_length=2, max_length=100)
    description: Optional[str] = Field(None, description="Описание тега", max_length=500)
    color: Optional[str] = Field(None, description="Цвет для UI (hex)", pattern="^#[0-9A-Fa-f]{6}$")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Бизнес-аналитика",
                "description": "Промпты для анализа бизнес-показателей",
                "color": "#2196f3"
            }
        }


class PromptWithTags(Prompt):
    """Модель промпта с тегами и рейтингом"""
    
    tags: List[Tag] = Field(default_factory=list, description="Теги промпта")
    average_rating: float = Field(0.0, description="Средний рейтинг (1-5)")
    total_votes: int = Field(0, description="Общее количество голосов")
    user_rating: Optional[int] = Field(None, description="Оценка текущего пользователя")
    is_bookmarked: bool = Field(False, description="Добавлен ли в закладки текущим пользователем")


class PromptRating(BaseModel):
    """Модель рейтинга промпта"""
    
    id: Optional[int] = Field(None, description="ID рейтинга (автоинкремент)")
    prompt_id: int = Field(..., description="ID промпта")
    user_id: str = Field(..., description="ID пользователя")
    rating: int = Field(..., description="Оценка (1-5)", ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Дата обновления")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt_id": 1,
                "user_id": "user123",
                "rating": 5
            }
        }


class PromptCreate(BaseModel):
    """Модель для создания промпта"""
    
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: bool = Field(True)
    tag_ids: List[int] = Field(default_factory=list, description="ID существующих тегов")
    new_tags: List[str] = Field(default_factory=list, description="Новые теги для создания")


class PromptUpdate(BaseModel):
    """Модель для обновления промпта"""
    
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = Field(None)
    tag_ids: Optional[List[int]] = Field(None, description="ID существующих тегов")
    new_tags: Optional[List[str]] = Field(None, description="Новые теги для создания")


class PromptFilters(BaseModel):
    """Фильтры для поиска промптов"""
    
    search_query: Optional[str] = Field(None, description="Поисковый запрос")
    tag_ids: Optional[List[int]] = Field(None, description="Фильтр по тегам")
    author_id: Optional[str] = Field(None, description="Фильтр по автору")
    min_rating: Optional[float] = Field(None, description="Минимальный рейтинг", ge=0, le=5)
    sort_by: str = Field("rating", description="Поле сортировки")
    sort_order: str = Field("desc", description="Порядок сортировки (asc/desc)")
    limit: int = Field(20, description="Количество результатов", ge=1, le=100)
    offset: int = Field(0, description="Смещение для пагинации", ge=0)


class TagCreate(BaseModel):
    """Модель для создания тега"""
    
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class PromptStats(BaseModel):
    """Статистика промпта"""
    
    prompt_id: int
    views_count: int
    usage_count: int
    average_rating: float
    total_votes: int
    rating_distribution: Dict[int, int] = Field(
        default_factory=dict, 
        description="Распределение оценок {1: count, 2: count, ...}"
    )