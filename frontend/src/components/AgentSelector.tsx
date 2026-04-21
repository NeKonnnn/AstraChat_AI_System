import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Box, Typography, Popover, Tooltip, CircularProgress } from '@mui/material';
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  Computer as ComputerIcon,
  SmartToy as AgentIcon,
  Check as CheckIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useAppActions } from '../contexts/AppContext';
import { getApiUrl } from '../config/api';
import {
  getDropdownItemSx,
  DROPDOWN_CHEVRON_SX,
  getDropdownPanelSx,
  getMenuColors,
  MENU_ACTION_TEXT_SIZE,
} from '../constants/menuStyles';

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
  /** model_id со стороны провайдера. */
  name: string;
  /** Полный путь ``<provider_id>/<model_id>`` (новый формат) или legacy ``llm-svc://...``. */
  path: string;
  /** Человеко-читаемое имя (бэкенд возвращает для external-провайдеров). */
  display_name?: string;
  size?: number;
  size_mb?: number;
  /** id провайдера (llm-svc/vllm/ollama/openai/anthropic/...). */
  provider_id?: string;
  /** kind провайдера, определяет иконку/цвет. */
  provider_kind?: string;
  /** Legacy-алиас для старых бэкендов (== provider_id). */
  llm_host_id?: string;
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

interface AgentSelectorProps {
  isDarkMode?: boolean;
  maxWidth?: string | number;
  triggerMaxWidth?: number;
  onAgentChange?: (agent: Agent | null) => void;
  onModelSelect?: (modelPath: string) => void;
}

const LEFT_PANEL_W = 185;
const RIGHT_PANEL_W = 260;

