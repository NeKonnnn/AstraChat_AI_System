from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from app.models.schemas import ChatResponse, Message

logger = None

class BaseLLMHandler(ABC):
    """Абстрактный базовый класс для всех LLM handlers."""
    
    def __init__(self):
        self.is_initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Асинхронная инициализация модели."""
        pass
    
    @abstractmethod
    def is_loaded(self) -> bool:
        """Проверка, загружена ли модель."""
        pass
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Union[ChatResponse, AsyncGenerator[str, None]]:
        """Универсальный метод для генерации ответа."""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """Очистка ресурсов модели."""
        pass




