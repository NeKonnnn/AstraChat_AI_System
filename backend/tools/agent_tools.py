"""
Инструменты для работы с агентами
Эти tools вызывают специализированных агентов для выполнения задач
"""

import logging
import asyncio
from typing import Dict, Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _run_async_agent(agent_class, message: str, context: Dict[str, Any] = None):
    """
    Вспомогательная функция для запуска асинхронных агентов в синхронном контексте
    """
    try:
        # Получаем контекст из глобального состояния если не передан
        if context is None:
            context = _get_global_context()
        
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            # Если есть запущенный loop, создаем задачу
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_in_new_loop, agent_class, message, context)
                return future.result()
        except RuntimeError:
            # Нет запущенного loop, можем использовать asyncio.run
            return _run_in_new_loop(agent_class, message, context)
    except Exception as e:
        logger.error(f"Ошибка в _run_async_agent: {e}")
        return f"Ошибка выполнения агента: {str(e)}"

def _run_in_new_loop(agent_class, message: str, context: Dict[str, Any] = None):
    """Запуск агента в новом event loop"""
    async def _async_wrapper():
        agent = agent_class()
        agent_context = context if context is not None else {"history": []}
        return await agent.process_message(message, agent_context)
    
    return asyncio.run(_async_wrapper())

def _get_global_context():
    """Получение глобального контекста из main.py"""
    try:
        import backend.main as main_module
        context = {}
        
        # Получаем doc_processor
        if hasattr(main_module, 'doc_processor'):
            context['doc_processor'] = main_module.doc_processor
        
        # Получаем другие компоненты если нужно
        if hasattr(main_module, 'selected_model'):
            context['selected_model'] = main_module.selected_model
            
        return context
    except Exception as e:
        logger.warning(f"Не удалось получить глобальный контекст: {e}")
        return {}


@tool
def search_documents(query: str) -> str:
    """
    Поиск информации в загруженных документах.
    Используется для поиска по векторному хранилищу документов.
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Найденная информация из документов
    """
    try:
        logger.info(f"[TOOL] search_documents: {query}")
        try:
            from backend.agents.document_agent import DocumentAgent
        except ModuleNotFoundError:
            from agents.document_agent import DocumentAgent
        
        result = _run_async_agent(DocumentAgent, query)
        logger.info(f"[TOOL] search_documents результат: {len(result)} символов")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в search_documents: {e}")
        return f"Ошибка при поиске в документах: {str(e)}"


class AgentTools:
    """Класс для группировки инструментов агентов"""
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов агентов"""
        return [
            search_documents
        ]