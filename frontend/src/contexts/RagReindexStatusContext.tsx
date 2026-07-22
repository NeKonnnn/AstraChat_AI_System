import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation } from 'react-router-dom';
import { getApiUrl, getAuthFetchHeaders } from '../config/api';
import { useAppContext } from './AppContext';
import { getSettings, initSettings } from '../settings';
import {
  ragReindexBlockMessage,
  shouldBlockRagSend,
  type RagReindexStatusPayload,
  type RagSendBlockContext,
} from '../utils/ragReindexBlock';

interface RagReindexStatusContextValue {
  status: RagReindexStatusPayload | null;
  anyReindexing: boolean;
  agentHasKb: boolean;
  projectHasDocuments: boolean;
  blockMessage: string;
  shouldBlockRagSend: (ctx: Pick<RagSendBlockContext, 'libraryEnabled'>) => boolean;
}

const defaultStatus: RagReindexStatusPayload = {
  memory: { reindexing: false },
  project: { reindexing: false },
  kb: { reindexing: false },
  any_reindexing: false,
  agent_has_kb: false,
  project_has_documents: false,
  message: '',
};

const RagReindexStatusContext = createContext<RagReindexStatusContextValue>({
  status: null,
  anyReindexing: false,
  agentHasKb: false,
  projectHasDocuments: false,
  blockMessage: '',
  shouldBlockRagSend: () => false,
});

function readActiveAgentId(): number | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem('active_agent_id');
  const parsed = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function projectIdFromPathname(pathname: string): string | null {
  const match = pathname.match(/^\/project\/([^/]+)/);
  return match?.[1] ?? null;
}

export function RagReindexStatusProvider({ children }: { children: ReactNode }) {
  const { state } = useAppContext();
  const location = useLocation();
  const [status, setStatus] = useState<RagReindexStatusPayload | null>(null);

  // Нельзя класть state.chats в deps интервала: при стриминге чат обновляется
  // каждый чанк → эффект перезапускается → шквал /reindex/status в логах.
  const chatsRef = useRef(state.chats);
  const currentChatIdRef = useRef(state.currentChatId);
  const pathnameRef = useRef(location.pathname);
  chatsRef.current = state.chats;
  currentChatIdRef.current = state.currentChatId;
  pathnameRef.current = location.pathname;

  const currentChatProjectId =
    state.chats.find((c) => c.id === state.currentChatId)?.projectId ?? null;

  const pollProjectId = useMemo(() => {
    const routeProjectId = projectIdFromPathname(location.pathname);
    return routeProjectId ?? currentChatProjectId;
  }, [location.pathname, currentChatProjectId]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    let cancelled = false;

    const startPolling = async () => {
      let settings;
      try {
        settings = getSettings();
      } catch {
        try {
          settings = await initSettings();
        } catch {
          return;
        }
      }
      if (cancelled) return;

      const pollIntervalSeconds = settings.app.ragReindexStatusPollSeconds;

      const poll = async () => {
        const activeAgentId = readActiveAgentId();
        const routeProjectId = projectIdFromPathname(pathnameRef.current);
        const chat = chatsRef.current.find((c) => c.id === currentChatIdRef.current);
        const activeProjectId = routeProjectId ?? chat?.projectId ?? null;
        const params = new URLSearchParams();
        if (activeAgentId != null) {
          params.set('agent_id', String(activeAgentId));
        }
        if (activeProjectId) {
          params.set('project_id', activeProjectId);
        }
        const qs = params.toString() ? `?${params.toString()}` : '';
        try {
          const res = await fetch(getApiUrl(`/api/rag/reindex-status${qs}`), {
            headers: getAuthFetchHeaders(),
          });
          if (!res.ok) return;
          const data = (await res.json()) as RagReindexStatusPayload;
          setStatus({
            memory: { reindexing: Boolean(data.memory?.reindexing) },
            project: { reindexing: Boolean(data.project?.reindexing) },
            kb: { reindexing: Boolean(data.kb?.reindexing) },
            any_reindexing: Boolean(data.any_reindexing),
            agent_has_kb: Boolean(data.agent_has_kb),
            project_has_documents: Boolean(data.project_has_documents),
            message: typeof data.message === 'string' ? data.message : '',
          });
        } catch {
          /* ignore transient network errors */
        }
      };

      void poll();
      interval = setInterval(poll, pollIntervalSeconds * 1000);
    };

    void startPolling();
    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [location.pathname, state.currentChatId, pollProjectId]);

  const effectiveStatus = status ?? defaultStatus;
  const blockMessage = ragReindexBlockMessage(effectiveStatus);

  const shouldBlock = useCallback(
    (ctx: Pick<RagSendBlockContext, 'libraryEnabled'>) =>
      shouldBlockRagSend(effectiveStatus, {
        libraryEnabled: ctx.libraryEnabled,
        projectHasDocuments: effectiveStatus.project_has_documents,
        agentHasKb: effectiveStatus.agent_has_kb,
      }),
    [effectiveStatus],
  );

  const value = useMemo(
    () => ({
      status: effectiveStatus,
      anyReindexing: effectiveStatus.any_reindexing,
      agentHasKb: effectiveStatus.agent_has_kb,
      projectHasDocuments: effectiveStatus.project_has_documents,
      blockMessage,
      shouldBlockRagSend: shouldBlock,
    }),
    [effectiveStatus, blockMessage, shouldBlock],
  );

  return (
    <RagReindexStatusContext.Provider value={value}>{children}</RagReindexStatusContext.Provider>
  );
}

export function useRagReindexStatus(): RagReindexStatusContextValue {
  return useContext(RagReindexStatusContext);
}
