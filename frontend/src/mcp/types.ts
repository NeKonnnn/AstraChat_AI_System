/** Generic MCP platform types (frontend/src/mcp). */

export interface McpServerConfigPublic {
  id: string;
  display_name: string;
  enabled: boolean;
  transport: 'stdio' | 'streamable-http' | string;
  auth_type?: string;
  auth_mode?: string;
  credential_provider?: string | null;
  tool_name_prefix?: string;
}

export interface McpServerStatus {
  id: string;
  display_name: string;
  enabled: boolean;
  connected: boolean;
  transport?: string;
  tools?: number;
  latency_ms?: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
}

export interface McpPlatformStatus {
  initialized?: boolean;
  enabled?: boolean;
  servers_connected?: number;
  servers_total?: number;
  total_servers?: number;
  tools?: number;
  tools_total?: number;
  servers?: McpServerStatus[];
  pool?: Record<string, unknown>;
  message?: string | null;
  /** Legacy compat from /api/agent/mcp/status */
  active_servers?: string[];
}

export interface McpToolInfo {
  name: string;
  qualified_name: string;
  server_id: string;
  description?: string;
}

export interface McpVerifyResult {
  server_id: string;
  success: boolean;
  tools_count?: number;
  latency_ms?: number;
  error?: string | null;
  tools?: string[];
}

export interface McpToolCallRecord {
  type: 'mcp_tool_start' | 'mcp_tool_end';
  server_id: string;
  tool: string;
  qualified_name: string;
  success?: boolean;
  duration_ms?: number;
  error?: string | null;
  model?: string;
  timestamp?: number;
  result_preview?: string;
  has_image?: boolean;
  has_audio?: boolean;
  has_resource?: boolean;
}

export interface McpCredentialsMetadata {
  configured?: boolean;
  fields?: Record<string, boolean>;
  storage_available?: boolean;
  auth_mode?: string;
  credential_fields?: string[];
}

export interface ServerPluginProps {
  serverId: string;
  isDarkMode: boolean;
  compact?: boolean;
  authMode?: string;
}
