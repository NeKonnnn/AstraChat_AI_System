"""
MCP (Model Context Protocol) клиент для astrachat
Позволяет агенту подключаться к внешним инструментам и сервисам
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass
import subprocess
import os
import time
from backend.settings.cef_logger.cef_logger import log_cef_event

logger = logging.getLogger(__name__)

@dataclass
class MCPServer:
    """Конфигурация MCP сервера"""
    name: str
    type: str  # "stdio", "sse", "http"
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    enabled: bool = True

@dataclass
class MCPTool:
    """Информация о MCP инструменте"""
    name: str
    description: str
    parameters: Dict[str, Any]
    server: str

class MCPClient:
    """Клиент для подключения к MCP серверам"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.initialized = False
        
    def add_server(self, server: MCPServer):
        """Добавление MCP сервера"""
        self.servers[server.name] = server
        logger.info(f"Добавлен MCP сервер: {server.name} ({server.type})")
    
    def load_default_servers(self):
        """Загрузка стандартных MCP серверов"""
        
        # Файловая система
        filesystem_server = MCPServer(
            name="filesystem",
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", os.path.expanduser("~")],
            enabled=True
        )
        self.add_server(filesystem_server)
        
        # Веб-браузер (Playwright)
        browser_server = MCPServer(
            name="browser",
            type="stdio", 
            command="npx",
            args=["-y", "@modelcontextprotocol/server-playwright"],
            enabled=True
        )
        self.add_server(browser_server)
        
        # База данных SQLite
        sqlite_server = MCPServer(
            name="sqlite",
            type="stdio",
            command="npx", 
            args=["-y", "@modelcontextprotocol/server-sqlite"],
            enabled=True
        )
        self.add_server(sqlite_server)
        
        # Поиск в интернете
        search_server = MCPServer(
            name="search",
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            enabled=True
        )
        self.add_server(search_server)
    
    async def start_server(self, server_name: str) -> bool:
        """Запуск MCP сервера"""
        if server_name not in self.servers:
            logger.error(f"Сервер {server_name} не найден")
            return False
            
        server = self.servers[server_name]
        if not server.enabled:
            logger.info(f"Сервер {server_name} отключен")
            return False
            
        try:
            if server.type == "stdio":
                # Запуск stdio сервера
                process = subprocess.Popen(
                    [server.command] + server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                self.processes[server_name] = process
                logger.info(f"Запущен MCP сервер: {server_name}")
                return True
                
            elif server.type == "http":
                # HTTP серверы не требуют запуска процесса
                logger.info(f"HTTP MCP сервер {server_name} готов к использованию")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка запуска сервера {server_name}: {e}")
            return False
    
    async def stop_server(self, server_name: str):
        """Остановка MCP сервера"""
        if server_name in self.processes:
            process = self.processes[server_name]
            process.terminate()
            process.wait()
            del self.processes[server_name]
            logger.info(f"Остановлен MCP сервер: {server_name}")
    
    async def list_tools(self, server_name: str) -> List[MCPTool]:
        """Получение списка инструментов от MCP сервера"""
        if server_name not in self.processes:
            logger.error(f"Сервер {server_name} не запущен")
            return []
            
        try:
            process = self.processes[server_name]
            
            # Отправляем запрос на получение списка инструментов
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }
            
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            
            # Читаем ответ
            response_line = process.stdout.readline()
            if response_line:
                response = json.loads(response_line)
                if "result" in response:
                    tools = []
                    for tool_info in response["result"].get("tools", []):
                        tool = MCPTool(
                            name=tool_info["name"],
                            description=tool_info.get("description", ""),
                            parameters=tool_info.get("inputSchema", {}),
                            server=server_name
                        )
                        tools.append(tool)
                        self.tools[f"{server_name}.{tool.name}"] = tool
                    return tools
                    
        except Exception as e:
            logger.error(f"Ошибка получения инструментов от {server_name}: {e}")
            
        return []

    def _cef_mcp_target_extra(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        dhost = os.getenv("CEF_MCP_DHOST")
        if dhost:
            out["dhost"] = dhost
        if os.getenv("CEF_MCP_DPT"):
            try:
                out["dpt"] = int(os.getenv("CEF_MCP_DPT", "5432"))
            except ValueError:
                out["dpt"] = 5432
        if os.getenv("CEF_MCP_DUSER"):
            out["duser"] = os.getenv("CEF_MCP_DUSER")
        if os.getenv("CEF_MCP_DNtdom"):
            out["dntdom"] = os.getenv("CEF_MCP_DNtdom")
        return out
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        cef_request: Any = None,
        cef_user: Optional[Dict[str, Any]] = None,
        cef_conversation_id: Optional[str] = None,
        cef_tail: str = "",
    ) -> Any:
        """Вызов MCP инструмента"""
        if tool_name not in self.tools:
            logger.error(f"Инструмент {tool_name} не найден")
            return {"error": f"Инструмент {tool_name} не найден"}
            
        tool = self.tools[tool_name]
        server_name = tool.server
        
        if server_name not in self.processes:
            logger.error(f"Сервер {server_name} не запущен")
            return {"error": f"Сервер {server_name} не запущен"}
            
        try:
            started = time.perf_counter()
            server_part = tool_name.split(".", 1)[0] if "." in tool_name else server_name
            tool_part = tool.name
            _u = cef_user or {"username": "anonymous"}
            log_cef_event(
                "INT001",
                request=cef_request,
                current_user=_u,
                status_code=200,
                extra={
                    **self._cef_mcp_target_extra(),
                    "cs1": tool_part,
                    "cs1Label": "MCPToolName",
                    "cs2": cef_conversation_id or "-",
                    "cs2Label": "ConversationId",
                    "cs3": server_part,
                    "cs3Label": "MCPServer",
                    "cef_tail": cef_tail or "",
                },
            )
            process = self.processes[server_name]
            
            # Отправляем запрос на выполнение инструмента
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool.name,
                    "arguments": arguments
                }
            }
            
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            
            # Читаем ответ
            response_line = process.stdout.readline()
            if response_line:
                response = json.loads(response_line)
                if "result" in response:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    log_cef_event(
                        "INT002",
                        request=cef_request,
                        current_user=cef_user or {"username": "anonymous"},
                        status_code=200,
                        extra={
                            **self._cef_mcp_target_extra(),
                            "cs1": tool_part,
                            "cs1Label": "MCPToolName",
                            "cs3": server_part,
                            "cs3Label": "MCPServer",
                            "cn1": duration_ms,
                            "cn1Label": "DurationMs",
                            "cef_tail": cef_tail or "",
                        },
                    )
                    return response["result"]
                elif "error" in response:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    log_cef_event(
                        "INT002",
                        request=cef_request,
                        current_user=cef_user or {"username": "anonymous"},
                        outcome="error",
                        status_code=500,
                        extra={
                            **self._cef_mcp_target_extra(),
                            "cs1": tool_part,
                            "cs1Label": "MCPToolName",
                            "cs3": server_part,
                            "cs3Label": "MCPServer",
                            "cn1": duration_ms,
                            "cn1Label": "DurationMs",
                            "cef_tail": cef_tail or "",
                        },
                    )
                    return {"error": response["error"]}
                    
        except Exception as e:
            logger.error(f"Ошибка вызова инструмента {tool_name}: {e}")
            return {"error": f"Ошибка вызова инструмента: {str(e)}"}
    
    async def initialize(self) -> bool:
        """Инициализация MCP клиента"""
        try:
            # Загружаем стандартные серверы
            self.load_default_servers()
            
            # Запускаем серверы
            for server_name in self.servers:
                await self.start_server(server_name)
            
            # Получаем инструменты от всех серверов
            for server_name in self.servers:
                tools = await self.list_tools(server_name)
                logger.info(f"Получено {len(tools)} инструментов от сервера {server_name}")
            
            self.initialized = True
            logger.info("MCP клиент успешно инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации MCP клиента: {e}")
            return False
    
    async def cleanup(self):
        """Очистка ресурсов"""
        for server_name in list(self.processes.keys()):
            await self.stop_server(server_name)
        self.initialized = False
        logger.info("MCP клиент очищен")

