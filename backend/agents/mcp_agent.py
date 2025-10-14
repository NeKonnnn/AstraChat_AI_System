"""
MCP агент для интеграции с внешними сервисами
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MCPAgent(BaseAgent):
    """Агент для работы с MCP серверами"""
    
    def __init__(self):
        super().__init__(
            name="mcp",
            description="Агент для работы с внешними сервисами через MCP"
        )
        
        self.capabilities = [
            "filesystem_access", "web_browser", "database_operations", 
            "search_services", "external_tools"
        ]
        self.mcp_client = None
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка запросов через MCP серверы"""
        try:
            # Инициализируем MCP клиент если не инициализирован
            if not self.mcp_client:
                await self._initialize_mcp_client()
            
            if not self.mcp_client or not self.mcp_client.initialized:
                return "MCP клиент недоступен. Проверьте настройки MCP серверов."
            
            # Определяем тип задачи и выбираем подходящий MCP сервер
            mcp_task = self._determine_mcp_task(message)
            
            if not mcp_task:
                return "Не удалось определить подходящий MCP сервер для данной задачи."
            
            # Выполняем задачу через MCP
            result = await self._execute_mcp_task(mcp_task, message)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка в MCPAgent: {e}")
            return f"Произошла ошибка при работе с MCP серверами: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Определяет, может ли агент обработать сообщение через MCP"""
        message_lower = message.lower()
        
        mcp_keywords = [
            "файловая система", "работа с файлами", "браузер", "веб-страница",
            "база данных", "sqlite", "поиск в интернете", "mcp", "внешний сервис"
        ]
        
        return any(keyword in message_lower for keyword in mcp_keywords)
    
    async def _initialize_mcp_client(self):
        """Инициализация MCP клиента"""
        try:
            from backend.mcp_client import get_mcp_client
            self.mcp_client = get_mcp_client()
            
            if not self.mcp_client:
                from backend.mcp_client import initialize_mcp_client
                success = await initialize_mcp_client()
                if success:
                    self.mcp_client = get_mcp_client()
                    logger.info("MCP клиент инициализирован для агента")
                else:
                    logger.warning("Не удалось инициализировать MCP клиент")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации MCP клиента: {e}")
    
    def _determine_mcp_task(self, message: str) -> Optional[str]:
        """Определение типа MCP задачи"""
        message_lower = message.lower()
        
        # Файловая система
        if any(word in message_lower for word in ["файл", "директория", "папка", "читать файл", "записать файл"]):
            return "filesystem"
        
        # Веб-браузер
        if any(word in message_lower for word in ["браузер", "веб-страница", "открыть сайт", "скриншот"]):
            return "browser"
        
        # База данных
        if any(word in message_lower for word in ["база данных", "sqlite", "sql", "запрос к бд"]):
            return "sqlite"
        
        # Поиск
        if any(word in message_lower for word in ["поиск в интернете", "найти в интернете", "веб-поиск"]):
            return "search"
        
        return None
    
    async def _execute_mcp_task(self, task_type: str, message: str) -> str:
        """Выполнение MCP задачи"""
        try:
            if task_type == "filesystem":
                return await self._handle_filesystem_task(message)
            elif task_type == "browser":
                return await self._handle_browser_task(message)
            elif task_type == "sqlite":
                return await self._handle_sqlite_task(message)
            elif task_type == "search":
                return await self._handle_search_task(message)
            else:
                return f"Неподдерживаемый тип MCP задачи: {task_type}"
                
        except Exception as e:
            logger.error(f"Ошибка выполнения MCP задачи {task_type}: {e}")
            return f"Ошибка выполнения MCP задачи: {str(e)}"
    
    async def _handle_filesystem_task(self, message: str) -> str:
        """Обработка задач файловой системы"""
        try:
            # Простые команды файловой системы
            if "список файлов" in message.lower() or "показать директорию" in message.lower():
                # Получаем список файлов в домашней директории
                result = await self.mcp_client.call_tool("filesystem.list_directory", {
                    "path": "~"
                })
                return f"Содержимое домашней директории:\n{result}"
            
            elif "читать файл" in message.lower():
                # Извлекаем путь к файлу из сообщения
                # Это упрощенная версия, в реальности нужен более сложный парсинг
                return "Для чтения файла укажите полный путь к файлу"
            
            else:
                return "Доступные команды файловой системы:\n- список файлов\n- читать файл [путь]\n- записать файл [путь] [содержимое]"
                
        except Exception as e:
            return f"Ошибка работы с файловой системой: {str(e)}"
    
    async def _handle_browser_task(self, message: str) -> str:
        """Обработка задач браузера"""
        try:
            if "открыть сайт" in message.lower() or "перейти на" in message.lower():
                # Извлекаем URL из сообщения
                # Это упрощенная версия
                return "Для открытия сайта укажите URL, например: 'открыть сайт https://example.com'"
            
            elif "скриншот" in message.lower():
                result = await self.mcp_client.call_tool("browser.take_screenshot", {})
                return f"Скриншот сделан: {result}"
            
            else:
                return "Доступные команды браузера:\n- открыть сайт [URL]\n- скриншот\n- получить текст страницы"
                
        except Exception as e:
            return f"Ошибка работы с браузером: {str(e)}"
    
    async def _handle_sqlite_task(self, message: str) -> str:
        """Обработка задач базы данных"""
        try:
            if "создать таблицу" in message.lower():
                return "Для создания таблицы укажите SQL команду"
            
            elif "выполнить запрос" in message.lower():
                return "Для выполнения SQL запроса укажите команду"
            
            else:
                return "Доступные команды базы данных:\n- создать таблицу [SQL]\n- выполнить запрос [SQL]\n- показать таблицы"
                
        except Exception as e:
            return f"Ошибка работы с базой данных: {str(e)}"
    
    async def _handle_search_task(self, message: str) -> str:
        """Обработка задач поиска"""
        try:
            # Извлекаем поисковый запрос
            query = message.replace("поиск в интернете", "").replace("найти в интернете", "").strip()
            
            if query:
                result = await self.mcp_client.call_tool("search.search", {
                    "query": query,
                    "num_results": 5
                })
                return f"Результаты поиска по запросу '{query}':\n{result}"
            else:
                return "Укажите поисковый запрос после команды поиска"
                
        except Exception as e:
            return f"Ошибка поиска в интернете: {str(e)}"
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """Получение статуса MCP серверов"""
        if not self.mcp_client:
            return {
                "initialized": False,
                "servers": 0,
                "tools": 0
            }
        
        return {
            "initialized": self.mcp_client.initialized,
            "servers": len(self.mcp_client.servers),
            "tools": len(self.mcp_client.tools),
            "active_processes": len(self.mcp_client.processes)
        }

