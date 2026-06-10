import { useCallback, useEffect, useState } from 'react';
import {
  fetchAgentMcpStatus,
  fetchMcpServers,
  fetchMcpStatus,
  fetchMcpTools,
  verifyMcpServer,
} from '../api';
import type { McpPlatformStatus, McpServerConfigPublic, McpToolInfo, McpVerifyResult } from '../types';

export function useMcpPlatform() {
  const [servers, setServers] = useState<McpServerConfigPublic[]>([]);
  const [status, setStatus] = useState<McpPlatformStatus | null>(null);
  const [tools, setTools] = useState<McpToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [srv, st] = await Promise.all([fetchMcpServers(), fetchMcpStatus()]);
      setServers(srv);
      setStatus(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить MCP');
      setServers([]);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTools = useCallback(async (serverId?: string) => {
    try {
      const list = await fetchMcpTools(serverId);
      setTools(list);
      return list;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить инструменты MCP');
      setTools([]);
      return [];
    }
  }, []);

  const testServerHealth = useCallback(async () => {
    await refresh();
    return status;
  }, [refresh, status]);

  const verifyServer = useCallback(async (serverId: string): Promise<McpVerifyResult> => {
    const result = await verifyMcpServer(serverId);
    await refresh();
    return result;
  }, [refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    servers,
    status,
    tools,
    loading,
    error,
    refresh,
    loadTools,
    testServerHealth,
    verifyServer,
  };
}

/** Aggregate status для AgentsSettings (совместим с /api/agent/mcp/status). */
export function useAgentMcpStatus() {
  const [status, setStatus] = useState<McpPlatformStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const st = await fetchAgentMcpStatus();
      setStatus(st);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { status, loading, refresh };
}
