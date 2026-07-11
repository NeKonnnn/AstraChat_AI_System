import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { InlineAttachment } from '../components/ChatInputBar';
import type { Message } from '../contexts/AppContext';
import { getApiUrl } from '../config/api';
import { getMcpToolIdsForChat, MCP_SELECTION_CHANGED_EVENT } from '../mcp/selectionStorage';
import { LAST_SELECTED_MODEL_PATH_STORAGE_KEY } from '../utils/modelThinking';
import {
  computeChatContextUsage,
  ContextUsageSegment,
  mergeContextUsageWithOverhead,
  MODEL_PATH_CHANGED_EVENT,
  MODEL_SETTINGS_CHANGED_EVENT,
  ModelContextMeta,
  isContextRequestOverLimit,
  resolveEffectiveContextLimit,
  resolveMultiModelContextLimit,
} from '../utils/contextTokens';

function readStoredModelPath(): string {
  try {
    return localStorage.getItem(LAST_SELECTED_MODEL_PATH_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function readStoredAgentId(): number | null {
  try {
    const raw = localStorage.getItem('active_agent_id');
    if (!raw) return null;
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface UseChatContextUsageOptions {
  messages: Message[];
  draftText?: string;
  inlineAttachments?: InlineAttachment[];
  availableModels: ModelContextMeta[];
  configuredContextSize?: number | null;
  configuredOutputTokens?: number | null;
  loadedModelCtx?: number | null;
  isMultiLlmMode?: boolean;
  multiLlmModelPaths?: string[];
  chatId?: string | null;
  useKbRag?: boolean;
  projectInstructions?: string | null;
}

export interface ChatContextUsageResult {
  currentTokens: number;
  maxTokens: number;
  percent: number;
  segments?: ContextUsageSegment[];
  overheadLoading: boolean;
  refreshOverhead: () => void;
  outputTokensReserve: number;
  isOverLimit: boolean;
}

export function useChatContextUsage({
  messages,
  draftText = '',
  inlineAttachments = [],
  availableModels,
  configuredContextSize,
  configuredOutputTokens,
  loadedModelCtx,
  isMultiLlmMode = false,
  multiLlmModelPaths = [],
  chatId = null,
  useKbRag = false,
  projectInstructions = null,
}: UseChatContextUsageOptions): ChatContextUsageResult {
  const [selectedModelPath, setSelectedModelPath] = useState(readStoredModelPath);
  const [settingsContextSize, setSettingsContextSize] = useState<number | null>(null);
  const [settingsOutputTokens, setSettingsOutputTokens] = useState<number | null>(null);
  const [overheadSegments, setOverheadSegments] = useState<ContextUsageSegment[]>([]);
  const [overheadLoading, setOverheadLoading] = useState(false);
  const [agentId, setAgentId] = useState<number | null>(() => readStoredAgentId());
  const [mcpToolIds, setMcpToolIds] = useState<string[]>(() =>
    chatId ? getMcpToolIdsForChat(chatId) : [],
  );
  const overheadLoadedKeyRef = useRef<string>('');

  const loadModelSettings = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/api/models/settings'));
      if (!response.ok) return;
      const data = await response.json();
      const ctx = data?.context_size;
      if (typeof ctx === 'number' && ctx > 0) {
        setSettingsContextSize(ctx);
      }
      const out = data?.output_tokens;
      if (typeof out === 'number' && out > 0) {
        setSettingsOutputTokens(out);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void loadModelSettings();
    const onSettingsChanged = () => void loadModelSettings();
    window.addEventListener(MODEL_SETTINGS_CHANGED_EVENT, onSettingsChanged);
    return () => window.removeEventListener(MODEL_SETTINGS_CHANGED_EVENT, onSettingsChanged);
  }, [loadModelSettings]);

  useEffect(() => {
    const sync = () => setSelectedModelPath(readStoredModelPath());
    const onModelChanged = (e: Event) => {
      const detail = (e as CustomEvent<{ path?: string }>).detail;
      if (detail?.path) setSelectedModelPath(detail.path);
      else sync();
    };
    window.addEventListener(MODEL_PATH_CHANGED_EVENT, onModelChanged);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(MODEL_PATH_CHANGED_EVENT, onModelChanged);
      window.removeEventListener('storage', sync);
    };
  }, []);

  useEffect(() => {
    const syncAgent = () => setAgentId(readStoredAgentId());
    window.addEventListener('agentSelected', syncAgent);
    return () => window.removeEventListener('agentSelected', syncAgent);
  }, []);

  useEffect(() => {
    setMcpToolIds(chatId ? getMcpToolIdsForChat(chatId) : []);
    const onMcp = (e: Event) => {
      const detail = (e as CustomEvent<{ chatId?: string }>).detail;
      if (!chatId || !detail?.chatId || detail.chatId === chatId) {
        setMcpToolIds(chatId ? getMcpToolIdsForChat(chatId) : []);
      }
    };
    window.addEventListener(MCP_SELECTION_CHANGED_EVENT, onMcp);
    return () => window.removeEventListener(MCP_SELECTION_CHANGED_EVENT, onMcp);
  }, [chatId]);

  const effectiveConfiguredSize =
    settingsContextSize ??
    (typeof configuredContextSize === 'number' && configuredContextSize > 0
      ? configuredContextSize
      : null);

  const effectiveOutputTokens =
    settingsOutputTokens ??
    (typeof configuredOutputTokens === 'number' && configuredOutputTokens > 0
      ? configuredOutputTokens
      : 0);

  const modelPathForLimit = useMemo(() => {
    if (isMultiLlmMode && multiLlmModelPaths.some(Boolean)) {
      return multiLlmModelPaths.find(Boolean) || selectedModelPath;
    }
    return selectedModelPath;
  }, [isMultiLlmMode, multiLlmModelPaths, selectedModelPath]);

  const maxTokens = useMemo(() => {
    if (isMultiLlmMode && multiLlmModelPaths.some(Boolean)) {
      return resolveMultiModelContextLimit(
        multiLlmModelPaths,
        availableModels,
        effectiveConfiguredSize,
      );
    }
    return resolveEffectiveContextLimit(
      selectedModelPath,
      availableModels,
      effectiveConfiguredSize,
      loadedModelCtx,
    );
  }, [
    isMultiLlmMode,
    multiLlmModelPaths,
    selectedModelPath,
    availableModels,
    effectiveConfiguredSize,
    loadedModelCtx,
  ]);

  const overheadRequestKey = useMemo(
    () =>
      JSON.stringify({
        model_path: modelPathForLimit || null,
        agent_id: agentId,
        use_kb_rag: useKbRag,
        tool_ids: mcpToolIds,
        project_instructions: projectInstructions?.trim() || null,
      }),
    [modelPathForLimit, agentId, useKbRag, mcpToolIds, projectInstructions],
  );

  const refreshOverhead = useCallback(() => {
    if (overheadLoadedKeyRef.current === overheadRequestKey) {
      return;
    }

    setOverheadLoading(true);

    void (async () => {
      try {
        const response = await fetch(getApiUrl('/api/chat/context-breakdown'), {
          method: 'POST',
          headers: authHeaders(),
          body: overheadRequestKey,
        });
        if (!response.ok) return;
        const data = await response.json();
        const segs = Array.isArray(data.segments) ? data.segments : [];
        overheadLoadedKeyRef.current = overheadRequestKey;
        setOverheadSegments(segs);
      } catch {
        setOverheadSegments([]);
      } finally {
        setOverheadLoading(false);
      }
    })();
  }, [overheadRequestKey]);

  useEffect(() => {
    overheadLoadedKeyRef.current = '';
    setOverheadSegments([]);
  }, [overheadRequestKey]);

  const featureFlags = useMemo(
    () => ({
      hasAgent: agentId != null,
      hasMcp: mcpToolIds.length > 0,
      hasRag: useKbRag,
      hasProject: Boolean(projectInstructions?.trim()),
    }),
    [agentId, mcpToolIds.length, useKbRag, projectInstructions],
  );

  return useMemo(() => {
    const conversation = computeChatContextUsage({
      messages,
      draftText,
      inlineAttachments,
      maxTokens,
    });
    const usage = mergeContextUsageWithOverhead(
      conversation,
      overheadSegments,
      maxTokens,
      featureFlags,
      effectiveOutputTokens,
    );
    const isOverLimit = isContextRequestOverLimit(usage.currentTokens, usage.maxTokens);
    return {
      ...usage,
      overheadLoading,
      refreshOverhead,
      outputTokensReserve: effectiveOutputTokens,
      isOverLimit,
    };
  }, [
    messages,
    draftText,
    inlineAttachments,
    maxTokens,
    overheadSegments,
    featureFlags,
    effectiveOutputTokens,
    overheadLoading,
    refreshOverhead,
  ]);
}
