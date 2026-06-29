import type { McpToolCallRecord } from '../types';

/** Нормализует событие MCP с backend/socket к формату UI. */
export function normalizeMcpToolCallRecord(raw: Record<string, unknown>): McpToolCallRecord {
  const eventType = String(raw.type || '');
  return {
    type: eventType === 'mcp_tool_end' ? 'mcp_tool_end' : 'mcp_tool_start',
    server_id: String(raw.server_id || ''),
    tool: String(raw.tool || ''),
    qualified_name: String(raw.qualified_name || raw.tool || ''),
    call_id: raw.call_id ? String(raw.call_id) : undefined,
    arguments:
      raw.arguments && typeof raw.arguments === 'object'
        ? (raw.arguments as Record<string, unknown>)
        : undefined,
    success: typeof raw.success === 'boolean' ? raw.success : undefined,
    duration_ms: typeof raw.duration_ms === 'number' ? raw.duration_ms : undefined,
    error: raw.error != null ? String(raw.error) : undefined,
    model: raw.model ? String(raw.model) : undefined,
    timestamp: typeof raw.timestamp === 'number' ? raw.timestamp : undefined,
    result_preview: raw.result_preview ? String(raw.result_preview) : undefined,
    result: raw.result ? String(raw.result) : undefined,
    has_image: Boolean(raw.has_image),
    has_audio: Boolean(raw.has_audio),
    has_resource: Boolean(raw.has_resource),
    download_urls: Array.isArray(raw.download_urls)
      ? raw.download_urls.map((item) => {
          const row = item as Record<string, unknown>;
          return {
            url: String(row.url || ''),
            label: row.label ? String(row.label) : undefined,
            mime: row.mime ? String(row.mime) : undefined,
          };
        })
      : undefined,
  };
}

export function normalizeMcpToolCallList(raw: unknown): McpToolCallRecord[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item) => item && typeof item === 'object')
    .map((item) => normalizeMcpToolCallRecord(item as Record<string, unknown>));
}