export default function AgentSelector({
  isDarkMode = true,
  maxWidth,
  triggerMaxWidth,
  onAgentChange,
  onModelSelect,
}: AgentSelectorProps) {
  const { token } = useAuth();
  const { showNotification } = useAppActions();

  const [models, setModels] = useState<ModelItem[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [loadingModelPath, setLoadingModelPath] = useState<string | null>(null);
  const [selectedModelPath, setSelectedModelPath] = useState('');
  const [activeAgent, setActiveAgent] = useState<{ id: number; name: string; system_prompt: string } | null>(
    () => getActiveAgentFromStorage(),
  );

  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [modelSearch, setModelSearch] = useState('');
  /** Правая панель со списком моделей — только при наведении на строку подключения. */
  const [modelsSubmenuOpen, setModelsSubmenuOpen] = useState(false);
  /** Какое подключение сейчас активно (наведено) в левой панели. */
  const [activeConnectionLabel, setActiveConnectionLabel] = useState<string | null>(null);

  const { menuItemColor, menuItemHover, menuDividerBorder } = getMenuColors(isDarkMode);
  const windowSx = { ...getDropdownPanelSx(isDarkMode) } as Record<string, unknown>;
  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const iconColor = isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)';
  const mutedTextColor = isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)';
  const placeholderColor = isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.35)';
  const subtleColor = isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)';

  // ─── Helpers ─────────────────────────────────────────────────────────────────

  /**
   * Метка «подключения» — это id провайдера в новой архитектуре (llm-svc,
   * vllm, ollama, openai, anthropic и т.п.). Для legacy-путей ``llm-svc://host/``
   * дополнительно парсим host из path.
   */
  const getConnectionLabel = useCallback((model: ModelItem): string => {
    const pid = (model.provider_id || model.llm_host_id || '').trim();
    if (pid) return pid;
    const path = model.path || '';
    if (!path) return 'local';
    if (path.startsWith('llm-svc://')) {
      const rest = path.slice('llm-svc://'.length);
      const host = rest.includes('/') ? rest.split('/')[0] : rest;
      return host || 'llm-svc';
    }
    if (path.includes('/')) {
      return path.split('/')[0] || 'local';
    }
    return 'local';
  }, []);

  const getModelDisplayName = useCallback(
    (path: string) => {
      if (!path) return '';
      const fromList = models.find((m) => m.path === path);
      const raw = fromList?.display_name || fromList?.name;
      if (raw) return raw.replace(/\.gguf$/i, '');
      return path.split(/[/\\]/).pop()?.replace(/\.gguf$/i, '') ?? path;
    },
    [models],
  );

  // ─── Data loading ─────────────────────────────────────────────────────────────

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
        setSelectedModelPath(current?.path || '');
      }
    } catch {
      /* silent */
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    if (anchorEl) {
      void loadModels();
    }
  }, [anchorEl, loadModels]);

  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl('/api/models/current'))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (!cancelled && data?.path) setSelectedModelPath(data.path); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onAgentSelected = () => setActiveAgent(getActiveAgentFromStorage());
    window.addEventListener('agentSelected', onAgentSelected);
    return () => window.removeEventListener('agentSelected', onAgentSelected);
  }, []);

  // ─── Open / close ─────────────────────────────────────────────────────────────

  const handleOpen = (e: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(e.currentTarget);
    setModelSearch('');
    setModelsSubmenuOpen(false);
    setActiveConnectionLabel(null);
  };

  const handleClose = () => {
    setAnchorEl(null);
    setModelSearch('');
    setModelsSubmenuOpen(false);
    setActiveConnectionLabel(null);
  };

  // ─── Model select ─────────────────────────────────────────────────────────────

  const handleSelectModel = async (modelPath: string) => {
    if (modelPath === selectedModelPath) { handleClose(); return; }
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
        await loadModels();
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

  // ─── Derived ─────────────────────────────────────────────────────────────────

  /** Список подключений (уникальные метки) с их моделями. */
  const connections = useMemo(() => {
    const map = new Map<string, ModelItem[]>();
    for (const m of models) {
      const label = getConnectionLabel(m);
      const bucket = map.get(label);
      if (bucket) bucket.push(m);
      else map.set(label, [m]);
    }
    return Array.from(map.entries()).map(([label, items]) => ({ label, items }));
  }, [models, getConnectionLabel]);

  /** Модели активного подключения, отфильтрованные по поиску. */
  const filteredModels = useMemo(() => {
    const base = connections.find((c) => c.label === activeConnectionLabel)?.items ?? [];
    if (!modelSearch.trim()) return base;
    const q = modelSearch.toLowerCase();
    return base.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        (m.display_name || '').toLowerCase().includes(q) ||
        m.path.toLowerCase().includes(q),
    );
  }, [connections, activeConnectionLabel, modelSearch]);

  const triggerLabel = activeAgent
    ? activeAgent.name
    : loadingModelPath
      ? getModelDisplayName(loadingModelPath)
      : selectedModelPath
        ? getModelDisplayName(selectedModelPath)
        : 'Агенты / Модели';

  // ─── Styles ──────────────────────────────────────────────────────────────────

  /** Стиль строки левой панели. */
  const leftEntrySx = (active: boolean) => ({
    ...dropdownItemSx,
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    color: active ? menuItemColor : mutedTextColor,
    fontWeight: active ? 600 : 400,
    bgcolor: active ? menuItemHover : 'transparent',
  });

  const triggerSx = {
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    px: 1.25,
    py: 0.75,
    borderRadius: '10px',
    bgcolor: isDarkMode ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.9)',
    border: isDarkMode ? '1px solid rgba(255,255,255,0.15)' : '1px solid rgba(0,0,0,0.12)',
    cursor: 'pointer',
    userSelect: 'none' as const,
    transition: 'background 0.15s, border-color 0.15s',
    color: menuItemColor,
    maxWidth: triggerMaxWidth ?? '100%',
    width: triggerMaxWidth != null ? `${triggerMaxWidth}px` : '100%',
    boxSizing: 'border-box' as const,
    '&:hover': {
      bgcolor: isDarkMode ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,1)',
      borderColor: isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.2)',
    },
  };

  // Paper Popover: прозрачный враппер, без тени — каждая карточка стилизуется сама
  const paperSx = {
    mt: 0.75,
    p: 0,
    overflow: 'visible',
    background: 'transparent !important',
    backgroundColor: 'transparent !important',
    boxShadow: 'none !important',
    backdropFilter: 'none',
    border: 'none',
    maxWidth: '96vw',
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <Box sx={{ maxWidth: maxWidth ?? '100%', width: '100%', mx: 'auto' }}>
      <Tooltip
        title={
          activeAgent
            ? `Агент: ${activeAgent.name}. Модели — наведите «Модели» в меню. Смена агента: Инструменты → Агенты`
            : loadingModelPath || selectedModelPath
              ? `Модель: ${getModelDisplayName(loadingModelPath || selectedModelPath || '')}. Список моделей — наведите «Модели»`
              : 'Модели — наведите на пункт «Модели». Агенты — в меню Инструменты'
        }
      >
        <Box
          onClick={isLoadingModel ? undefined : handleOpen}
          sx={{ ...triggerSx, cursor: isLoadingModel ? 'default' : 'pointer', opacity: isLoadingModel ? 0.9 : 1 }}
        >
          {activeAgent ? (
            <AgentIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          ) : loadingModelPath || selectedModelPath ? (
            <ComputerIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          ) : (
            <AgentIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          )}
          <Typography
            sx={{
              fontSize: MENU_ACTION_TEXT_SIZE,
              fontWeight: 500,
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {triggerLabel}
          </Typography>
          {isLoadingModel ? (
            <CircularProgress size={16} sx={{ color: mutedTextColor, flexShrink: 0 }} />
          ) : (
            <ExpandMoreIcon
              sx={{ ...DROPDOWN_CHEVRON_SX, transform: anchorEl ? 'rotate(180deg)' : 'none', flexShrink: 0 }}
            />
          )}
        </Box>
      </Tooltip>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{
          paper: { sx: paperSx },
        }}
      >
        {/* Уход мыши с области обеих карточек — скрывает правую панель */}
        <Box
          onMouseLeave={() => setModelsSubmenuOpen(false)}
          sx={{ display: 'flex', flexDirection: 'row', alignItems: 'flex-start', gap: '6px' }}
        >
          {/* ── Левая карточка: список подключений ─────────────── */}
          <Box
            sx={{
              ...windowSx,
              width: LEFT_PANEL_W,
              flexShrink: 0,
              display: 'flex',
              flexDirection: 'column',
              maxHeight: 300,
              overflowY: 'auto',
              scrollbarWidth: 'none',
              msOverflowStyle: 'none',
              '&::-webkit-scrollbar': { display: 'none' },
            }}
          >
            <Box sx={{ py: 0.5, px: 0.5 }}>
              {connections.length === 0 ? (
                <Box sx={{ px: 1.5, py: 2, fontSize: MENU_ACTION_TEXT_SIZE, color: subtleColor, textAlign: 'center' }}>
                  {loadingModels ? '' : 'Нет подключений'}
                </Box>
              ) : (
                connections.map((conn) => {
                  const isActive = modelsSubmenuOpen && conn.label === activeConnectionLabel;
                  const hasSelectedModel = conn.items.some((m) => m.path === selectedModelPath);
                  return (
                    <Box
                      key={conn.label}
                      onMouseEnter={() => {
                        setActiveConnectionLabel(conn.label);
                        setModelsSubmenuOpen(true);
                        setModelSearch('');
                      }}
                      sx={leftEntrySx(isActive || hasSelectedModel)}
                    >
                      <ComputerIcon sx={{ fontSize: 18, color: iconColor, flexShrink: 0 }} />
                      <Typography
                        sx={{
                          flex: 1,
                          minWidth: 0,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: MENU_ACTION_TEXT_SIZE,
                        }}
                      >
                        {conn.label}
                      </Typography>
                      <ChevronRightIcon
                        sx={{
                          fontSize: 18,
                          color: subtleColor,
                          flexShrink: 0,
                          transform: isActive ? 'rotate(90deg)' : 'none',
                          transition: 'transform 0.15s',
                        }}
                      />
                    </Box>
                  );
                })
              )}
              {loadingModels && (
                <Box sx={{ py: 1.5, display: 'flex', justifyContent: 'center' }}>
                  <CircularProgress size={18} sx={{ color: subtleColor }} />
                </Box>
              )}
            </Box>
          </Box>

          {/* ── Правая карточка: список моделей подключения ─────── */}
          {modelsSubmenuOpen ? (
            <Box
              sx={{
                ...windowSx,
                width: RIGHT_PANEL_W,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {/* Поиск */}
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
                  placeholder="Поиск моделей..."
                  value={modelSearch}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setModelSearch(e.target.value)}
                  disabled={isLoadingModel}
                  sx={{
                    flex: 1,
                    bgcolor: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: menuItemColor,
                    fontSize: MENU_ACTION_TEXT_SIZE,
                    '&::placeholder': { color: placeholderColor },
                  }}
                />
              </Box>

              {/* Список */}
              <Box
                sx={{
                  maxHeight: 260,
                  overflowY: 'auto',
                  py: 0.5,
                  pointerEvents: isLoadingModel ? 'none' : 'auto',
                  scrollbarWidth: 'none',
                  msOverflowStyle: 'none',
                  '&::-webkit-scrollbar': { display: 'none' },
                }}
              >
                {filteredModels.map((model) => {
                  const isSelected = selectedModelPath === model.path && !loadingModelPath;
                  const isLoading = loadingModelPath === model.path;
                  return (
                    <Box
                      key={model.path}
                      onClick={isLoading ? undefined : () => handleSelectModel(model.path)}
                      sx={{
                        ...dropdownItemSx,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        color: isSelected || isLoading ? menuItemColor : mutedTextColor,
                        fontWeight: isSelected || isLoading ? 600 : 400,
                        bgcolor: isSelected || isLoading ? menuItemHover : 'transparent',
                      }}
                    >
                      <ComputerIcon sx={{ fontSize: 18, color: iconColor, flexShrink: 0 }} />
                      <Typography
                        sx={{
                          flex: 1,
                          minWidth: 0,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          fontSize: MENU_ACTION_TEXT_SIZE,
                        }}
                      >
                        {(model.display_name || model.name || '').replace(/\.gguf$/i, '')}
                      </Typography>
                      {isLoading ? (
                        <CircularProgress size={16} sx={{ color: mutedTextColor, flexShrink: 0 }} />
                      ) : isSelected ? (
                        <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
                      ) : null}
                    </Box>
                  );
                })}
                {!loadingModels && filteredModels.length === 0 && (
                  <Box sx={{ px: 1.5, py: 2, fontSize: MENU_ACTION_TEXT_SIZE, color: subtleColor, textAlign: 'center' }}>
                    {modelSearch.trim() ? 'Ничего не найдено' : 'Нет доступных моделей'}
                  </Box>
                )}
              </Box>
            </Box>
          ) : null}
        </Box>
      </Popover>
    </Box>
  );
}
