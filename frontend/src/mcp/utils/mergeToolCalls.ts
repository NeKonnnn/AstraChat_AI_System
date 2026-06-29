import type { McpToolCallRecord, McpToolExecution } from '../types';

function findRunningIndex(executions: McpToolExecution[], qualifiedName: string): number {
  for (let i = executions.length - 1; i >= 0; i -= 1) {
    if (executions[i].qualified_name === qualifiedName && executions[i].status === 'running') {
      return i;
    }
  }
  return -1;
}

/** Объединяет mcp_tool_start / mcp_tool_end в одну карточку на инструмент. */
export function mergeMcpToolCalls(records: McpToolCallRecord[]): McpToolExecution[] {
  const executions: McpToolExecution[] = [];
  const indexByCallId = new Map<string, number>();

  records.forEach((record, index) => {
    let callId = record.call_id;
    if (!callId && record.type === 'mcp_tool_end') {
      const runningIdx = findRunningIndex(executions, record.qualified_name);
      if (runningIdx >= 0) {
        callId = executions[runningIdx].call_id;
      }
    }
    if (!callId) {
      callId = `${record.qualified_name}:${record.timestamp ?? index}`;
    }

    if (record.type === 'mcp_tool_start') {
      const existingIdx = indexByCallId.get(callId);
      if (existingIdx != null) {
        const prev = executions[existingIdx];
        executions[existingIdx] = {
          ...prev,
          status: prev.status === 'completed' || prev.status === 'failed' ? prev.status : 'running',
          arguments: record.arguments ?? prev.arguments,
          started_at: record.timestamp ?? prev.started_at,
        };
        return;
      }

      indexByCallId.set(callId, executions.length);
      executions.push({
        call_id: callId,
        server_id: record.server_id,
        tool: record.tool,
        qualified_name: record.qualified_name,
        model: record.model,
        status: 'running',
        arguments: record.arguments,
        started_at: record.timestamp,
      });
      return;
    }

    const existingIdx = indexByCallId.get(callId);
    const base: McpToolExecution =
      existingIdx != null
        ? executions[existingIdx]
        : {
            call_id: callId,
            server_id: record.server_id,
            tool: record.tool,
            qualified_name: record.qualified_name,
            model: record.model,
            status: 'running',
          };

    const merged: McpToolExecution = {
      ...base,
      status: record.success === false ? 'failed' : 'completed',
      arguments: record.arguments ?? base.arguments,
      result: record.result ?? record.result_preview ?? base.result,
      result_preview: record.result_preview ?? base.result_preview,
      error: record.error ?? base.error,
      duration_ms: record.duration_ms ?? base.duration_ms,
      download_urls: record.download_urls ?? base.download_urls,
      has_image: record.has_image ?? base.has_image,
      has_audio: record.has_audio ?? base.has_audio,
      has_resource: record.has_resource ?? base.has_resource,
      ended_at: record.timestamp ?? base.ended_at,
    };

    if (existingIdx != null) {
      executions[existingIdx] = merged;
    } else {
      indexByCallId.set(callId, executions.length);
      executions.push(merged);
    }
  });

  return executions;
}
