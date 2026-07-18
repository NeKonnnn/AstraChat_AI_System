import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  TextField,
  Button,
  IconButton,
  Slider,
  Switch,
  FormControlLabel,
  FormControl,
  InputLabel,
  OutlinedInput,
  InputAdornment,
  Divider,
  Popover,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  ContentCopy as CopyIcon,
  Save as SaveIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import {
  getFormFieldInputSx,
  getDropdownPopoverPaperSx,
  DROPDOWN_ITEM_SX,
  DROPDOWN_ITEM_HOVER_BG,
  DROPDOWN_CHEVRON_SX,
} from '../constants/menuStyles';
import { getSidebarPanelBackground } from '../constants/sidebarPanelColor';
import ModelSettingsFields from './ModelSettingsFields';
import { MODEL_SETTINGS_DEFAULT, type ModelSettingsState } from '../constants/modelSettingsStyles';

export interface ModelParamsState {
  provider: string;
  model: string;
  contextTokens: string;
  outputTokens: string;
  temperature: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  stopSequences: string[];
  resendFiles: boolean;
  imageDetails: number;
  useResponsesApi: boolean;
  webSearch: boolean;
  disableStreaming: boolean;
  fileTokenLimit: string;
}

const defaultParams: ModelParamsState = {
  provider: 'local',
  model: '',
  contextTokens: 'Системная',
  outputTokens: 'Системная',
  temperature: 1,
  topP: 1,
  frequencyPenalty: 0,
  presencePenalty: 0,
  stopSequences: [],
  resendFiles: false,
  imageDetails: 0.5,
  useResponsesApi: false,
  webSearch: false,
  disableStreaming: false,
  fileTokenLimit: 'Системная',
};

export interface ProviderModelOption {
  name: string;
  path: string;
  display_name?: string;
  provider_id?: string;
  llm_host_id?: string;
}

interface ModelParametersModalProps {
  open: boolean;
  onClose: () => void;
  currentModel: string;
  availableModels: string[];
  initialParams?: Partial<ModelParamsState>;
  onSave: (model: string, params: Partial<ModelParamsState>) => void;
  /** 'modal' — диалог поверх контента; 'panel' — панель вместо формы агента с кнопкой «Назад» */
  variant?: 'modal' | 'panel';
  /** Тонкая настройка модели (из конструктора агента): при задании показывается блок внутри меню и сохраняется через onSaveModelSettings */
  initialModelSettings?: ModelSettingsState;
  onSaveModelSettings?: (s: ModelSettingsState) => void;
  /** Каталог моделей с провайдерами (id из config, напр. local). Если задан — провайдер выбирается из реальных подключений, модели фильтруются по провайдеру. */
  providerModels?: ProviderModelOption[];
  /** Порядок/список id провайдеров для выпадающего списка. */
  providerIds?: string[];
}

