import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Typography, CircularProgress } from '@mui/material';
import {
  SmartToy as AgentIcon,
  Check as CheckIcon,
  PersonOff as NoAgentIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useAppActions } from '../contexts/AppContext';
import { getApiUrl } from '../config/api';
import {
  getDropdownItemSx,
  MENU_ACTION_TEXT_SIZE,
  CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX,
  CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
} from '../constants/menuStyles';
import type { Agent } from './AgentSelector';
import { getActiveAgentFromStorage } from './AgentSelector';
import { applyAgentModelAndSettings } from '../utils/applyAgentServer';
import { MODEL_SETTINGS_DEFAULT } from '../constants/modelSettingsStyles';

const STORAGE_AGENT_ID = 'active_agent_id';
const STORAGE_AGENT_NAME = 'active_agent_name';
const STORAGE_AGENT_PROMPT = 'active_agent_prompt';

interface ChatGearMyAgentsTabProps {
  isDarkMode: boolean;
  searchQuery: string;
  visible: boolean;
}

export default function ChatGearMyAgentsTab({ isDarkMode, searchQuery, visible }: ChatGearMyAgentsTabProps) {
  const { token } = useAuth();
  const { showNotification } = useAppActions();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [activeAgent, setActiveAgent] = useState(() => getActiveAgentFromStorage());
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [loadingAgentId, setLoadingAgentId] = useState<number | null>(null);

  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const mutedTextColor = isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)';
  const iconColor = isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)';
  const subtleColor = isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)';

  const loadAgents = useCallback(async () => {
    setLoadingAgents(true);
    try {
      const url = getApiUrl('/api/agents/my/agents');
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) return;
      const data = await resp.json();
      setAgents(data.agents || []);
    } catch {
      /* silent */
    } finally {
      setLoadingAgents(false);
    }
  }, [token]);

  useEffect(() => {
    if (!visible) return;
    void loadAgents();
  }, [visible, loadAgents]);

  useEffect(() => {
    const onAgentSelected = () => setActiveAgent(getActiveAgentFromStorage());
    window.addEventListener('agentSelected', onAgentSelected);
    return () => window.removeEventListener('agentSelected', onAgentSelected);
  }, []);

  const handleClearAgent = useCallback(() => {
    localStorage.removeItem(STORAGE_AGENT_ID);
    localStorage.removeItem(STORAGE_AGENT_NAME);
    localStorage.removeItem(STORAGE_AGENT_PROMPT);
    setActiveAgent(null);
    window.dispatchEvent(new CustomEvent('agentSelected', { detail: null }));
    showNotification('info', 'Агент снят');
  }, [showNotification]);

  const handleSelectAgent = useCallback(
    async (agent: Agent) => {
      let full: Agent = { ...agent };
      if (token) {
        try {
          const r = await fetch(getApiUrl(`/api/agents/${agent.id}`), {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (r.ok) {
            const j = await r.json();
            full = {
              ...agent,
              ...j,
              system_prompt: j.system_prompt ?? agent.system_prompt,
              config: (j.config as Record<string, unknown>) ?? agent.config,
            };
          }
        } catch {
          /* */
        }
      }

      const cfg = (full.config || {}) as Record<string, unknown>;
      const modelPath = String(cfg.model_path || cfg.model || '')
        .trim()
        .replace(/^1lm-svc:\/\//i, 'llm-svc://')
        .replace(/\s+/g, '');
      const rawSettings = {
        ...MODEL_SETTINGS_DEFAULT,
        ...((cfg.model_settings as Record<string, unknown>) || {}),
      };

      const persistLocal = () => {
        localStorage.setItem(STORAGE_AGENT_ID, String(full.id));
        localStorage.setItem(STORAGE_AGENT_NAME, full.name);
        localStorage.setItem(STORAGE_AGENT_PROMPT, full.system_prompt || '');
        setActiveAgent({ id: full.id, name: full.name, system_prompt: full.system_prompt || '' });
        window.dispatchEvent(new CustomEvent('agentSelected', { detail: full }));
      };

      if (!token) {
        persistLocal();
        showNotification('info', 'Войдите в аккаунт, чтобы на сервер применились модель и настройки агента');
        return;
      }

      setIsLoadingModel(true);
      setLoadingAgentId(full.id);
      showNotification(
        'info',
        modelPath ? `Загрузка модели агента «${full.name}»…` : `Применение настроек агента «${full.name}»…`,
      );
      try {
        const applied = await applyAgentModelAndSettings(token, {
          system_prompt: full.system_prompt || '',
          model_path: modelPath || null,
          model_settings: rawSettings,
        });
        if (!applied.ok) {
          showNotification('error', `Агент не активирован: ${applied.message}`);
          return;
        }
        persistLocal();
        showNotification(
          'success',
          modelPath
            ? `Агент «${full.name}»: модель загружена, настройки и промпт применены`
            : `Агент «${full.name}»: настройки и промпт применены (модель в агенте не задана)`,
        );
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        showNotification('error', `Агент не активирован: ${msg}`);
      } finally {
        setIsLoadingModel(false);
        setLoadingAgentId(null);
      }
    },
    [token, showNotification],
  );

  const filteredAgents = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter((a) => a.name.toLowerCase().includes(q));
  }, [agents, searchQuery]);

  return (
    <Box
      sx={{
        height: `${CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX}px`,
        maxHeight: `${CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX}px`,
        flexShrink: 0,
        overflowX: 'hidden',
        overflowY: 'auto',
        px: 0.75,
        py: 1,
        boxSizing: 'border-box',
        ...CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
      }}
    >
      {loadingAgents && agents.length === 0 ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={28} />
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Box
            onClick={() => {
              if (!isLoadingModel) handleClearAgent();
            }}
            sx={{
              ...dropdownItemSx,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              color: !activeAgent ? mutedTextColor : iconColor,
              fontWeight: !activeAgent ? 600 : 400,
              bgcolor: !activeAgent ? (isDarkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)') : 'transparent',
              fontStyle: 'italic',
              borderRadius: 1,
              py: 0.75,
              px: 0.75,
              opacity: isLoadingModel ? 0.6 : 1,
              pointerEvents: isLoadingModel ? 'none' : 'auto',
            }}
          >
            <NoAgentIcon sx={{ fontSize: 18, color: subtleColor, flexShrink: 0 }} />
            <Typography sx={{ flex: 1, fontSize: MENU_ACTION_TEXT_SIZE }}>Без агента</Typography>
            {!activeAgent && <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />}
          </Box>
          {filteredAgents.map((agent) => (
            <Box
              key={agent.id}
              onClick={() => {
                if (!isLoadingModel) void handleSelectAgent(agent);
              }}
              sx={{
                ...dropdownItemSx,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                color: activeAgent?.id === agent.id ? mutedTextColor : iconColor,
                fontWeight: activeAgent?.id === agent.id ? 600 : 400,
                bgcolor:
                  activeAgent?.id === agent.id
                    ? isDarkMode
                      ? 'rgba(255,255,255,0.06)'
                      : 'rgba(0,0,0,0.04)'
                    : 'transparent',
                borderRadius: 1,
                py: 0.75,
                px: 0.75,
                opacity: isLoadingModel ? 0.6 : 1,
                pointerEvents: isLoadingModel ? 'none' : 'auto',
              }}
            >
              <AgentIcon sx={{ fontSize: 18, color: iconColor, flexShrink: 0 }} />
              <Typography
                sx={{
                  flex: 1,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  fontSize: MENU_ACTION_TEXT_SIZE,
                }}
              >
                {agent.name}
              </Typography>
              {loadingAgentId === agent.id ? (
                <CircularProgress size={14} sx={{ flexShrink: 0, color: 'primary.main' }} />
              ) : activeAgent?.id === agent.id ? (
                <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
              ) : null}
            </Box>
          ))}
          {!loadingAgents && filteredAgents.length === 0 && !searchQuery.trim() && (
            <Typography
              variant="body2"
              sx={{ color: subtleColor, fontSize: MENU_ACTION_TEXT_SIZE, px: 0.5, py: 1, textAlign: 'center' }}
            >
              Нет созданных агентов
            </Typography>
          )}
          {!loadingAgents && searchQuery.trim() && filteredAgents.length === 0 && (
            <Typography
              variant="body2"
              sx={{ color: subtleColor, fontSize: MENU_ACTION_TEXT_SIZE, px: 0.5, py: 1, textAlign: 'center' }}
            >
              Ничего не найдено
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}
