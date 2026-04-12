import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Typography,
  Switch,
  FormControlLabel,
  CircularProgress,
  IconButton,
  Collapse,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tooltip,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  SmartToyOutlined as AgentIcon,
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  HelpOutline as HelpOutlineIcon,
} from '@mui/icons-material';
import { getApiUrl } from '../config/api';
import { useAppActions } from '../contexts/AppContext';
import {
  getDropdownItemSx,
  MENU_ACTION_TEXT_SIZE,
  CHAT_GEAR_MENU_AGENT_LIST_MAX_HEIGHT_PX,
  CHAT_GEAR_SCROLL_AREA_NO_VISIBLE_SCROLLBAR_SX,
} from '../constants/menuStyles';
import ChatGearMyAgentsTab from './ChatGearMyAgentsTab';
import { getOrchestratorAgentTitleRu } from '../utils/orchestratorAgentDisplay';

/** Как в настройках «Агенты» → список в агентном режиме (ответ /api/agent/agents). */
export interface OrchestratorAgentRow {
  name: string;
  description: string;
  capabilities: string[];
  tools_count: number;
  is_active: boolean;
  agent_id: string;
  tools?: Array<{
    name: string;
    description: string;
    is_active: boolean;
    instruction: string;
  }>;
  usage_examples?: string[];
}

interface LangGraphStatusPayload {
  is_active?: boolean;
  orchestrator_active?: boolean;
}

interface ChatGearAgentsPanelProps {
  isDarkMode: boolean;
  /** Агентная архитектура инициализирована (режим direct/agent подключается при включении агента здесь) */
  canUseAgents: boolean;
}

