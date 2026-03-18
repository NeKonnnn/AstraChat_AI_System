import React, { useState, useCallback, useEffect } from 'react';
import { Box, Typography, Popover, Tooltip, CircularProgress } from '@mui/material';
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  SmartToy as AgentIcon,
  Computer as ComputerIcon,
  Check as CheckIcon,
  PersonOff as NoAgentIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useAppActions } from '../contexts/AppContext';
import { getApiUrl } from '../config/api';
import {
  DROPDOWN_PANEL_SX,
  DROPDOWN_ITEM_SX,
  DROPDOWN_ITEM_HOVER_BG,
  DROPDOWN_CHEVRON_SX,
} from '../constants/menuStyles';
import { applyAgentModelAndSettings } from '../utils/applyAgentServer';
import { MODEL_SETTINGS_DEFAULT } from '../constants/modelSettingsStyles';

export interface Agent {
  id: number;
  name: string;
  description?: string;
  system_prompt: string;
  config?: Record<string, unknown>;
  author_id: string;
  author_name?: string;
}

interface ModelItem {
  name: string;
  path: string;
  size?: number;
  size_mb?: number;
}

const STORAGE_AGENT_ID = 'active_agent_id';
const STORAGE_AGENT_NAME = 'active_agent_name';
const STORAGE_AGENT_PROMPT = 'active_agent_prompt';

export function getActiveAgentFromStorage(): { id: number; name: string; system_prompt: string } | null {
  if (typeof window === 'undefined') return null;
  const id = localStorage.getItem(STORAGE_AGENT_ID);
  const name = localStorage.getItem(STORAGE_AGENT_NAME);
  const system_prompt = localStorage.getItem(STORAGE_AGENT_PROMPT) || '';
  if (!id || !name) return null;
  const numId = parseInt(id, 10);
  if (Number.isNaN(numId)) return null;
  return { id: numId, name, system_prompt };
}

type Submenu = 'agents' | 'models' | null;

interface AgentSelectorProps {
  isDarkMode?: boolean;
  maxWidth?: string | number;
  /** Ограничить ширину кнопки-триггера (для размещения в шапке) */
  triggerMaxWidth?: number;
  onAgentChange?: (agent: Agent | null) => void;
  onModelSelect?: (modelPath: string) => void;
}