# Глобальный экземпляр MCP клиента
mcp_client = None

async def initialize_mcp_client():
    """Инициализация MCP клиента"""
    global mcp_client
    try:
        mcp_client = MCPClient()
        success = await mcp_client.initialize()
        if success:
            logger.info("MCP клиент успешно инициализирован")
        return success
    except Exception as e:
        logger.error(f"Ошибка инициализации MCP клиента: {e}")
        return False

def get_mcp_client():
    """Получение экземпляра MCP клиента"""
    global mcp_client
    return mcp_client

# Интеграция с LangChain
def create_mcp_tools_for_langchain() -> List:
    """Создание инструментов LangChain из MCP инструментов"""
    from langchain_core.tools import tool
    
    tools = []
    
    if mcp_client and mcp_client.initialized:
        for tool_name, mcp_tool in mcp_client.tools.items():
            
            def create_tool_func(tool_name, mcp_tool):
                @tool
                def mcp_tool_wrapper(**kwargs) -> str:
                    """MCP инструмент: {description}"""
                    try:
                        result = asyncio.run(mcp_client.call_tool(tool_name, kwargs))
                        if isinstance(result, dict) and "error" in result:
                            return f"Ошибка: {result['error']}"
                        return str(result)
                    except Exception as e:
                        return f"Ошибка выполнения MCP инструмента: {str(e)}"
                
                # Обновляем описание
                mcp_tool_wrapper.__doc__ = f"MCP инструмент: {mcp_tool.description}"
                mcp_tool_wrapper.__name__ = f"mcp_{mcp_tool.name}"
                
                return mcp_tool_wrapper
            
            tools.append(create_tool_func(tool_name, mcp_tool))
    
    return tools
