import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Popover,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Search as SearchIcon,
  ExpandMore as ExpandMoreIcon,
  ChevronRight as ChevronRightIcon,
  Computer as ComputerIcon,
  Check as CheckIcon,
} from '@mui/icons-material';
import { useAppActions } from '../contexts/AppContext';
import { getApiUrl } from '../config/api';
import {
  getDropdownItemSx,
  DROPDOWN_CHEVRON_SX,
  getDropdownPanelSx,
  getMenuColors,
  MENU_ACTION_TEXT_SIZE,
} from '../constants/menuStyles';

export type RagModelKind = 'embedding' | 'reranker';

interface RagModelRow {
  path: string;
  name: string;
  display_name: string;
  source: string;
  kind: RagModelKind;
  description?: string;
  available?: boolean;
}

interface RagModelSelectorProps {
  kind: RagModelKind;
  isDarkMode: boolean;
  disabled?: boolean;
  triggerMaxWidth?: number;
  onModelSelect?: (modelPath: string) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  local: 'local-rag',
  huggingface: 'huggingface',
};

const LEFT_PANEL_W = 185;
const RIGHT_PANEL_W = 260;

export default function RagModelSelector({
  kind,
  isDarkMode,
  disabled = false,
  triggerMaxWidth = 220,
  onModelSelect,
}: RagModelSelectorProps) {
  const [models, setModels] = useState<RagModelRow[]>([]);
  const [selectedPath, setSelectedPath] = useState('');
  const [loadingModels, setLoadingModels] = useState(false);
  const [isSelecting, setIsSelecting] = useState(false);
  const [loadingModelPath, setLoadingModelPath] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [modelSearch, setModelSearch] = useState('');
  const [sourcesSubmenuOpen, setSourcesSubmenuOpen] = useState(false);
  const [activeSource, setActiveSource] = useState<string | null>(null);
  const { showNotification } = useAppActions();

  const { menuItemColor, menuItemHover, menuDividerBorder } = getMenuColors(isDarkMode);
  const windowSx = { ...getDropdownPanelSx(isDarkMode) } as Record<string, unknown>;
  const dropdownItemSx = useMemo(() => getDropdownItemSx(isDarkMode), [isDarkMode]);
  const iconColor = isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)';
  const mutedTextColor = isDarkMode ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)';
  const placeholderColor = isDarkMode ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.35)';
  const subtleColor = isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)';

  const loadModels = useCallback(async () => {
    try {
      setLoadingModels(true);
      const response = await fetch(getApiUrl(`/api/rag/models?type=${kind}`));
      if (!response.ok) return;
      const data = await response.json();
      const rows: RagModelRow[] = data?.models?.[kind] ?? [];
      setModels(rows);
      setOffline(Boolean(data?.offline));
      const current = data?.current?.[kind];
      if (current?.path) {
        setSelectedPath(current.path);
      }
    } catch {
      // сервис может быть недоступен
    } finally {
      setLoadingModels(false);
    }
  }, [kind]);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const getDisplayName = useCallback(
    (path: string) => {
      const model = models.find((m) => m.path === path);
      if (model?.display_name) return model.display_name;
      return path.split('/').pop() || path;
    },
    [models],
  );

  const sources = useMemo(() => {
    const map = new Map<string, RagModelRow[]>();
    for (const m of models) {
      const label = SOURCE_LABELS[m.source] || m.source || 'local';
      const bucket = map.get(label);
      if (bucket) bucket.push(m);
      else map.set(label, [m]);
    }
    return Array.from(map.entries()).map(([label, items]) => ({ label, items }));
  }, [models]);

  const filteredModels = useMemo(() => {
    const base = sources.find((s) => s.label === activeSource)?.items ?? [];
    if (!modelSearch.trim()) return base;
    const q = modelSearch.toLowerCase();
    return base.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.display_name.toLowerCase().includes(q) ||
        m.path.toLowerCase().includes(q),
    );
  }, [sources, activeSource, modelSearch]);

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    if (disabled || isSelecting) return;
    setAnchorEl(event.currentTarget);
    setModelSearch('');
    if (sources.length > 0) {
      const firstWithSelection = sources.find((s) => s.items.some((m) => m.path === selectedPath));
      setActiveSource(firstWithSelection?.label ?? sources[0].label);
      setSourcesSubmenuOpen(true);
    }
  };

  const handleClose = () => {
    setAnchorEl(null);
    setSourcesSubmenuOpen(false);
    setModelSearch('');
  };

  const handleSelect = async (modelPath: string) => {
    if (modelPath === selectedPath) {
      handleClose();
      return;
    }
    const prevPath = selectedPath;
    try {
      setIsSelecting(true);
      setLoadingModelPath(modelPath);
      const response = await fetch(getApiUrl('/api/rag/models/select'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_type: kind, model_path: modelPath }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof data?.detail === 'string'
            ? data.detail
            : data?.message || 'Не удалось загрузить модель',
        );
      }
      setSelectedPath(modelPath);
      showNotification('success', 'Модель RAG успешно загружена');
      handleClose();
      onModelSelect?.(modelPath);
      await loadModels();
    } catch (err: unknown) {
      setSelectedPath(prevPath);
      const message = err instanceof Error ? err.message : String(err);
      showNotification('error', `Ошибка загрузки модели: ${message}`);
    } finally {
      setIsSelecting(false);
      setLoadingModelPath(null);
    }
  };

  const triggerLabel = loadingModelPath
    ? getDisplayName(loadingModelPath)
    : selectedPath
      ? getDisplayName(selectedPath)
      : kind === 'embedding'
        ? 'Выбрать эмбеддинг'
        : 'Выбрать реранкер';

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

  if (loadingModels && models.length === 0) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.5 }}>
        <CircularProgress size={16} sx={{ color: subtleColor }} />
        <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, color: subtleColor }}>
          Загрузка моделей…
        </Typography>
      </Box>
    );
  }

  if (models.length === 0) {
    return (
      <Typography sx={{ fontSize: MENU_ACTION_TEXT_SIZE, color: subtleColor }}>
        Модели {kind === 'embedding' ? 'эмбеддингов' : 'cross-encoder'} недоступны
        {offline ? ' (офлайн-режим)' : ''}
      </Typography>
    );
  }

  return (
    <Box sx={{ maxWidth: '100%', width: '100%' }}>
      <Tooltip
        title={
          selectedPath
            ? `${kind === 'embedding' ? 'Эмбеддинг' : 'Cross-encoder'}: ${getDisplayName(selectedPath)}. Наведите на источник в меню`
            : `Выберите ${kind === 'embedding' ? 'модель эмбеддингов' : 'cross-encoder'}`
        }
      >
        <Box
          onClick={isSelecting ? undefined : handleOpen}
          sx={{
            ...triggerSx,
            cursor: disabled || isSelecting ? 'default' : 'pointer',
            opacity: disabled || isSelecting ? 0.9 : 1,
            pointerEvents: disabled ? 'none' : 'auto',
          }}
        >
          <ComputerIcon sx={{ fontSize: '1.1rem', color: mutedTextColor, flexShrink: 0 }} />
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
          {isSelecting ? (
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
        slotProps={{ paper: { sx: paperSx } }}
      >
        <Box
          onMouseLeave={() => setSourcesSubmenuOpen(false)}
          sx={{ display: 'flex', flexDirection: 'row', alignItems: 'flex-start', gap: '6px' }}
        >
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
              {sources.map((src) => {
                const isActive = sourcesSubmenuOpen && src.label === activeSource;
                const hasSelectedModel = src.items.some((m) => m.path === selectedPath);
                return (
                  <Box
                    key={src.label}
                    onMouseEnter={() => {
                      setActiveSource(src.label);
                      setSourcesSubmenuOpen(true);
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
                      {src.label}
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
              })}
            </Box>
          </Box>

          {sourcesSubmenuOpen ? (
            <Box
              sx={{
                ...windowSx,
                width: RIGHT_PANEL_W,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
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
                  disabled={isSelecting}
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

              <Box
                sx={{
                  maxHeight: 260,
                  overflowY: 'auto',
                  py: 0.5,
                  pointerEvents: isSelecting ? 'none' : 'auto',
                  scrollbarWidth: 'none',
                  msOverflowStyle: 'none',
                  '&::-webkit-scrollbar': { display: 'none' },
                }}
              >
                {filteredModels.map((model) => {
                  const isSelected = selectedPath === model.path && !loadingModelPath;
                  const isLoading = loadingModelPath === model.path;
                  const unavailable = model.available === false;
                  return (
                    <Box
                      key={model.path}
                      onClick={unavailable || isLoading ? undefined : () => handleSelect(model.path)}
                      sx={{
                        ...dropdownItemSx,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        opacity: unavailable ? 0.45 : 1,
                        color: isSelected || isLoading ? menuItemColor : mutedTextColor,
                        fontWeight: isSelected || isLoading ? 600 : 400,
                        bgcolor: isSelected || isLoading ? menuItemHover : 'transparent',
                        cursor: unavailable ? 'not-allowed' : 'pointer',
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
                        {model.display_name}
                      </Typography>
                      {isLoading ? (
                        <CircularProgress size={16} sx={{ color: mutedTextColor, flexShrink: 0 }} />
                      ) : isSelected ? (
                        <CheckIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
                      ) : null}
                    </Box>
                  );
                })}
                {filteredModels.length === 0 && (
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
