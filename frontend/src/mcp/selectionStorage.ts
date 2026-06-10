/** Per-chat MCP tool_ids (OWUI-compatible: server:mcp:{id}). */

export const MCP_SELECTION_CHANGED_EVENT = 'astrachatMcpSelectionChanged';

export function mcpServerToolId(serverId: string): string {
  return `server:mcp:${serverId}`;
}

export function parseMcpServerIdFromToolId(toolId: string): string | null {
  const raw = (toolId || '').trim();
  if (raw.startsWith('server:mcp:')) return raw.slice('server:mcp:'.length);
  if (raw.startsWith('mcp:')) return raw.slice('mcp:'.length);
  return raw || null;
}

function storageKey(chatId: string): string {
  return `chat:${chatId}:mcp_tool_ids`;
}

export function getMcpToolIdsForChat(chatId: string): string[] {
  if (!chatId) return [];
  try {
    const raw = localStorage.getItem(storageKey(chatId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function setMcpToolIdsForChat(chatId: string, toolIds: string[]): void {
  if (!chatId) return;
  localStorage.setItem(storageKey(chatId), JSON.stringify(toolIds));
  window.dispatchEvent(new CustomEvent(MCP_SELECTION_CHANGED_EVENT, { detail: { chatId } }));
}

export function isMcpServerEnabledForChat(chatId: string, serverId: string): boolean {
  const tid = mcpServerToolId(serverId);
  return getMcpToolIdsForChat(chatId).includes(tid);
}

export function projectMcpChatKey(projectId: string): string {
  return `project:${projectId}`;
}

export function copyMcpToolIds(fromChatId: string, toChatId: string): void {
  const ids = getMcpToolIdsForChat(fromChatId);
  if (ids.length) {
    setMcpToolIdsForChat(toChatId, ids);
  }
}

export function toggleMcpServerForChat(chatId: string, serverId: string, enabled: boolean): string[] {
  const tid = mcpServerToolId(serverId);
  const current = getMcpToolIdsForChat(chatId);
  const next = enabled
    ? current.includes(tid)
      ? current
      : [...current, tid]
    : current.filter((x) => x !== tid);
  setMcpToolIdsForChat(chatId, next);
  return next;
}
