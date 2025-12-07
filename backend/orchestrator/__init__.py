"""
Оркестратор агентной архитектуры
Использует LangGraph Orchestrator для управления агентами и инструментами
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Оркестратор для управления агентной архитектурой
    Обертка над LangGraph Orchestrator для обратной совместимости с API
    """
    
    def __init__(self):
        self.langgraph_orchestrator = None
        self.is_initialized = False
        self.mode = "direct"  # "agent", "direct" или "multi-llm" - по умолчанию прямой режим
        self.multi_llm_models = []  # Список выбранных моделей для режима multi-llm
        
    async def initialize(self) -> bool:
        """Инициализация оркестратора"""
        try:
            logger.info("Инициализация AgentOrchestrator...")
            
            # Инициализируем LangGraph оркестратор
            try:
                from backend.agents.langgraph_orchestrator import (
                    initialize_langgraph_orchestrator,
                    get_langgraph_orchestrator
                )
            except ModuleNotFoundError:
                # Если запущено из backend/, используем относительный импорт
                from agents.langgraph_orchestrator import (
                    initialize_langgraph_orchestrator,
                    get_langgraph_orchestrator
                )
            
            initialize_langgraph_orchestrator()
            self.langgraph_orchestrator = get_langgraph_orchestrator()
            
            if self.langgraph_orchestrator:
                logger.info("LangGraph Orchestrator инициализирован")
                self.is_initialized = True
                return True
            else:
                logger.error("Не удалось получить экземпляр LangGraph Orchestrator")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка инициализации оркестратора: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def process_message(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        context: Dict[str, Any] = None
    ) -> str:
        """Обработка сообщения через агентную архитектуру"""
        logger.info("="*70)
        logger.info("🔄 AgentOrchestrator.process_message ВЫЗВАН")
        logger.info(f"📝 Запрос: {message[:100]}...")
        logger.info(f"🔧 Текущий режим: {self.mode}")
        logger.info(f"✅ Инициализирован: {self.is_initialized}")
        logger.info("="*70)
        
        if not self.is_initialized and self.mode != "multi-llm":
            logger.info("⚠️ Оркестратор не инициализирован, выполняем инициализацию...")
            await self.initialize()
        
        try:
            if self.mode == "agent":
                # Используем агентную архитектуру (LangGraph)
                logger.info("="*70)
                logger.info("✅ АГЕНТНЫЙ РЕЖИМ АКТИВИРОВАН")
                logger.info("🤖 Передаем запрос в LangGraph Orchestrator")
                logger.info("="*70)
                
                if not self.langgraph_orchestrator:
                    logger.error("❌ LangGraph Orchestrator не инициализирован")
                    return "Ошибка: агентная архитектура не инициализирована"
                
                logger.info("🚀 Вызов langgraph_orchestrator.process_message...")
                result = await self.langgraph_orchestrator.process_message(
                    message,
                    history=history or [],
                    context=context or {}
                )
                logger.info(f"✅ LangGraph Orchestrator вернул ответ: {len(result) if result else 0} символов")
                return result
            elif self.mode == "multi-llm":
                # Режим с несколькими LLM - возвращаем специальный маркер
                # Фактическая обработка происходит в WebSocket обработчике
                logger.info(f"РЕЖИМ MULTI-LLM: Обработка через несколько моделей")
                return "MULTI_LLM_MODE"
            else:
                # Используем прямое обращение к LLM
                logger.info(f"ПРЯМОЙ РЕЖИМ: Обращение напрямую к LLM")
                return await self._direct_llm_call(message, history, context)
                
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Произошла ошибка при обработке запроса: {str(e)}"
    
    async def _direct_llm_call(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        context: Dict[str, Any] = None
    ) -> str:
        """Прямое обращение к LLM модели"""
        try:
            try:
                from backend.agent import ask_agent
            except ModuleNotFoundError:
                from agent import ask_agent
            
            response = ask_agent(
                message,
                history=history or [],
                streaming=False,
                model_path=context.get("selected_model") if context else None
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка прямого вызова LLM: {e}")
            return f"Ошибка при обращении к модели: {str(e)}"
    
    def set_mode(self, mode: str):
        """Установка режима работы"""
        if mode in ["agent", "direct", "multi-llm"]:
            self.mode = mode
            logger.info(f"Режим работы изменен на: {mode}")
        else:
            logger.warning(f"Недопустимый режим: {mode}")
    
    def set_multi_llm_models(self, models: List[str]):
        """Установка списка моделей для режима multi-llm"""
        self.multi_llm_models = models
        logger.info(f"Установлены модели для режима multi-llm: {models}")
    
    def get_multi_llm_models(self) -> List[str]:
        """Получение списка моделей для режима multi-llm"""
        return self.multi_llm_models
    
    def get_mode(self) -> str:
        """Получение текущего режима работы"""
        return self.mode
    
    def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных агентов (теперь это инструменты)
        Для обратной совместимости с API
        """
        if not self.langgraph_orchestrator:
            return []
        
        # Возвращаем инструменты как "агентов" для совместимости
        return self.langgraph_orchestrator.get_available_tools()
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Получение списка доступных инструментов"""
        if not self.langgraph_orchestrator:
            return []
        
        return self.langgraph_orchestrator.get_available_tools()
    
    def set_agent_status(self, agent_id: str, is_active: bool):
        """
        Установка статуса агента (теперь инструмента)
        Для обратной совместимости с API
        """
        if not self.langgraph_orchestrator:
            logger.warning("LangGraph Orchestrator не инициализирован")
            return
        
        self.langgraph_orchestrator.set_tool_status(agent_id, is_active)
    
    def set_tool_status(self, tool_name: str, is_active: bool):
        """Установка статуса инструмента"""
        if not self.langgraph_orchestrator:
            logger.warning("LangGraph Orchestrator не инициализирован")
            return
        
        self.langgraph_orchestrator.set_tool_status(tool_name, is_active)
    
    def get_all_agent_statuses(self) -> Dict[str, bool]:
        """
        Получение статусов всех агентов (теперь инструментов)
        Для обратной совместимости с API
        """
        if not self.langgraph_orchestrator:
            return {}
        
        return self.langgraph_orchestrator.get_all_tool_statuses()
    
    def get_all_tool_statuses(self) -> Dict[str, bool]:
        """Получение статусов всех инструментов"""
        if not self.langgraph_orchestrator:
            return {}
        
        return self.langgraph_orchestrator.get_all_tool_statuses()
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса оркестратора"""
        available_tools = self.get_available_tools()
        
        return {
            "is_initialized": self.is_initialized,
            "mode": self.mode,
            "available_agents": len(available_tools),  # Для совместимости
            "available_tools": len(available_tools),
            "orchestrator_type": "LangGraph",
            "orchestrator_active": self.is_orchestrator_active()
        }
    
    def set_orchestrator_status(self, is_active: bool):
        """Установка статуса активности оркестратора"""
        if self.langgraph_orchestrator:
            self.langgraph_orchestrator.set_orchestrator_status(is_active)
        logger.info(f"Оркестратор {'включен' if is_active else 'отключен'}")
    
    def is_orchestrator_active(self) -> bool:
        """Проверка активности оркестратора"""
        if self.langgraph_orchestrator:
            return self.langgraph_orchestrator.is_orchestrator_active()
        return self.is_initialized


# Глобальный экземпляр оркестратора
agent_orchestrator: Optional[AgentOrchestrator] = None


async def initialize_agent_orchestrator():
    """Инициализация глобального оркестратора"""
    global agent_orchestrator
    try:
        logger.info("="*70)
        logger.info("Инициализация глобального AgentOrchestrator...")
        logger.info("="*70)
        
        agent_orchestrator = AgentOrchestrator()
        success = await agent_orchestrator.initialize()
        
        if success:
            logger.info("="*70)
            logger.info("Глобальный AgentOrchestrator успешно инициализирован")
            logger.info("="*70)
        else:
            logger.error("="*70)
            logger.error("Ошибка инициализации глобального AgentOrchestrator")
            logger.error("="*70)
        
        return success
        
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def get_agent_orchestrator() -> Optional[AgentOrchestrator]:
    """Получение экземпляра оркестратора"""
    global agent_orchestrator
    return agent_orchestrator
