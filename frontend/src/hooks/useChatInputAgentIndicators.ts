import { useState, useEffect, useCallback } from 'react';
import { getApiUrl, getAuthFetchHeaders } from '../config/api';
import { getActiveAgentFromStorage } from '../components/AgentSelector';

type AgentRow = { is_active?: boolean };

async function fetchAgentsList(): Promise<AgentRow[]> {
  const res = await fetch(getApiUrl('/api/agent/agents'), { cache: 'no-store' });
  if (!res.ok) return [];
  const data = await res.json();
  return data.agents || [];
}

/** Есть ли хотя бы один включённый стандартный агент. */
export async function fetchStandardAgentsActive(): Promise<boolean> {
  try {
    const list = await fetchAgentsList();
    return list.some((a) => Boolean(a.is_active));
  } catch {
    return false;
  }
}

/** Переключить в прямой режим, если не осталось активных стандартных агентов. */
export async function switchToDirectIfNoAgentsActive(): Promise<boolean> {
  try {
    const list = await fetchAgentsList();
    if (list.some((a) => Boolean(a.is_active))) {
      return false;
    }
    const modeRes = await fetch(getApiUrl('/api/agent/mode'), {
      method: 'POST',
      headers: getAuthFetchHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ mode: 'direct' }),
      cache: 'no-store',
    });
    return modeRes.ok;
  } catch {
    return false;
  }
}

export function dispatchAgentStatusChanged(anyActive?: boolean): void {
  if (typeof anyActive === 'boolean') {
    window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged', { detail: { anyActive } }));
    return;
  }
  window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
}

/** Есть ли хотя бы один включённый стандартный агент оркестратора (/api/agent/agents). */
export function useOrchestratorAgentsAnyActive(orchestratorReady: boolean): boolean {
  const [anyActive, setAnyActive] = useState(false);

  const refresh = useCallback(async () => {
    if (!orchestratorReady) {
      setAnyActive(false);
      return;
    }
    setAnyActive(await fetchStandardAgentsActive());
  }, [orchestratorReady]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const h = (e: Event) => {
      const detail = (e as CustomEvent<{ anyActive?: boolean }>).detail;
      if (typeof detail?.anyActive === 'boolean') {
        setAnyActive(detail.anyActive);
        return;
      }
      void refresh();
    };
    window.addEventListener('astrachatAgentStatusChanged', h);
    return () => window.removeEventListener('astrachatAgentStatusChanged', h);
  }, [refresh]);

  return anyActive;
}

/** Выбранный «мой» агент из localStorage + событие agentSelected. */
export function useMyAgentSelection(): { id: number; name: string; system_prompt: string } | null {
  const [sel, setSel] = useState(() => getActiveAgentFromStorage());

  useEffect(() => {
    const on = () => setSel(getActiveAgentFromStorage());
    window.addEventListener('agentSelected', on);
    return () => window.removeEventListener('agentSelected', on);
  }, []);

  return sel;
}
