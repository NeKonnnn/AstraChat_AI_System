"""
Модуль инструментов для агентной архитектуры
Содержит все доступные tools для LangGraph оркестратора
"""

try:
    from backend.tools.agent_tools import AgentTools
    from backend.tools.prompt_tools import PromptTools
    from backend.tools.summarization_tools import SummarizationTools
except ModuleNotFoundError:
    # Если запущено из backend/, используем относительные импорты
    from tools.agent_tools import AgentTools
    from tools.prompt_tools import PromptTools
    from tools.summarization_tools import SummarizationTools


def get_all_tools():
    """
    Получение всех доступных инструментов для LangGraph оркестратора
    
    Returns:
        List: Список всех инструментов
    """
    all_tools = []
    
    # Инструменты агентов (основные, приоритетные)
    all_tools.extend(AgentTools.get_tools())
    
    # Инструменты для работы с промптами
    all_tools.extend(PromptTools.get_tools())
    
    # Инструменты для суммаризации
    all_tools.extend(SummarizationTools.get_tools())
    
    return all_tools


def get_tool_categories():
    """
    Получение инструментов по категориям
    
    Returns:
        Dict: Словарь с категориями инструментов
    """
    return {
        "agents": AgentTools.get_tools(),
        "prompts": PromptTools.get_tools(),
        "summarization": SummarizationTools.get_tools()
    }


def get_tools_info():
    """
    Получение информации о всех доступных инструментах
    
    Returns:
        Dict: Информация об инструментах
    """
    tools = get_all_tools()
    
    info = {
        "total_count": len(tools),
        "categories": {
            "agents": len(AgentTools.get_tools()),
            "prompts": len(PromptTools.get_tools()),
            "summarization": len(SummarizationTools.get_tools())
        },
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "category": _get_tool_category(tool.name)
            }
            for tool in tools
        ]
    }
    
    return info


def _get_tool_category(tool_name: str) -> str:
    """Определение категории инструмента по его имени"""
    categories = get_tool_categories()
    
    for category, tools in categories.items():
        if any(t.name == tool_name for t in tools):
            return category
    
    return "unknown"


__all__ = [
    'get_all_tools',
    'get_tool_categories',
    'get_tools_info',
    'AgentTools',
    'PromptTools',
    'SummarizationTools'
]