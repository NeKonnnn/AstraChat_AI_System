import { useCallback, useEffect, useState } from 'react';
import {
  getMcpToolIdsForChat,
  MCP_SELECTION_CHANGED_EVENT,
  setMcpToolIdsForChat,
  toggleMcpServerForChat,
} from '../selectionStorage';

export function useChatMcpSelection(chatId: string | null | undefined) {
  const [enabledMcpToolIds, setEnabled] = useState<string[]>([]);

  const sync = useCallback(() => {
    if (!chatId) {
      setEnabled([]);
      return;
    }
    setEnabled(getMcpToolIdsForChat(chatId));
  }, [chatId]);

  useEffect(() => {
    sync();
  }, [sync]);

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<{ chatId?: string }>).detail;
      if (!chatId || !detail?.chatId || detail.chatId === chatId) {
        sync();
      }
    };
    window.addEventListener(MCP_SELECTION_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(MCP_SELECTION_CHANGED_EVENT, onChange);
  }, [chatId, sync]);

  const setEnabledMcpToolIds = useCallback(
    (ids: string[]) => {
      if (!chatId) return;
      setMcpToolIdsForChat(chatId, ids);
      setEnabled(ids);
    },
    [chatId],
  );

  const toggleServer = useCallback(
    (serverId: string, on: boolean) => {
      if (!chatId) return;
      const next = toggleMcpServerForChat(chatId, serverId, on);
      setEnabled(next);
    },
    [chatId],
  );

  return { enabledMcpToolIds, setEnabledMcpToolIds, toggleServer };
}
