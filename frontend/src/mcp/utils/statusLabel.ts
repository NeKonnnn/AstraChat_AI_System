import type { McpPlatformStatus, McpServerStatus } from '../types';

type McpStatusLegacy = McpPlatformStatus & { servers?: McpServerStatus[] | number };

/** Единый label для aggregate MCP status (AgentsSettings, AgentArchitectureSettings). */
export function formatMcpAggregateLabel(status: McpPlatformStatus): string {
  const tools = status.tools_total ?? status.tools ?? 0;
  const raw = status as McpStatusLegacy;

  if (Array.isArray(raw.servers)) {
    const connected =
      status.servers_connected ?? raw.servers.filter((s) => s.connected).length;
    const total = status.servers_total ?? status.total_servers ?? raw.servers.length;
    return `MCP: ${connected}/${total} серверов, ${tools} инструментов`;
  }

  if (typeof raw.servers === 'number') {
    return `MCP: ${raw.servers} серверов, ${tools} инструментов`;
  }

  const total = status.servers_total ?? status.total_servers ?? 0;
  const connected = status.servers_connected ?? 0;
  return `MCP: ${connected}/${total} серверов, ${tools} инструментов`;
}

export function isMcpPlatformHealthy(status: McpPlatformStatus): boolean {
  if (status.initialized != null) return Boolean(status.initialized);
  if (status.enabled != null) return Boolean(status.enabled);
  const raw = status as McpStatusLegacy;
  if (Array.isArray(raw.servers)) {
    return raw.servers.some((s) => s.connected);
  }
  return Boolean(status.servers_connected);
}
