"""
Базовый класс для всех агентов в системе astrachat
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# ============================================================================
# Утилита для получения правильной версии ask_agent
# ============================================================================

def get_ask_agent():
    """
    Получить версию ask_agent из agent_llm_svc.py.
    Эта функция должна использоваться всеми агентами для единообразия.
    Всегда использует agent_llm_svc.py как основной источник.
    """
    # Всегда используем agent_llm_svc как основной источник
    try:
        from backend.agent_llm_svc import ask_agent
        logger.debug("[BaseAgent] Используется ask_agent из agent_llm_svc")
        return ask_agent
    except (ImportError, ModuleNotFoundError) as e:
        logger.warning(f"[BaseAgent] Не удалось импортировать agent_llm_svc: {e}, пробуем agent.py как fallback")
        # Используем agent_llm_svc (работает через llm-svc без загрузки модели)
        try:
            from backend.agent_llm_svc import ask_agent
            logger.debug("[BaseAgent] Используется ask_agent из agent_llm_svc")
            return ask_agent
        except ModuleNotFoundError:
            from agent_llm_svc import ask_agent
            logger.debug("[BaseAgent] Используется ask_agent_llm_svc (относительный импорт)")
            return ask_agent

class BaseAgent(ABC):
    """Базовый класс для всех агентов"""
    
    def __init__(self, name: str, description: str, tools: List = None):
        self.name = name
        self.description = description
        self.tools = tools or []
        self.capabilities = []
        self.is_active = True
        
    @abstractmethod
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка сообщения пользователя"""
        pass
    
    @abstractmethod
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать данное сообщение"""
        pass
    
    def get_capabilities(self) -> List[str]:
        """Возвращает список возможностей агента"""
        return self.capabilities
    
    def add_tool(self, tool):
        """Добавление инструмента к агенту"""
        self.tools.append(tool)
    
    def get_tools(self) -> List:
        """Получение списка инструментов агента"""
        return self.tools
    
    def activate(self):
        """Активация агента"""
        self.is_active = True
    
    def deactivate(self):
        """Деактивация агента"""
        self.is_active = False
    
    def get_info(self) -> Dict[str, Any]:
        """Получение информации об агенте"""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "tools_count": len(self.tools),
            "is_active": self.is_active
        }

