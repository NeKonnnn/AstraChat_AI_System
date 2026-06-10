import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchMcpServers, fetchMcpStatus } from '../api';
import {
  getMcpToolIdsForChat,
  MCP_SELECTION_CHANGED_EVENT,
  parseMcpServerIdFromToolId,
} from '../selectionStorage';
import type { McpServerConfigPublic, McpServerStatus } from '../types';

export interface ActiveMcpServerIndicator {
  id: string;
  display_name: string;
  connected?: boolean;
}

export function useChatInputMcpIndicators(chatId: string | null | undefined): ActiveMcpServerIndicator[] {
  const [servers, setServers] = useState<McpServerConfigPublic[]>([]);
  const [statusMap, setStatusMap] = useState<Map<string, McpServerStatus>>(new Map());
  const [toolIds, setToolIds] = useState<string[]>([]);

  const refreshSelection = useCallback(() => {
    if (!chatId) {
      setToolIds([]);
      return;
    }
    setToolIds(getMcpToolIdsForChat(chatId));
  }, [chatId]);

  const refreshMeta = useCallback(async () => {
    try {
      const [srv, st] = await Promise.all([fetchMcpServers(), fetchMcpStatus()]);
      setServers(srv);
      const map = new Map<string, McpServerStatus>();
      for (const s of st.servers || []) {
        map.set(s.id, s);
      }
      setStatusMap(map);
    } catch {
      /* keep previous */
    }
  }, []);

  useEffect(() => {
    refreshSelection();
    void refreshMeta();
  }, [refreshSelection, refreshMeta]);

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<{ chatId?: string }>).detail;
      if (!chatId || !detail?.chatId || detail.chatId === chatId) {
        refreshSelection();
      }
    };
    window.addEventListener(MCP_SELECTION_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(MCP_SELECTION_CHANGED_EVENT, onChange);
  }, [chatId, refreshSelection]);

  return useMemo(() => {
    const byId = new Map(servers.map((s) => [s.id, s]));
    const result: ActiveMcpServerIndicator[] = [];
    for (const tid of toolIds) {
      const sid = parseMcpServerIdFromToolId(tid);
      if (!sid) continue;
      const cfg = byId.get(sid);
      const st = statusMap.get(sid);
      result.push({
        id: sid,
        display_name: cfg?.display_name || st?.display_name || sid,
        connected: st?.connected,
      });
    }
    return result;
  }, [toolIds, servers, statusMap]);
}
