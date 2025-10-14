"""
LangGraph агент для планирования и выполнения сложных задач
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class LangGraphAgent(BaseAgent):
    """Агент для планирования и выполнения сложных многошаговых задач"""
    
    def __init__(self):
        super().__init__(
            name="langgraph",
            description="Агент для планирования и выполнения сложных многошаговых задач"
        )
        
        self.capabilities = [
            "task_planning", "multi_step_execution", "workflow_management",
            "error_recovery", "state_tracking"
        ]
        self.langgraph_agent = None
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка сложных задач через LangGraph"""
        try:
            # Инициализируем LangGraph агент если не инициализирован
            if not self.langgraph_agent:
                await self._initialize_langgraph_agent()
            
            if not self.langgraph_agent:
                return "LangGraph агент недоступен. Проверьте настройки LangGraph."
            
            # Определяем, является ли задача сложной
            if not self._is_complex_task(message):
                return "Эта задача не требует планирования. Используйте обычного агента."
            
            # Выполняем задачу через LangGraph
            session_id = context.get("session_id", "default") if context else "default"
            result = await self.langgraph_agent.process_message(message, session_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка в LangGraphAgent: {e}")
            return f"Произошла ошибка при планировании задачи: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение через LangGraph"""
        message_lower = message.lower()
        
        complex_task_keywords = [
            "создай план", "выполни последовательность", "многошаговая задача",
            "сначала", "затем", "после этого", "в итоге", "пошагово",
            "анализ и", "сравни и", "найди и сохрани", "обработай и"
        ]
        
        return any(keyword in message_lower for keyword in complex_task_keywords)
    
    async def _initialize_langgraph_agent(self):
        """Инициализация LangGraph агента"""
        try:
            from backend.langgraph_agent import get_langgraph_agent
            self.langgraph_agent = get_langgraph_agent()
            
            if not self.langgraph_agent:
                from backend.langgraph_agent import initialize_langgraph_agent
                success = initialize_langgraph_agent()
                if success:
                    self.langgraph_agent = get_langgraph_agent()
                    logger.info("LangGraph агент инициализирован")
                else:
                    logger.warning("Не удалось инициализировать LangGraph агент")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации LangGraph агента: {e}")
    
    def _is_complex_task(self, message: str) -> bool:
        """Определение сложности задачи"""
        message_lower = message.lower()
        
        # Индикаторы сложных задач
        complexity_indicators = [
            # Многошаговые инструкции
            "сначала", "затем", "после этого", "в итоге", "пошагово",
            "шаг 1", "шаг 2", "первый", "второй", "третий",
            
            # Составные задачи
            "и затем", "а также", "плюс", "дополнительно", "кроме того",
            
            # Планирование
            "создай план", "составь план", "спланируй", "организуй",
            
            # Анализ и сравнение
            "сравни", "проанализируй", "изучи и", "найди и",
            
            # Обработка данных
            "обработай и", "сохрани и", "найди и сохрани", "создай и"
        ]
        
        # Подсчитываем количество индикаторов сложности
        complexity_score = sum(1 for indicator in complexity_indicators if indicator in message_lower)
        
        # Также проверяем длину сообщения
        is_long_message = len(message.split()) > 10
        
        return complexity_score >= 2 or is_long_message
    
    def get_langgraph_status(self) -> Dict[str, Any]:
        """Получение статуса LangGraph агента"""
        if not self.langgraph_agent:
            return {
                "initialized": False,
                "tools_available": 0,
                "memory_enabled": False
            }
        
        return {
            "initialized": True,
            "tools_available": len(self.langgraph_agent.tools) if hasattr(self.langgraph_agent, 'tools') else 0,
            "memory_enabled": hasattr(self.langgraph_agent, 'memory') and self.langgraph_agent.memory is not None,
            "graph_compiled": hasattr(self.langgraph_agent, 'graph') and self.langgraph_agent.graph is not None
        }
    
    async def create_task_plan(self, task_description: str) -> str:
        """Создание плана выполнения задачи"""
        try:
            if not self.langgraph_agent:
                return "LangGraph агент недоступен"
            
            # Создаем промпт для планирования
            planning_prompt = f"""
            Создай детальный план выполнения следующей задачи:
            
            {task_description}
            
            Разбей задачу на шаги и определи необходимые инструменты для каждого шага.
            """
            
            session_id = "planning_session"
            plan = await self.langgraph_agent.process_message(planning_prompt, session_id)
            
            return f"План выполнения задачи:\n\n{plan}"
            
        except Exception as e:
            logger.error(f"Ошибка создания плана: {e}")
            return f"Ошибка создания плана: {str(e)}"
    
    async def execute_workflow(self, workflow_description: str) -> str:
        """Выполнение рабочего процесса"""
        try:
            if not self.langgraph_agent:
                return "LangGraph агент недоступен"
            
            session_id = "workflow_session"
            result = await self.langgraph_agent.process_message(workflow_description, session_id)
            
            return f"Результат выполнения рабочего процесса:\n\n{result}"
            
        except Exception as e:
            logger.error(f"Ошибка выполнения рабочего процесса: {e}")
            return f"Ошибка выполнения рабочего процесса: {str(e)}"

