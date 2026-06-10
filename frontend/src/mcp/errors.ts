/** Generic MCP API error messages (F-10). */

export class McpApiError extends Error {
  status: number;
  serverId?: string;

  constructor(message: string, status: number, serverId?: string) {
    super(message);
    this.name = 'McpApiError';
    this.status = status;
    this.serverId = serverId;
  }
}

export function formatMcpApiError(status: number, detail: string, serverId?: string): string {
  const d = (detail || '').trim();
  if (status === 401) {
    return 'Требуется повторный вход в систему';
  }
  if (status === 403) {
    return d || 'Недостаточно прав для операции MCP';
  }
  if (status === 404) {
    if (serverId) {
      return `MCP-сервер «${serverId}» не найден в конфигурации`;
    }
    return d || 'MCP-сервер не найден в конфигурации';
  }
  if (status === 503) {
    if (serverId) {
      return `MCP-сервер «${serverId}» недоступен`;
    }
    return d || 'MCP-платформа недоступна';
  }
  return d || `Ошибка MCP API (${status})`;
}

export function extractServerIdFromPath(path: string): string | undefined {
  const m = path.match(/\/api\/mcp\/servers\/([^/]+)/);
  return m?.[1] ? decodeURIComponent(m[1]) : undefined;
}