/** Провайдер (первый сегмент пути ``<provider>/<model_id>``). */
function providerOfPath(path: string): string {
  const p = (path || '').replace(/^llm-svc:\/\//i, '');
  if (!p) return '';
  return p.includes('/') ? p.split('/')[0] : '';
}

const inputSx = {
  '& .MuiOutlinedInput-root': {
    bgcolor: 'rgba(0,0,0,0.25)',
    color: 'white',
    fontSize: '0.85rem',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
    '&.Mui-focused fieldset': { borderColor: 'rgba(33,150,243,0.7)' },
  },
  '& .MuiInputBase-input': { color: 'white' },
  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
};

const outlinedSelectSx = {
  ...getFormFieldInputSx(true),
  '& .MuiOutlinedInput-root': {
    ...((getFormFieldInputSx(true) as any)['& .MuiOutlinedInput-root'] ?? {}),
    cursor: 'pointer',
  },
  '& .MuiOutlinedInput-root.Mui-focused fieldset': {
    borderColor: 'rgba(255,255,255,0.23)',
    borderWidth: '1px',
  },
  '& .MuiOutlinedInput-root:hover fieldset': {
    borderColor: 'rgba(255,255,255,0.4)',
  },
  '& .MuiOutlinedInput-root.Mui-focused:hover fieldset': {
    borderColor: 'rgba(255,255,255,0.4)',
  },
  '& .MuiInputLabel-root.Mui-focused': {
    color: 'rgba(255,255,255,0.7)',
  },
  '& .MuiFormLabel-asterisk': { color: '#f44336' },
} as const;

/** Fallback, если /api/llm-providers ещё не ответил. Id должен совпадать с config (microservices.llm.hosts[].id). */
const PROVIDER_OPTIONS = [
  { value: 'local', label: 'local' },
];

function formatModelLabel(path: string) {
  return path.replace('llm-svc://', '').split('/').pop() || path || '—';
}

export default function ModelParametersModal({
  open,
  onClose,
  currentModel,
  availableModels,
  initialParams,
  onSave,
  variant = 'modal',
  initialModelSettings,
  onSaveModelSettings,
  providerModels,
  providerIds,
}: ModelParametersModalProps) {
  const [params, setParams] = useState<ModelParamsState>({ ...defaultParams, model: currentModel });
  const [stopInput, setStopInput] = useState('');
  const [providerAnchor, setProviderAnchor] = useState<HTMLElement | null>(null);
  const [modelAnchor, setModelAnchor] = useState<HTMLElement | null>(null);
  const hasModelSettings = initialModelSettings != null && onSaveModelSettings != null;
  const [modelSettings, setModelSettings] = useState<ModelSettingsState>(() => ({ ...MODEL_SETTINGS_DEFAULT, ...initialModelSettings }));

  // ─── Режим провайдеров (CORSUR / Phoenix …) ──────────────────────────────────
  const providerMode = Array.isArray(providerModels) && providerModels.length > 0;
  const providerOptions = useMemo(() => {
    if (!providerMode) return PROVIDER_OPTIONS;
    const ids =
      providerIds && providerIds.length
        ? providerIds
        : Array.from(
            new Set(
              (providerModels || [])
                .map(m => m.provider_id || providerOfPath(m.path))
                .filter(Boolean),
            ),
          );
    return ids.map(id => ({ value: id as string, label: id as string }));
  }, [providerMode, providerModels, providerIds]);

  const selectedProvider = params.provider || '';

  const providerFilteredModels = useMemo(() => {
    if (!providerMode) return availableModels;
    return (providerModels || [])
      .filter(m => (m.provider_id || providerOfPath(m.path)) === selectedProvider)
      .map(m => m.path);
  }, [providerMode, providerModels, availableModels, selectedProvider]);

  const modelLabelOf = useCallback(
    (path: string) => {
      if (providerMode) {
        const found = (providerModels || []).find(m => m.path === path);
        if (found) return (found.display_name || found.name || formatModelLabel(path)).replace(/\.gguf$/i, '');
      }
      return formatModelLabel(path);
    },
    [providerMode, providerModels],
  );

  useEffect(() => {
    if (open) {
      const nextModel = currentModel || (initialParams?.model as string) || '';
      setParams(prev => ({
        ...defaultParams,
        ...prev,
        ...initialParams,
        model: nextModel || prev.model,
        provider: providerMode
          ? providerOfPath(nextModel || prev.model) || (initialParams?.provider as string) || prev.provider
          : (initialParams?.provider as string) || prev.provider,
      }));
      if (hasModelSettings && initialModelSettings) {
        setModelSettings({ ...MODEL_SETTINGS_DEFAULT, ...initialModelSettings });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, currentModel, initialParams, hasModelSettings, initialModelSettings, providerMode]);

  const handleReset = () => {
    setParams({ ...defaultParams, model: params.model });
    if (hasModelSettings) setModelSettings({ ...MODEL_SETTINGS_DEFAULT });
  };

  const handleSave = () => {
    onSave(params.model, params);
    if (hasModelSettings) onSaveModelSettings(modelSettings);
    onClose();
  };

  const handleStopKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && stopInput.trim()) {
      e.preventDefault();
      setParams(prev => ({ ...prev, stopSequences: [...prev.stopSequences, stopInput.trim()] }));
      setStopInput('');
    }
  };

  const labelSx = { color: 'rgba(255,255,255,0.85)', fontSize: '0.8rem', mb: 0.5, display: 'block' };

  const content = (
    <>
      {/* Header: back + title */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.08)', flexShrink: 0 }}>
        <IconButton size="small" onClick={onClose} sx={{ color: 'rgba(255,255,255,0.7)', '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' } }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h6" sx={{ color: 'white', fontSize: '1rem', fontWeight: 600 }}>
          Параметры модели
        </Typography>
      </Box>

      <Box sx={{ px: 2, py: 2, display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minHeight: 0, overflow: 'auto' }}>
          {/* Провайдер — outlined с плавающим лейблом; без синего фокуса */}
          <Box>
            <FormControl variant="outlined" fullWidth size="small" required sx={outlinedSelectSx}>
              <InputLabel htmlFor="model-params-provider">Провайдер</InputLabel>
              <OutlinedInput
                id="model-params-provider"
                label="Провайдер"
                value={providerOptions.find(o => o.value === params.provider)?.label ?? params.provider}
                readOnly
                placeholder="Выберите провайдера"
                onClick={e => setProviderAnchor(e.currentTarget)}
                endAdornment={
                  <InputAdornment position="end">
                    <ExpandMoreIcon
                      sx={{ ...DROPDOWN_CHEVRON_SX, transform: Boolean(providerAnchor) ? 'rotate(180deg)' : 'none' }}
                    />
                  </InputAdornment>
                }
              />
            </FormControl>
            <Popover
              open={Boolean(providerAnchor)}
              anchorEl={providerAnchor}
              onClose={() => setProviderAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
              slotProps={{ paper: { sx: getDropdownPopoverPaperSx(providerAnchor) } }}
            >
              <Box sx={{ py: 0.5 }}>
                {providerOptions.map(o => (
                  <Box
                    key={o.value}
                    onClick={() => {
                      setParams(p => {
                        if (!providerMode) return { ...p, provider: o.value };
                        // При смене провайдера сбрасываем модель, если она не из этого провайдера
                        const keepModel = providerOfPath(p.model) === o.value ? p.model : '';
                        return { ...p, provider: o.value, model: keepModel };
                      });
                      setProviderAnchor(null);
                    }}
                    sx={{
                      ...DROPDOWN_ITEM_SX,
                      color: params.provider === o.value ? 'white' : 'rgba(255,255,255,0.9)',
                      fontWeight: params.provider === o.value ? 600 : 400,
                      bgcolor: params.provider === o.value ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                    }}
                  >
                    {o.label}
                  </Box>
                ))}
                {providerOptions.length === 0 && (
                  <Box sx={{ px: 1.5, py: 1, fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)' }}>
                    Нет доступных провайдеров
                  </Box>
                )}
              </Box>
            </Popover>
          </Box>

          {/* Модель — outlined с плавающим лейблом; без синего фокуса */}
          <Box>
            <FormControl variant="outlined" fullWidth size="small" required sx={outlinedSelectSx}>
              <InputLabel htmlFor="model-params-model">Модель</InputLabel>
              <OutlinedInput
                id="model-params-model"
                label="Модель"
                value={params.model ? modelLabelOf(params.model) : ''}
                placeholder={providerMode && !selectedProvider ? 'Сначала выберите провайдера' : 'Выберите модель'}
                readOnly
                onClick={e => {
                  if (providerMode && !selectedProvider) {
                    setProviderAnchor(e.currentTarget);
                    return;
                  }
                  setModelAnchor(e.currentTarget);
                }}
                endAdornment={
                  <InputAdornment position="end">
                    <ExpandMoreIcon
                      sx={{ ...DROPDOWN_CHEVRON_SX, transform: Boolean(modelAnchor) ? 'rotate(180deg)' : 'none', flexShrink: 0 }}
                    />
                  </InputAdornment>
                }
                sx={{ '& .MuiOutlinedInput-input': { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }}
              />
            </FormControl>
            <Popover
              open={Boolean(modelAnchor)}
              anchorEl={modelAnchor}
              onClose={() => setModelAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
              slotProps={{ paper: { sx: getDropdownPopoverPaperSx(modelAnchor) } }}
            >
              <Box
                sx={{
                  py: 0.5,
                  maxHeight: 280,
                  overflowY: 'auto',
                  '&::-webkit-scrollbar': { width: 3 },
                  '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.12)', borderRadius: 2 },
                }}
              >
                {providerFilteredModels.map(m => (
                  <Box
                    key={m}
                    onClick={() => {
                      setParams(p => ({ ...p, model: m }));
                      setModelAnchor(null);
                    }}
                    sx={{
                      ...DROPDOWN_ITEM_SX,
                      color: params.model === m ? 'white' : 'rgba(255,255,255,0.9)',
                      fontWeight: params.model === m ? 600 : 400,
                      bgcolor: params.model === m ? DROPDOWN_ITEM_HOVER_BG : 'transparent',
                      whiteSpace: 'normal',
                      wordBreak: 'break-word',
                    }}
                  >
                    {modelLabelOf(m)}
                  </Box>
                ))}
                {providerFilteredModels.length === 0 && (
                  <Box sx={{ px: 1.5, py: 1, fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)' }}>
                    {providerMode && !selectedProvider ? 'Сначала выберите провайдера' : 'Нет моделей'}
                  </Box>
                )}
              </Box>
            </Popover>
          </Box>

          {/* Тонкая настройка модели (при открытии из конструктора агента) */}
          {hasModelSettings && (
            <Box sx={{ mt: 1 }}>
              <ModelSettingsFields
                value={modelSettings}
                onChange={setModelSettings}
                accordion
                darkPanel
                compact
              />
            </Box>
          )}

          {/* Контекст / токены / слайдеры — скрыты при тонкой настройке из конструктора */}
          {!hasModelSettings && (
            <>
          <Box>
            <Typography sx={labelSx}>Максимальное количество контекстных токенов</Typography>
            <TextField size="small" fullWidth value={params.contextTokens} onChange={e => setParams(p => ({ ...p, contextTokens: e.target.value }))} sx={inputSx} />
          </Box>
          <Box>
            <Typography sx={labelSx}>Максимальное количество выводимых токенов</Typography>
            <TextField size="small" fullWidth value={params.outputTokens} onChange={e => setParams(p => ({ ...p, outputTokens: e.target.value }))} sx={inputSx} />
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, alignItems: 'stretch' }}>
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography sx={{ ...labelSx, minHeight: 28, display: 'flex', alignItems: 'center' }}>Температура — {params.temperature.toFixed(2)}</Typography>
              <Slider size="small" value={params.temperature} min={0} max={2} step={0.01} onChange={(_, v) => setParams(p => ({ ...p, temperature: v as number }))}
                sx={{ color: '#2196f3', '& .MuiSlider-thumb': { color: '#2196f3' }, '& .MuiSlider-track': { color: '#2196f3' } }} />
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography sx={{ ...labelSx, minHeight: 28, display: 'flex', alignItems: 'center' }}>Top P — {params.topP.toFixed(2)}</Typography>
              <Slider size="small" value={params.topP} min={0} max={1} step={0.01} onChange={(_, v) => setParams(p => ({ ...p, topP: v as number }))}
                sx={{ color: '#2196f3' }} />
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography sx={{ ...labelSx, minHeight: 28, display: 'flex', alignItems: 'center' }}>Штраф за частоту — {params.frequencyPenalty.toFixed(2)}</Typography>
              <Slider size="small" value={params.frequencyPenalty} min={0} max={2} step={0.01} onChange={(_, v) => setParams(p => ({ ...p, frequencyPenalty: v as number }))}
                sx={{ color: '#2196f3' }} />
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography sx={{ ...labelSx, minHeight: 28, display: 'flex', alignItems: 'center' }}>Штраф за присутствие — {params.presencePenalty.toFixed(2)}</Typography>
              <Slider size="small" value={params.presencePenalty} min={0} max={2} step={0.01} onChange={(_, v) => setParams(p => ({ ...p, presencePenalty: v as number }))}
                sx={{ color: '#2196f3' }} />
            </Box>
          </Box>
            </>
          )}

          {/* Stop sequences */}
          <Box>
            <Typography sx={labelSx}>Стоп-последовательности</Typography>
            <TextField size="small" fullWidth placeholder="Разделяйте значения нажатием Enter" value={stopInput} onChange={e => setStopInput(e.target.value)} onKeyDown={handleStopKeyDown} sx={inputSx} />
          </Box>

          <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)' }} />

          {/* Toggles */}
          <FormControlLabel
            control={<Switch checked={params.resendFiles} onChange={e => setParams(p => ({ ...p, resendFiles: e.target.checked }))} sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' }, '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.2)' } }} />}
            label={<Typography sx={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.85rem' }}>Повторить отправку файлов</Typography>}
          />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography sx={{ ...labelSx, flex: 1 }}>Детали изображения</Typography>
            <Slider size="small" value={params.imageDetails} min={0} max={1} step={0.1} sx={{ width: 120, color: '#2196f3' }} onChange={(_, v) => setParams(p => ({ ...p, imageDetails: v as number }))} />
            <Button size="small" sx={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.75rem', textTransform: 'none' }}>Авто</Button>
          </Box>
          <FormControlLabel
            control={<Switch checked={params.useResponsesApi} onChange={e => setParams(p => ({ ...p, useResponsesApi: e.target.checked }))} sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' } }} />}
            label={<Typography sx={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.85rem' }}>Использовать Responses API</Typography>}
          />
          <FormControlLabel
            control={<Switch checked={params.webSearch} onChange={e => setParams(p => ({ ...p, webSearch: e.target.checked }))} sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' } }} />}
            label={<Typography sx={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.85rem' }}>Веб-поиск</Typography>}
          />
          <FormControlLabel
            control={<Switch checked={params.disableStreaming} onChange={e => setParams(p => ({ ...p, disableStreaming: e.target.checked }))} sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' } }} />}
            label={<Typography sx={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.85rem' }}>Отключить потоковую передачу</Typography>}
          />
          <Box>
            <Typography sx={labelSx}>Ограничение на количество токенов файла</Typography>
            <TextField size="small" fullWidth value={params.fileTokenLimit} onChange={e => setParams(p => ({ ...p, fileTokenLimit: e.target.value }))} sx={inputSx} />
          </Box>
        </Box>

      {/* Footer: Reset, Copy, Save */}
      <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.08)', px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', flexShrink: 0 }}>
        <Button size="small" startIcon={<RefreshIcon />} onClick={handleReset}
          sx={{ color: 'rgba(255,255,255,0.7)', border: '1px solid rgba(255,255,255,0.2)', textTransform: 'none', fontSize: '0.8rem', '&:hover': { borderColor: 'rgba(255,255,255,0.4)', bgcolor: 'rgba(255,255,255,0.06)' } }}>
          Сбросить параметры модели
        </Button>
        <IconButton size="small" sx={{ color: 'rgba(255,255,255,0.5)', '&:hover': { color: 'white', bgcolor: 'rgba(255,255,255,0.08)' } }}>
          <CopyIcon fontSize="small" />
        </IconButton>
        <Box sx={{ flex: 1 }} />
        <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave}
          sx={{ bgcolor: '#26a69a', color: 'white', textTransform: 'none', fontWeight: 600, '&:hover': { bgcolor: '#2dbdb3' } }}>
          Сохранить
        </Button>
      </Box>
    </>
  );

  const panelBg = getSidebarPanelBackground();
  if (variant === 'panel') {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: panelBg, color: 'white' }}>
        {content}
      </Box>
    );
  }
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          background: panelBg,
          color: 'white',
          borderRadius: 2,
          border: '1px solid rgba(255,255,255,0.08)',
          maxHeight: '90vh',
        },
      }}
    >
      <DialogContent sx={{ p: 0, overflow: 'auto' }}>
        {content}
      </DialogContent>
    </Dialog>
  );
}
