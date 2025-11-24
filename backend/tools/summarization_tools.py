"""
Инструменты для суммаризации текстов и документов
"""

import logging
from typing import Dict, Any
from langchain_core.tools import tool

try:
    from backend.agents.summarization_agent import SummarizationAgent
    from backend.tools.prompt_tools import _run_async_agent
except ModuleNotFoundError:
    from agents.summarization_agent import SummarizationAgent
    from tools.prompt_tools import _run_async_agent

logger = logging.getLogger("Backend")

@tool
def summarize_text(query: str) -> str:
    """
    Создание краткого резюме текста или документа.
    Создает структурированное саммари на основе текста из чата или прикрепленного документа.
    
    Используй этот инструмент, когда пользователь просит:
    - Сделать саммари документа или текста
    - Создать краткое резюме
    - Подвести итоги
    - Сделать краткую версию
    
    Args:
        query: Запрос на суммаризацию с деталями и требованиями
        
    Returns:
        Краткое саммари текста или документа
    """
    logger.info(f"[summarize_text] Вызов инструмента суммаризации: {query[:100]}...")
    
    try:
        # Получаем контекст из глобального хранилища
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        context = get_tool_context()
        result = _run_async_agent(SummarizationAgent, query, context)
        logger.info(f"[summarize_text] Суммаризация завершена успешно")
        return result
    except Exception as e:
        error_msg = f"Ошибка при суммаризации: {str(e)}"
        logger.error(f"[summarize_text] {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return f"{error_msg}"

@tool
def extract_key_points(query: str) -> str:
    """
    Извлечение ключевой информации и важных моментов из текста или документа.
    Анализирует текст и выделяет самую важную информацию: факты, цифры, даты, имена.
    
    Используй этот инструмент, когда пользователь просит:
    - Выделить ключевую информацию
    - Найти важные моменты
    - Показать главное
    - Извлечь основные факты
    - Highlights или key points
    
    Args:
        query: Запрос с указанием типа информации для извлечения
        
    Returns:
        Структурированная ключевая информация
    """
    logger.info(f"[extract_key_points] Извлечение ключевых моментов: {query[:100]}...")
    
    try:
        # Получаем контекст из глобального хранилища
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        context = get_tool_context()
        
        # Добавляем подсказку в запрос для правильного определения типа
        enhanced_query = f"Извлеки ключевую информацию: {query}"
        result = _run_async_agent(SummarizationAgent, enhanced_query, context)
        logger.info(f"[extract_key_points] Извлечение завершено успешно")
        return result
    except Exception as e:
        error_msg = f"Ошибка при извлечении ключевой информации: {str(e)}"
        logger.error(f"[extract_key_points] {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return f"{error_msg}"

@tool
def create_bullet_summary(query: str) -> str:
    """
    Создание саммари в виде маркированного или нумерованного списка.
    Структурирует информацию в удобный список основных пунктов и тезисов.
    
    Используй этот инструмент, когда пользователь просит:
    - Создать список основных пунктов
    - Сделать саммари тезисами
    - Показать в виде bullets
    - Структурировать по пунктам
    
    Args:
        query: Запрос с указанием требований к списку
        
    Returns:
        Саммари в виде структурированного списка
    """
    logger.info(f"[create_bullet_summary] Создание списка: {query[:100]}...")
    
    try:
        # Получаем контекст из глобального хранилища
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        context = get_tool_context()
        
        # Добавляем подсказку в запрос для правильного определения типа
        enhanced_query = f"Создай краткий список основных пунктов: {query}"
        result = _run_async_agent(SummarizationAgent, enhanced_query, context)
        logger.info(f"[create_bullet_summary] Список создан успешно")
        return result
    except Exception as e:
        error_msg = f"Ошибка при создании списка: {str(e)}"
        logger.error(f"[create_bullet_summary] {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return f"{error_msg}"

@tool
def summarize_conversation(query: str) -> str:
    """
    Создание саммари истории диалога или чата.
    Анализирует историю сообщений и создает резюме беседы с основными темами и выводами.
    
    Используй этот инструмент, когда пользователь просит:
    - Подвести итоги диалога
    - Сделать саммари чата
    - Резюме беседы
    - Что мы обсуждали
    
    Args:
        query: Запрос на суммаризацию с указанием фокуса
        
    Returns:
        Саммари истории диалога
    """
    logger.info(f"[summarize_conversation] Суммаризация диалога: {query[:100]}...")
    
    try:
        # Получаем контекст из глобального хранилища
        try:
            from backend.tools.prompt_tools import get_tool_context
        except ModuleNotFoundError:
            from tools.prompt_tools import get_tool_context
        
        context = get_tool_context()
        
        # Добавляем подсказку в запрос для правильного определения типа
        enhanced_query = f"Создай саммари нашего диалога: {query}"
        result = _run_async_agent(SummarizationAgent, enhanced_query, context)
        logger.info(f"[summarize_conversation] Саммари диалога создано успешно")
        return result
    except Exception as e:
        error_msg = f"Ошибка при суммаризации диалога: {str(e)}"
        logger.error(f"[summarize_conversation] {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        return f"{error_msg}"


# ============================================================================
# Класс для группировки инструментов суммаризации
# ============================================================================

class SummarizationTools:
    """Класс для группировки инструментов суммаризации"""
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов для суммаризации"""
        return [
            summarize_text,
            extract_key_points,
            create_bullet_summary,
            summarize_conversation
        ]
