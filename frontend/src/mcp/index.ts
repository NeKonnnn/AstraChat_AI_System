/** Public exports MCP platform (frontend/src/mcp). */

export * from './types';
export * from './api';
export * from './errors';
export * from './selectionStorage';
export { useMcpPlatform, useAgentMcpStatus } from './hooks/useMcpPlatform';
export { useChatMcpSelection } from './hooks/useChatMcpSelection';
export { useChatInputMcpIndicators } from './hooks/useChatInputMcpIndicators';
export { useMcpStreamingTools, MCP_TOOL_ACTIVITY_EVENT } from './hooks/useMcpStreamingTools';
export { formatMcpAggregateLabel, isMcpPlatformHealthy } from './utils/statusLabel';