export default function AgentSelector({ isDarkMode = true, maxWidth, triggerMaxWidth, onAgentChange, onModelSelect }: AgentSelectorProps) {
  const { token } = useAuth();
  const { showNotification } = useAppActions();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [loadingModelPath, setLoadingModelPath] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [submenu, setSubmenu] = useState<Submenu>(null);
  const [agentSearch, setAgentSearch] = useState('');
  const [modelSearch, setModelSearch] = useState('');
  const [activeAgent, setActiveAgent] = useState<{ id: number; name: string; system_prompt: string } | null>(() => getActiveAgentFromStorage());
  const [selectedModelPath, setSelectedModelPath] = useState<string>('');

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
      // silent
    } finally {
      setLoadingAgents(false);
    }
  }, [token]);

  const loadModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const [listResp, currentResp] = await Promise.all([
        fetch(getApiUrl('/api/models')),
        fetch(getApiUrl('/api/models/current')),
      ]);
      if (listResp.ok) {
        const data = await listResp.json();
        setModels(data.models || []);
      }
      if (currentResp.ok) {
        const current = await currentResp.json();
        const path = current?.path || '';
        setSelectedModelPath(path);
      }
    } catch {
      // silent
    } finally {
      setLoadingModels(false);
    }
  }, []);

  // При открытии меню подгружаем списки агентов и моделей
  useEffect(() => {
    if (anchorEl) {
      loadAgents();
      loadModels();
    }
  }, [anchorEl, loadAgents, loadModels]);

  // При монтировании узнаём текущую модель, чтобы показывать её название на кнопке
  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl('/api/models/current'))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data?.path) setSelectedModelPath(data.path);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onAgentSelected = () => setActiveAgent(getActiveAgentFromStorage());
    window.addEventListener('agentSelected', onAgentSelected);
    return () => window.removeEventListener('agentSelected', onAgentSelected);
  }, []);

  const handleOpen = (e: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(e.currentTarget);
    setSubmenu(null);
    setAgentSearch('');
    setModelSearch('');
  };

  const handleClose = () => {
    setAnchorEl(null);
    setSubmenu(null);
    setAgentSearch('');
    setModelSearch('');
  };

  /** Полные данные агента + на сервер: промпт, model_settings, загрузка модели (поле config.model или model_path). */
  const handleSelectAgent = async (agent: Agent) => {
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
      onAgentChange?.(full);
    };

    if (!token) {
      persistLocal();
      showNotification('info', 'Войдите в аккаунт, чтобы на сервер применились модель и настройки агента');
      handleClose();
      return;
    }

    setIsLoadingModel(true);
    setLoadingModelPath(modelPath || null);
    showNotification('info', modelPath ? `Загрузка модели агента «${full.name}»…` : `Применение настроек агента «${full.name}»…`);
    try {
      const applied = await applyAgentModelAndSettings(token, {
        system_prompt: full.system_prompt || '',
        model_path: modelPath || null,
        model_settings: rawSettings,
      });
      if (!applied.ok) {
        showNotification('error', `Агент не активирован: ${applied.message}`);
        handleClose();
        return;
      }
      if (modelPath) {
        setSelectedModelPath(modelPath);
        await loadModels();
      }
      persistLocal();
      showNotification(
        'success',
        modelPath
          ? `Агент «${full.name}»: модель загружена, настройки и промпт применены`
          : `Агент «${full.name}»: настройки и промпт применены (модель в агенте не задана)`
      );
      handleClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      showNotification('error', `Агент не активирован: ${msg}`);
      handleClose();
    } finally {
      setIsLoadingModel(false);
      setLoadingModelPath(null);
    }
  };

  const handleClearAgent = () => {
    localStorage.removeItem(STORAGE_AGENT_ID);
    localStorage.removeItem(STORAGE_AGENT_NAME);
    localStorage.removeItem(STORAGE_AGENT_PROMPT);
    setActiveAgent(null);
    onAgentChange?.(null);
    handleClose();
  };

  const handleSelectModel = async (modelPath: string) => {
    if (modelPath === selectedModelPath) {
      handleClose();
      return;
    }
    try {
      setIsLoadingModel(true);
      setLoadingModelPath(modelPath);
      const response = await fetch(getApiUrl('/api/models/load'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ model_path: modelPath }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setSelectedModelPath(modelPath);
        await loadModels(); // обновляем список и текущую модель с бэкенда
        showNotification('success', 'Модель успешно загружена');
        handleClose();
        onModelSelect?.(modelPath);
      } else {
        throw new Error(data.message || data.detail || 'Не удалось загрузить модель');
      }
    } catch (e: any) {
      showNotification('error', `Ошибка загрузки модели: ${e?.message || e}`);
    } finally {
      setIsLoadingModel(false);
      setLoadingModelPath(null);
    }
  };

  const filteredAgents = agents.filter(
    (a) => !agentSearch.trim() || a.name.toLowerCase().includes(agentSearch.toLowerCase())
  );
  const filteredModels = models.filter(
    (m) =>
      !modelSearch.trim() ||
      m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
      (m.path && m.path.toLowerCase().includes(modelSearch.toLowerCase()))
  );

  const leftPanelWidth = 185;
  const rightPanelWidth = 260;
  const windowSx = { ...DROPDOWN_PANEL_SX } as Record<string, unknown>;
  // Paper MUI Popover: убираем всё своё оформление, оставляем только flex-контейнер
  const paperSx = {
    mt: 0.75,
    p: 0,
    overflow: 'visible',
    background: 'transparent !important',
    backgroundColor: 'transparent !important',
    boxShadow: 'none !important',
    backdropFilter: 'none',
    border: 'none',
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: '6px',
    maxWidth: '90vw',
  };

  // Надпись на кнопке: агент → имя агента; при загрузке — имя загружаемой модели; иначе текущая модель или «Агент / Модель»
  const getModelDisplayName = (path: string) => {
    if (!path) return '';
    const fromList = models.find((m) => m.path === path);
    if (fromList?.name) return fromList.name.replace(/\.gguf$/i, '');
    const fromPath = path.split(/[/\\]/).pop()?.replace(/\.gguf$/i, '') ?? path;
    return fromPath;
  };
  const triggerLabel = activeAgent
    ? activeAgent.name
    : loadingModelPath
      ? getModelDisplayName(loadingModelPath)
      : selectedModelPath
        ? getModelDisplayName(selectedModelPath)
        : 'Агент / Модель';

  const triggerSx = {
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    px: 1.25,
    py: 0.75,
    borderRadius: '10px',
    bgcolor: 'rgba(0,0,0,0.25)',
    border: '1px solid rgba(255,255,255,0.15)',
    cursor: 'pointer',
    userSelect: 'none' as const,
    transition: 'background 0.15s, border-color 0.15s',
    color: 'white',
    maxWidth: triggerMaxWidth ?? '100%',
    '&:hover': {
      bgcolor: 'rgba(0,0,0,0.35)',
      borderColor: 'rgba(255,255,255,0.3)',
    },
  };

  const leftEntrySx = (active: boolean) => ({
    ...DROPDOWN_ITEM_SX,
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    color: active ? 'white' : 'rgba(255,255,255,0.9)',
    fontWeight: active ? 600 : 400,
    bgcolor: active ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
  });

  return (
    <Box sx={{ maxWidth: maxWidth ?? '100%', width: '100%', mx: 'auto' }}>
      <Tooltip title={activeAgent ? `Агент: ${activeAgent.name}. Нажмите, чтобы сменить` : (loadingModelPath || selectedModelPath) ? `Модель: ${getModelDisplayName(loadingModelPath || selectedModelPath || '')}. Нажмите, чтобы сменить` : 'Выберите агента или модель'}>
        <Box onClick={isLoadingModel ? undefined : handleOpen} sx={{ ...triggerSx, cursor: isLoadingModel ? 'default' : 'pointer', opacity: isLoadingModel ? 0.9 : 1 }}>
          {activeAgent ? (
            <AgentIcon sx={{ fontSize: '1.1rem', color: 'rgba(255,255,255,0.9)', flexShrink: 0 }} />
          ) : (selectedModelPath || loadingModelPath) ? (
            <ComputerIcon sx={{ fontSize: '1.1rem', color: 'rgba(255,255,255,0.9)', flexShrink: 0 }} />
          ) : (
            <AgentIcon sx={{ fontSize: '1.1rem', color: 'rgba(255,255,255,0.9)', flexShrink: 0 }} />
          )}
          <Typography sx={{ fontSize: '0.875rem', fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {triggerLabel}
          </Typography>
          {isLoadingModel ? (
            <CircularProgress size={16} sx={{ color: 'rgba(255,255,255,0.9)', flexShrink: 0 }} />
          ) : (
            <ExpandMoreIcon sx={{ ...DROPDOWN_CHEVRON_SX, transform: anchorEl ? 'rotate(180deg)' : 'none', flexShrink: 0 }} />
          )}
        </Box>
      </Tooltip>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: paperSx } }}
      >
        <Box
          onMouseLeave={() => setSubmenu(null)}
          sx={{ display: 'flex', flexDirection: 'row', alignItems: 'flex-start', gap: '6px' }}
        >
        {/* Первое окошко: только две кнопки «Мои агенты» и «Модели» */}
        <Box sx={{ ...windowSx, width: leftPanelWidth, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ py: 0.5, px: 0.5 }}>
            <Box
              onMouseEnter={() => setSubmenu('agents')}
              sx={leftEntrySx(submenu === 'agents')}
            >
              <AgentIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.7)', flexShrink: 0 }} />
              <Typography sx={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>Агенты</Typography>
              {activeAgent && <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />}
              <ChevronRightIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.5)', flexShrink: 0 }} />
            </Box>
            <Box
              onMouseEnter={() => setSubmenu('models')}
              sx={leftEntrySx(submenu === 'models')}
            >
              <ComputerIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.7)', flexShrink: 0 }} />
              <Typography sx={{ flex: 1 }}>Модели</Typography>
              <ChevronRightIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.5)', flexShrink: 0 }} />
            </Box>
          </Box>
        </Box>

        {/* Второе окошко: появляется при наведении на «Мои агенты» или «Модели»; список — не более 4 пунктов по высоте, остальное скролл */}
        {submenu !== null && (
          <Box sx={{ ...windowSx, width: rightPanelWidth, display: 'flex', flexDirection: 'column' }}>
          {submenu === 'agents' && (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', px: 1.5, py: 0.9, gap: 1, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                <SearchIcon sx={{ color: 'rgba(255,255,255,0.35)', fontSize: 16, flexShrink: 0 }} />
                <Box
                  component="input"
                  placeholder="Поиск агентов..."
                  value={agentSearch}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAgentSearch(e.target.value)}
                  sx={{
                    flex: 1,
                    bgcolor: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: 'white',
                    fontSize: '0.82rem',
                    '&::placeholder': { color: 'rgba(255,255,255,0.3)' },
                  }}
                />
              </Box>
              <Box sx={{ maxHeight: 208, overflowY: 'auto', py: 0.5, '&::-webkit-scrollbar': { width: 3 }, '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 } }}>
                {loadingAgents ? (
                  <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                    <CircularProgress size={20} sx={{ color: 'rgba(255,255,255,0.5)' }} />
                  </Box>
                ) : (
                  <>
                    <Box onClick={handleClearAgent} sx={{ ...DROPDOWN_ITEM_SX, display: 'flex', alignItems: 'center', gap: 1, color: !activeAgent ? 'white' : 'rgba(255,255,255,0.7)', fontWeight: !activeAgent ? 600 : 400, bgcolor: !activeAgent ? DROPDOWN_ITEM_HOVER_BG : 'transparent', fontStyle: 'italic' }}>
                      <NoAgentIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.5)', flexShrink: 0 }} />
                      <Typography sx={{ flex: 1 }}>Без агента</Typography>
                      {!activeAgent && <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />}
                    </Box>
                    {filteredAgents.map((agent) => (
                      <Box
                        key={agent.id}
                        onClick={() => {
                          if (!isLoadingModel) void handleSelectAgent(agent);
                        }}
                        sx={{ ...DROPDOWN_ITEM_SX, display: 'flex', alignItems: 'center', gap: 1, color: activeAgent?.id === agent.id ? 'white' : 'rgba(255,255,255,0.9)', fontWeight: activeAgent?.id === agent.id ? 600 : 400, bgcolor: activeAgent?.id === agent.id ? DROPDOWN_ITEM_HOVER_BG : 'transparent', opacity: isLoadingModel ? 0.6 : 1, pointerEvents: isLoadingModel ? 'none' : 'auto' }}
                      >
                        <AgentIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.7)', flexShrink: 0 }} />
                        <Typography sx={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{agent.name}</Typography>
                        {activeAgent?.id === agent.id && <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />}
                      </Box>
                    ))}
                    {!loadingAgents && filteredAgents.length === 0 && !agentSearch.trim() && (
                      <Box sx={{ px: 1.5, py: 2, fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', textAlign: 'center' }}>Нет созданных агентов</Box>
                    )}
                    {!loadingAgents && agentSearch.trim() && filteredAgents.length === 0 && (
                      <Box sx={{ px: 1.5, py: 2, fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', textAlign: 'center' }}>Ничего не найдено</Box>
                    )}
                  </>
                )}
              </Box>
            </>
          )}

          {submenu === 'models' && (
            <>
              <Box sx={{ display: 'flex', alignItems: 'center', px: 1.5, py: 0.9, gap: 1, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                <SearchIcon sx={{ color: 'rgba(255,255,255,0.35)', fontSize: 16, flexShrink: 0 }} />
                <Box
                  component="input"
                  placeholder="Поиск моделей..."
                  value={modelSearch}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setModelSearch(e.target.value)}
                  disabled={isLoadingModel}
                  sx={{
                    flex: 1,
                    bgcolor: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: 'white',
                    fontSize: '0.82rem',
                    '&::placeholder': { color: 'rgba(255,255,255,0.3)' },
                  }}
                />
              </Box>
              <Box sx={{ maxHeight: 208, overflowY: 'auto', py: 0.5, '&::-webkit-scrollbar': { width: 3 }, '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 }, pointerEvents: isLoadingModel ? 'none' : 'auto' }}>
                {loadingModels ? (
                  <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                    <CircularProgress size={20} sx={{ color: 'rgba(255,255,255,0.5)' }} />
                  </Box>
                ) : (
                  <>
                    {filteredModels.map((model) => {
                      const isSelected = selectedModelPath === model.path && !loadingModelPath;
                      const isLoading = loadingModelPath === model.path;
                      return (
                        <Box
                          key={model.path}
                          onClick={isLoading ? undefined : () => handleSelectModel(model.path)}
                          sx={{
                            ...DROPDOWN_ITEM_SX,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1,
                            color: isSelected || isLoading ? 'white' : 'rgba(255,255,255,0.9)',
                            fontWeight: isSelected || isLoading ? 600 : 400,
                            bgcolor: isSelected || isLoading ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                          }}
                        >
                          <ComputerIcon sx={{ fontSize: 18, color: 'rgba(255,255,255,0.7)', flexShrink: 0 }} />
                          <Typography sx={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{model.name.replace('.gguf', '')}</Typography>
                          {isLoading ? (
                            <CircularProgress size={16} sx={{ color: 'rgba(255,255,255,0.8)', flexShrink: 0 }} />
                          ) : isSelected ? (
                            <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
                          ) : null}
                        </Box>
                      );
                    })}
                    {!loadingModels && filteredModels.length === 0 && (
                      <Box sx={{ px: 1.5, py: 2, fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', textAlign: 'center' }}>
                        {modelSearch.trim() ? 'Ничего не найдено' : 'Нет доступных моделей'}
                      </Box>
                    )}
                  </>
                )}
              </Box>
            </>
          )}
          </Box>
        )}
        </Box>
      </Popover>
    </Box>
  );
}
