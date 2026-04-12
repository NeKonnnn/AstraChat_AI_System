import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Box, Typography, Popover, Tooltip, CircularProgress } from '@mui/material';
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  SmartToy as AgentIcon,
  Computer as ComputerIcon,
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
  const [models, setModels] = useState<ModelItem[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [isLoadingModel, setIsLoadingModel] = useState(false);
  const [loadingModelPath, setLoadingModelPath] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  /** Ширина выпадающего окна = ширина кнопки-триггера */
  const [popoverPanelWidth, setPopoverPanelWidth] = useState<number | null>(null);
  const [modelSearch, setModelSearch] = useState('');
  const [activeAgent, setActiveAgent] = useState<{ id: number; name: string; system_prompt: string } | null>(() => getActiveAgentFromStorage());
  const [selectedModelPath, setSelectedModelPath] = useState<string>('');
  const { menuItemColor, menuItemHover, menuDividerBorder } = getMenuColors(isDarkMode);
  const windowSx = { ...getDropdownPanelSx(isDarkMode) } as Record<string, unknown>;
  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const iconColor = isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)';
  const mutedTextColor = isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)';
  const placeholderColor = isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.35)';
  const subtleColor = isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)';

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

  useEffect(() => {
    if (anchorEl) {
      loadModels();
    }
  }, [anchorEl, loadModels]);

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
    const el = e.currentTarget;
    setPopoverPanelWidth(Math.round(el.getBoundingClientRect().width));
    setAnchorEl(el);
    setModelSearch('');
  };

  const handleClose = () => {
    setAnchorEl(null);
    setModelSearch('');
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

  const filteredModels = models.filter(
    (m) =>
      !modelSearch.trim() ||
      m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
      (m.path && m.path.toLowerCase().includes(modelSearch.toLowerCase())),
  );

  const paperSx = useMemo(
    () => ({
      mt: 0.75,
      p: 0,
      overflow: 'hidden',
      background: 'transparent !important',
      backgroundColor: 'transparent !important',
      boxShadow: 'none !important',
      backdropFilter: 'none',
      border: 'none',
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      maxWidth: '90vw',
      boxSizing: 'border-box' as const,
      ...(popoverPanelWidth != null
        ? {
            width: `${popoverPanelWidth}px`,
            minWidth: `${popoverPanelWidth}px`,
            maxWidth: `min(90vw, ${popoverPanelWidth}px)`,
          }
        : {}),
    }),
    [popoverPanelWidth],
  );

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
        : 'Агенты / Модели';

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

  return (
    <Box sx={{ maxWidth: maxWidth ?? '100%', width: '100%', mx: 'auto' }}>
      <Tooltip
        title={
          activeAgent
            ? `Агент: ${activeAgent.name}. Смена агента — Инструменты → Агенты`
            : loadingModelPath || selectedModelPath
              ? `Модель: ${getModelDisplayName(loadingModelPath || selectedModelPath || '')}`
              : 'Список моделей. Агенты — в меню Инструменты'
        }
      >
        <Box onClick={isLoadingModel ? undefined : handleOpen} sx={{ ...triggerSx, cursor: isLoadingModel ? 'default' : 'pointer', opacity: isLoadingModel ? 0.9 : 1 }}>
          {activeAgent ? (
            <AgentIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          ) : loadingModelPath || selectedModelPath ? (
            <ComputerIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          ) : (
            <AgentIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
          )}
          <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {triggerLabel}
          </Typography>
          {isLoadingModel ? (
            <CircularProgress size={16} sx={{ color: mutedTextColor, flexShrink: 0 }} />
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
        slotProps={{
          paper: { sx: paperSx },
          transition: {
            onExited: () => setPopoverPanelWidth(null),
          },
        }}
      >
        <Box
          sx={{
            ...windowSx,
            width: popoverPanelWidth != null ? `${popoverPanelWidth}px` : '100%',
            minWidth: popoverPanelWidth != null ? `${popoverPanelWidth}px` : undefined,
            maxWidth: popoverPanelWidth != null ? `${popoverPanelWidth}px` : undefined,
            display: 'flex',
            flexDirection: 'column',
            boxSizing: 'border-box',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', px: 1.5, py: 0.9, gap: 1, borderBottom: `1px solid ${menuDividerBorder}` }}>
            <SearchIcon sx={{ color: subtleColor, fontSize: 16, flexShrink: 0 }} />
            <Box
              component="input"
              placeholder="Поиск моделей..."
              value={modelSearch}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setModelSearch(e.target.value)}
              disabled={isLoadingModel}
              sx={{
                flex: 1,
                minWidth: 0,
                bgcolor: 'transparent',
                border: 'none',
                outline: 'none',
                color: menuItemColor,
                fontSize: MENU_ACTION_TEXT_SIZE,
                '&::placeholder': { color: placeholderColor },
              }}
            />
          </Box>
          <Box
            sx={{
              maxHeight: 208,
              overflowY: 'auto',
              py: 0.5,
              '&::-webkit-scrollbar': { width: 3 },
              '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 },
              pointerEvents: isLoadingModel ? 'none' : 'auto',
            }}
          >
            {loadingModels ? (
              <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                <CircularProgress size={20} sx={{ color: subtleColor }} />
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
                        {model.name.replace('.gguf', '')}
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
              </>
            )}
          </Box>
        </Box>
      </Popover>
    </Box>
  );
}
