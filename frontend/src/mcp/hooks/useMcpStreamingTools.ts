import { useCallback, useEffect, useState } from 'react';
import type { McpToolCallRecord } from '../types';

export const MCP_TOOL_ACTIVITY_EVENT = 'astrachatMcpToolActivity';

interface McpToolActivityDetail {
  record: McpToolCallRecord;
  phase: 'start' | 'end';
}

/** In-flight MCP tools во время генерации (live indicator F-6). */
export function useMcpStreamingTools() {
  const [active, setActive] = useState<McpToolCallRecord[]>([]);

  useEffect(() => {
    const onActivity = (e: Event) => {
      const detail = (e as CustomEvent<McpToolActivityDetail>).detail;
      if (!detail?.record) return;
      const { record, phase } = detail;
      const key = `${record.qualified_name}:${record.model || ''}`;
      setActive((prev) => {
        if (phase === 'start') {
          if (prev.some((x) => `${x.qualified_name}:${x.model || ''}` === key)) return prev;
          return [...prev, record];
        }
        return prev.filter((x) => `${x.qualified_name}:${x.model || ''}` !== key);
      });
    };
    const onClear = () => setActive([]);
    window.addEventListener(MCP_TOOL_ACTIVITY_EVENT, onActivity);
    window.addEventListener('astrachatMcpToolActivityClear', onClear);
    return () => {
      window.removeEventListener(MCP_TOOL_ACTIVITY_EVENT, onActivity);
      window.removeEventListener('astrachatMcpToolActivityClear', onClear);
    };
  }, []);

  const clear = useCallback(() => setActive([]), []);

  return { activeMcpTools: active, clearActiveMcpTools: clear };
}
