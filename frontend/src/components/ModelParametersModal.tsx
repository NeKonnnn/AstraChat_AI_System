import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  TextField,
  Button,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  Switch,
  FormControlLabel,
  Divider,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  ContentCopy as CopyIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { getSidebarPanelBackground } from '../constants/sidebarPanelColor';

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
  provider: 'SC',
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

interface ModelParametersModalProps {
  open: boolean;
  onClose: () => void;
  currentModel: string;
  availableModels: string[];
  initialParams?: Partial<ModelParamsState>;
  onSave: (model: string, params: Partial<ModelParamsState>) => void;
  /** 'modal' — диалог поверх контента; 'panel' — панель вместо формы агента с кнопкой «Назад» */
  variant?: 'modal' | 'panel';
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

const selectSx = {
  '& .MuiOutlinedInput-root': {
    bgcolor: 'rgba(0,0,0,0.25)',
    color: 'white',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.3)' },
  },
  '& .MuiSelect-icon': { color: 'rgba(255,255,255,0.5)' },
};

export default function ModelParametersModal({
  open,
  onClose,
  currentModel,
  availableModels,
  initialParams,
  onSave,
  variant = 'modal',
}: ModelParametersModalProps) {
  const [params, setParams] = useState<ModelParamsState>({ ...defaultParams, model: currentModel });
  const [stopInput, setStopInput] = useState('');

  useEffect(() => {
    if (open) {
      setParams(prev => ({
        ...defaultParams,
        ...prev,
        ...initialParams,
        model: currentModel || (initialParams?.model as string) || prev.model,
      }));
    }
  }, [open, currentModel, initialParams]);

  const handleReset = () => {
    setParams({ ...defaultParams, model: params.model });
  };

  const handleSave = () => {
    onSave(params.model, params);
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
          {/* Provider & Model */}
          <FormControl size="small" fullWidth>
            <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Провайдер *</InputLabel>
            <Select
              value={params.provider}
              onChange={e => setParams(p => ({ ...p, provider: e.target.value }))}
              label="Провайдер *"
              sx={selectSx}
              MenuProps={{ PaperProps: { sx: { bgcolor: '#1e2530', color: 'white', '& .MuiMenuItem-root': { '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' } } } } }}
            >
              <MenuItem value="SC">SC</MenuItem>
              <MenuItem value="OpenAI">OpenAI</MenuItem>
              <MenuItem value="Local">Local</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" fullWidth>
            <InputLabel sx={{ color: 'rgba(255,255,255,0.7)' }}>Модель *</InputLabel>
            <Select
              value={params.model}
              onChange={e => setParams(p => ({ ...p, model: e.target.value }))}
              label="Модель *"
              sx={selectSx}
              MenuProps={{
                PaperProps: {
                  sx: {
                    bgcolor: '#1e2530',
                    color: 'white',
                    maxHeight: 280,
                    '& .MuiMenuItem-root': { fontSize: '0.8rem', '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' }, whiteSpace: 'normal' },
                  },
                },
              }}
            >
              {availableModels.map(m => (
                <MenuItem key={m} value={m}>{m.replace('llm-svc://', '').split('/').pop() || m}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Context / Output tokens */}
          <Box>
            <Typography sx={labelSx}>Максимальное количество контекстных токенов</Typography>
            <TextField size="small" fullWidth value={params.contextTokens} onChange={e => setParams(p => ({ ...p, contextTokens: e.target.value }))} sx={inputSx} />
          </Box>
          <Box>
            <Typography sx={labelSx}>Максимальное количество выводимых токенов</Typography>
            <TextField size="small" fullWidth value={params.outputTokens} onChange={e => setParams(p => ({ ...p, outputTokens: e.target.value }))} sx={inputSx} />
          </Box>

          {/* Sliders — по 2 в ряд, подписи одной высотой для выравнивания треков */}
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
