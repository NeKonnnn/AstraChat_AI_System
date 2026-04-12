import { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from '../config/api';
import { getActiveAgentFromStorage } from '../components/AgentSelector';

/** Есть ли хотя бы один включённый стандартный агент оркестратора (/api/agent/agents). */
export function useOrchestratorAgentsAnyActive(orchestratorReady: boolean): boolean {
  const [anyActive, setAnyActive] = useState(false);

  const refresh = useCallback(async () => {
    if (!orchestratorReady) {
      setAnyActive(false);
      return;
    }
    try {
      const r = await fetch(getApiUrl('/api/agent/agents'));
      if (!r.ok) return;
      const data = await r.json();
      const list = data.agents || [];
      setAnyActive(list.some((a: { is_active?: boolean }) => Boolean(a.is_active)));
    } catch {
      setAnyActive(false);
    }
  }, [orchestratorReady]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const h = () => void refresh();
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
