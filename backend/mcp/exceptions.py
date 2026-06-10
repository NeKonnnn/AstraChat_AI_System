"""Исключения MCP-платформы."""


class McpError(Exception):
    """Базовая ошибка MCP."""


class McpServerNotFoundError(McpError):
    """MCP-сервер не найден в конфигурации."""


class McpConnectionError(McpError):
    """Не удалось подключиться к MCP-серверу."""


class McpToolError(McpError):
    """Ошибка вызова MCP tool."""