export default function ChatGearAgentsPanel({ isDarkMode, canUseAgents }: ChatGearAgentsPanelProps) {
  const { showNotification } = useAppActions();
  const showNotificationRef = useRef(showNotification);
  showNotificationRef.current = showNotification;

  const [agents, setAgents] = useState<OrchestratorAgentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [agentSearch, setAgentSearch] = useState('');
  const [expandedAgentKey, setExpandedAgentKey] = useState<string | null>(null);
  const [langgraphStatus, setLanggraphStatus] = useState<LangGraphStatusPayload | null>(null);
  const [agentStatusOrchestratorActive, setAgentStatusOrchestratorActive] = useState<boolean | undefined>(undefined);
  const [orchestratorConfirmOpen, setOrchestratorConfirmOpen] = useState(false);
  const [pendingOrchestratorOff, setPendingOrchestratorOff] = useState(false);
  const [agentsSubtab, setAgentsSubtab] = useState<'standard' | 'my'>('standard');

  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const muted = isDarkMode ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)';
  const text = isDarkMode ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.9)';
  const border = isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
  const placeholderColor = isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.35)';
  const menuDividerBorder = isDarkMode ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)';
  const subtleColor = isDarkMode ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.45)';

  const pullAgentsFromServer = useCallback(async (): Promise<OrchestratorAgentRow[]> => {
    const response = await fetch(getApiUrl('/api/agent/agents'));
    if (!response.ok) throw new Error('agents');
    const data = await response.json();
    return data.agents || [];
  }, []);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const list = await pullAgentsFromServer();
      setAgents(list);
    } catch {
      showNotificationRef.current('error', 'Не удалось загрузить список агентов');
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, [pullAgentsFromServer]);

  const refreshAgentsQuiet = useCallback(async () => {
    try {
      const list = await pullAgentsFromServer();
      setAgents(list);
    } catch {
      /* оставляем предыдущее состояние */
    }
  }, [pullAgentsFromServer]);

  const loadLanggraphStatus = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/langgraph/status'));
      if (response.ok) {
        const data = await response.json();
        setLanggraphStatus(data.langgraph_status ?? null);
      }
    } catch {
      /* ignore */
    }
  }, []);

  const loadAgentStatusOrchestrator = useCallback(async () => {
    try {
      const response = await fetch(getApiUrl('/api/agent/status'));
      if (response.ok) {
        const data = await response.json();
        setAgentStatusOrchestratorActive(data.orchestrator_active);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!canUseAgents) return;
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const list = await pullAgentsFromServer();
        if (!cancelled) setAgents(list);
      } catch {
        if (!cancelled) {
          showNotificationRef.current('error', 'Не удалось загрузить список агентов');
          setAgents([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    void loadLanggraphStatus();
    void loadAgentStatusOrchestrator();
    return () => {
      cancelled = true;
    };
  }, [canUseAgents, pullAgentsFromServer, loadLanggraphStatus, loadAgentStatusOrchestrator]);

  useEffect(() => {
    if (!canUseAgents) return;
    const onChange = () => {
      void loadLanggraphStatus();
      void loadAgentStatusOrchestrator();
    };
    window.addEventListener('astrachatAgentStatusChanged', onChange);
    return () => window.removeEventListener('astrachatAgentStatusChanged', onChange);
  }, [canUseAgents, loadLanggraphStatus, loadAgentStatusOrchestrator]);

  const agentKey = useCallback((a: OrchestratorAgentRow) => a.agent_id || a.name, []);

  const filteredAgents = useMemo(() => {
    const q = agentSearch.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter((a) => {
      const titleRu = getOrchestratorAgentTitleRu(a.agent_id, a.name);
      const blob = [titleRu, a.name, a.description, a.agent_id, ...(a.capabilities || [])].join(' ').toLowerCase();
      return blob.includes(q);
    });
  }, [agents, agentSearch]);

  const maybeSwitchToDirectIfNoAgentsActive = useCallback(async () => {
    try {
      const list = await pullAgentsFromServer();
      const anyActive = list.some((a) => a.is_active);
      if (!anyActive) {
        await fetch(getApiUrl('/api/agent/mode'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'direct' }),
        });
      }
    } catch {
      /* ignore */
    }
  }, [pullAgentsFromServer]);

  /** Целевое состояние с MUI Switch (checked), без инверсии от устаревшего props. */
  const applyAgentStatus = useCallback(
    async (agentId: string, next: boolean) => {
      try {
        if (next) {
          const mr = await fetch(getApiUrl('/api/agent/mode'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'agent' }),
          });
          if (!mr.ok) throw new Error((await mr.text()) || 'Режим агента');
        }
        const ar = await fetch(getApiUrl(`/api/agent/agents/${encodeURIComponent(agentId)}/status`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: next }),
        });
        if (!ar.ok) throw new Error((await ar.text()) || 'Статус агента');
        if (!next) {
          await maybeSwitchToDirectIfNoAgentsActive();
        }
        await refreshAgentsQuiet();
        window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
        showNotificationRef.current('success', next ? 'Агент включён (все инструменты агента активны)' : 'Агент отключён');
      } catch (e) {
        showNotificationRef.current(
          'error',
          e instanceof Error ? e.message : 'Не удалось изменить агента',
        );
        await refreshAgentsQuiet();
      }
    },
    [maybeSwitchToDirectIfNoAgentsActive, refreshAgentsQuiet],
  );

  const applyToolStatus = useCallback(
    async (_agentId: string, toolName: string, next: boolean) => {
      try {
        const tr = await fetch(getApiUrl(`/api/agent/tool/${encodeURIComponent(toolName)}/status`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: next }),
        });
        if (!tr.ok) throw new Error((await tr.text()) || 'Статус инструмента');
        await refreshAgentsQuiet();
        window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
        showNotificationRef.current('success', next ? 'Инструмент включён' : 'Инструмент отключён');
      } catch (e) {
        showNotificationRef.current(
          'error',
          e instanceof Error ? e.message : 'Не удалось изменить инструмент',
        );
        await refreshAgentsQuiet();
      }
    },
    [refreshAgentsQuiet],
  );

  const toggleExpand = useCallback((key: string) => {
    setExpandedAgentKey((prev) => (prev === key ? null : key));
  }, []);

  const orchestratorChecked =
    langgraphStatus?.orchestrator_active ?? agentStatusOrchestratorActive ?? false;

  const applyOrchestratorToggle = useCallback(
    async (isActive: boolean) => {
      try {
        const response = await fetch(getApiUrl('/api/agent/orchestrator/toggle'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_active: isActive }),
        });
        if (!response.ok) throw new Error('orchestrator');
        const data = await response.json();
        await loadLanggraphStatus();
        await loadAgentStatusOrchestrator();
        window.dispatchEvent(new CustomEvent('astrachatAgentStatusChanged'));
        showNotificationRef.current('success', data.message || (isActive ? 'Оркестратор включён' : 'Оркестратор отключён'));
      } catch {
        showNotificationRef.current('error', 'Не удалось переключить оркестратор');
        await loadLanggraphStatus();
      }
    },
    [loadLanggraphStatus, loadAgentStatusOrchestrator],
  );

  const handleOrchestratorSwitch = useCallback(
    (next: boolean) => {
      if (!next) {
        setPendingOrchestratorOff(true);
        setOrchestratorConfirmOpen(true);
        return;
      }
      void applyOrchestratorToggle(true);
    },
    [applyOrchestratorToggle],
  );

  const handleOrchestratorConfirmClose = useCallback(() => {
    setOrchestratorConfirmOpen(false);
    setPendingOrchestratorOff(false);
  }, []);

  const handleOrchestratorConfirm = useCallback(() => {
    if (pendingOrchestratorOff) {
      void applyOrchestratorToggle(false);
    }
    setOrchestratorConfirmOpen(false);
    setPendingOrchestratorOff(false);
  }, [pendingOrchestratorOff, applyOrchestratorToggle]);

  if (!canUseAgents) {
    return (
      <Box sx={{ p: 1.5, maxWidth: 320 }}>
        <Typography variant="body2" sx={{ color: muted, fontSize: MENU_ACTION_TEXT_SIZE, lineHeight: 1.45 }}>
          Список агентов доступен после инициализации агентной архитектуры в разделе{' '}
          <strong style={{ color: text }}>Настройки → Агенты</strong>. Включение агента здесь переводит чат в агентный режим.
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        flex: 1,
        height: '100%',
        maxHeight: '100%',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ flexShrink: 0 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            px: 1.5,
            py: 0.9,
            gap: 1,
            borderBottom: `1px solid ${menuDividerBorder}`,
          }}
        >
          <SearchIcon sx={{ color: subtleColor, fontSize: 16, flexShrink: 0 }} />
          <Box
            component="input"
            placeholder="Поиск агентов..."
            value={agentSearch}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAgentSearch(e.target.value)}
            sx={{
              flex: 1,
              minWidth: 0,
              bgcolor: 'transparent',
              border: 'none',
              outline: 'none',
              color: text,
              fontSize: MENU_ACTION_TEXT_SIZE,
              '&::placeholder': { color: placeholderColor },
            }}
          />
        </Box>
        <ToggleButtonGroup
          exclusive
          value={agentsSubtab}
          onChange={(_, v: 'standard' | 'my' | null) => {
            if (v) setAgentsSubtab(v);
          }}
          fullWidth
          size="small"
          sx={{
            flexShrink: 0,
            px: 1.25,
            py: 0.5,
            gap: 0.5,
            borderBottom: `1px solid ${menuDividerBorder}`,
            '& .MuiToggleButtonGroup-grouped': {
              border: `1px solid ${border}`,
              borderRadius: '8px !important',
              flex: 1,
              py: 0.4,
              textTransform: 'none',
              fontSize: MENU_ACTION_TEXT_SIZE,
              fontWeight: 500,
            },
          }}
        >
          <ToggleButton value="standard">Стандартные агенты</ToggleButton>
          <ToggleButton value="my">Мои агенты</ToggleButton>
        </ToggleButtonGroup>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
            px: 1.5,
            py: 0.75,
            borderBottom: `1px solid ${menuDividerBorder}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
            <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, fontWeight: 500, color: text }}>
              Оркестратор
            </Typography>
            <Tooltip
              title="Оркестратор автоматически выберет подходящего агента для задачи (как в настройках AstraChat)."
              arrow
            >
              <IconButton
                size="small"
                sx={{
                  p: 0,
                  ml: 0.25,
                  opacity: 0.7,
                  '&:hover': { opacity: 1, '& .MuiSvgIcon-root': { color: 'primary.main' } },
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <HelpOutlineIcon fontSize="small" sx={{ color: muted }} />
              </IconButton>
            </Tooltip>
          </Box>
          <Switch
            size="small"
            checked={orchestratorChecked}
            disabled={!langgraphStatus?.is_active}
            onChange={(e) => handleOrchestratorSwitch(e.target.checked)}
            color="primary"
            sx={{ flexShrink: 0, m: 0 }}
          />
        </Box>
      </Box>

      {agentsSubtab === 'my' ? (
        <ChatGearMyAgentsTab isDarkMode={isDarkMode} searchQuery={agentSearch} visible={agentsSubtab === 'my'} />
      ) : (
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
          {loading && agents.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={28} />
            </Box>
          ) : agents.length === 0 ? (
            <Typography variant="body2" sx={{ color: muted, fontSize: MENU_ACTION_TEXT_SIZE, px: 0.5 }}>
              Нет зарегистрированных агентов.
            </Typography>
          ) : filteredAgents.length === 0 ? (
            <Typography variant="body2" sx={{ color: muted, fontSize: MENU_ACTION_TEXT_SIZE, px: 0.5 }}>
              Ничего не найдено.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {filteredAgents.map((agent) => {
                const aid = agentKey(agent);
                const titleRu = getOrchestratorAgentTitleRu(agent.agent_id, agent.name);
                const expanded = expandedAgentKey === aid;
                return (
                  <Box
                    key={aid}
                    sx={{
                      border: `1px solid ${border}`,
                      borderRadius: 1,
                      overflow: 'hidden',
                      bgcolor: isDarkMode ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.02)',
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.75,
                        py: 0.65,
                        px: 0.85,
                        minWidth: 0,
                      }}
                    >
                      <AgentIcon sx={{ fontSize: 20, color: agent.is_active ? 'primary.main' : muted, flexShrink: 0 }} />
                      <Box
                        role="button"
                        tabIndex={0}
                        onClick={() => toggleExpand(aid)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            toggleExpand(aid);
                          }
                        }}
                        sx={{
                          flex: 1,
                          minWidth: 0,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          cursor: 'pointer',
                          textAlign: 'left',
                          border: 'none',
                          background: 'none',
                          p: 0,
                          color: 'inherit',
                          '&:hover .gear-agent-title': { textDecoration: 'underline' },
                        }}
                      >
                        <Typography
                          className="gear-agent-title"
                          sx={{
                            fontSize: MENU_ACTION_TEXT_SIZE,
                            fontWeight: 600,
                            color: text,
                            flex: 1,
                            minWidth: 0,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {titleRu}
                        </Typography>
                        <ExpandMoreIcon
                          sx={{
                            fontSize: 20,
                            color: muted,
                            flexShrink: 0,
                            transform: expanded ? 'rotate(180deg)' : 'none',
                            transition: 'transform 0.2s',
                          }}
                        />
                      </Box>
                      <FormControlLabel
                        onClick={(e) => e.stopPropagation()}
                        control={
                          <Switch
                            size="small"
                            checked={agent.is_active}
                            onChange={(_e, checked) => void applyAgentStatus(aid, checked)}
                            color="primary"
                          />
                        }
                        label=""
                        sx={{ m: 0, flexShrink: 0 }}
                      />
                    </Box>
                    <Collapse in={expanded}>
                      <Box
                        sx={{
                          px: 1,
                          pb: 1,
                          pt: 0,
                          borderTop: `1px solid ${border}`,
                          bgcolor: isDarkMode ? 'rgba(0,0,0,0.12)' : 'rgba(0,0,0,0.03)',
                        }}
                      >
                        <Typography
                          sx={{
                            fontSize: '0.72rem',
                            fontWeight: 600,
                            color: muted,
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                            mb: 0.5,
                            mt: 1,
                          }}
                        >
                          Что делает
                        </Typography>
                        <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, color: text, lineHeight: 1.45, mb: 1.25 }}>
                          {agent.description?.trim() || 'Описание не задано.'}
                        </Typography>
                        {agent.tools && agent.tools.length > 0 ? (
                          <>
                            <Typography
                              sx={{
                                fontSize: '0.72rem',
                                fontWeight: 600,
                                color: muted,
                                textTransform: 'uppercase',
                                letterSpacing: '0.04em',
                                mb: 0.75,
                              }}
                            >
                              Инструменты
                            </Typography>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                              {agent.tools.map((tool) => (
                                <Box
                                  key={tool.name}
                                  sx={{
                                    ...dropdownItemSx,
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: 1,
                                    py: 0.75,
                                    px: 0.75,
                                    borderRadius: 1,
                                    border: `1px solid ${border}`,
                                  }}
                                >
                                  <Box sx={{ flex: 1, minWidth: 0 }}>
                                    <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, fontWeight: 600, color: text }}>
                                      {tool.name}
                                    </Typography>
                                    {tool.description ? (
                                      <Typography
                                        sx={{ fontSize: '0.72rem', color: muted, mt: 0.25, lineHeight: 1.4 }}
                                      >
                                        {tool.description}
                                      </Typography>
                                    ) : null}
                                  </Box>
                                  <Switch
                                    size="small"
                                    checked={tool.is_active}
                                    disabled={!agent.is_active}
                                    onChange={(_e, checked) => void applyToolStatus(aid, tool.name, checked)}
                                    color="primary"
                                    sx={{ flexShrink: 0, mt: 0.15 }}
                                  />
                                </Box>
                              ))}
                            </Box>
                          </>
                        ) : (
                          <Typography sx={{ fontSize: '0.72rem', color: muted, fontStyle: 'italic' }}>
                            У этого агента нет отдельных инструментов в конфигурации.
                          </Typography>
                        )}
                      </Box>
                    </Collapse>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>
      )}

      <Dialog open={orchestratorConfirmOpen} onClose={handleOrchestratorConfirmClose} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'warning.main', display: 'flex', alignItems: 'center', gap: 1 }}>
          Внимание
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Вы отключаете LangGraph оркестратор.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            При отключении оркестратора вы будете работать с агентами напрямую и сами выбираете агента для задачи.
          </Typography>
          <Alert severity="warning" sx={{ mt: 1 }}>
            Убедитесь, что понимаете последствия.
          </Alert>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleOrchestratorConfirmClose} color="primary">
            Отмена
          </Button>
          <Button onClick={handleOrchestratorConfirm} color="warning" variant="contained">
            Да, отключить оркестратор
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
