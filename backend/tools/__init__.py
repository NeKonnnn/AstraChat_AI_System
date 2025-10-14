"""
Модуль инструментов для агентной архитектуры
Содержит все доступные tools для LangGraph оркестратора
"""

try:
    from backend.tools.agent_tools import AgentTools
    from backend.tools.file_tools import FileTools
    from backend.tools.web_tools import WebTools
    from backend.tools.calculation_tools import CalculationTools
    from backend.tools.system_tools import SystemTools
except ModuleNotFoundError:
    # Если запущено из backend/, используем относительные импорты
    from tools.agent_tools import AgentTools
    from tools.file_tools import FileTools
    from tools.web_tools import WebTools
    from tools.calculation_tools import CalculationTools
    from tools.system_tools import SystemTools


def get_all_tools():
    """
    Получение всех доступных инструментов для LangGraph оркестратора
    
    Returns:
        List: Список всех инструментов
    """
    all_tools = []
    
    # Инструменты агентов (основные, приоритетные)
    all_tools.extend(AgentTools.get_tools())
    
    # Инструменты для работы с файлами
    all_tools.extend(FileTools.get_tools())
    
    # Инструменты для веб-поиска
    all_tools.extend(WebTools.get_tools())
    
    # Инструменты для вычислений
    all_tools.extend(CalculationTools.get_tools())
    
    # Системные инструменты
    all_tools.extend(SystemTools.get_tools())
    
    return all_tools


def get_tool_categories():
    """
    Получение инструментов по категориям
    
    Returns:
        Dict: Словарь с категориями инструментов
    """
    return {
        "agents": AgentTools.get_tools(),
        "files": FileTools.get_tools(),
        "web": WebTools.get_tools(),
        "calculations": CalculationTools.get_tools(),
        "system": SystemTools.get_tools()
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
            "files": len(FileTools.get_tools()),
            "web": len(WebTools.get_tools()),
            "calculations": len(CalculationTools.get_tools()),
            "system": len(SystemTools.get_tools())
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
    'FileTools',
    'WebTools',
    'CalculationTools',
    'SystemTools'
]
