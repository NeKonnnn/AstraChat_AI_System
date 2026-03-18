import React from 'react';
import {
  Box,
  Typography,
  TextField,
  Switch,
  IconButton,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { HelpOutline as HelpOutlineIcon, ExpandMore as ExpandMoreIcon, Settings as SettingsIcon } from '@mui/icons-material';
import {
  MODEL_SETTINGS_ACCORDION_SX,
  MODEL_SETTINGS_GRID_SX,
  MODEL_SETTINGS_GRID_COMPACT_SX,
  MODEL_SETTINGS_LABEL_WRAPPER_SX,
  MODEL_SETTINGS_HELP_ICON_BUTTON_SX,
  MODEL_SETTINGS_INPUT_SX,
  MODEL_SETTINGS_SWITCH_ROW_COMPACT_SX,
  modelSettingsSwitchSx,
  MODEL_SETTINGS_DEFAULT,
  MODEL_SETTINGS_MAX_DEFAULT,
  type ModelSettingsState,
  type ModelSettingsMaxValues,
} from '../constants/modelSettingsStyles';

const TOOLTIPS: Record<string, string> = {
  context_size: 'Максимальное количество токенов, которые модель может использовать для понимания контекста. Больше значение = больше контекста, но больше потребление памяти.',
  output_tokens: 'Максимальное количество токенов, которые модель может сгенерировать в ответе. Увеличение позволяет получать более длинные ответы.',
  temperature: 'Контролирует случайность генерации. Низкие значения (0.1-0.5) — более точные ответы, высокие (0.8-1.5) — более креативные.',
  top_p: 'Работает совместно с top-k. Высокое значение (0.95) — разнообразнее текст, низкое (0.5) — более сфокусированный.',
  repeat_penalty: 'Штраф за повторение уже использованных токенов. Значения выше 1.0 уменьшают повторения.',
  top_k: 'Ограничивает выборку k наиболее вероятными токенами. Больше (100+) — разнообразнее, меньше (10-20) — консервативнее.',
  min_p: 'Минимальная вероятность токена относительно наиболее вероятного. Альтернатива top_p/top_k.',
  frequency_penalty: 'Штраф за частоту появления токенов. Высокое значение сильнее наказывает за повторения.',
  presence_penalty: 'Штраф за сам факт появления токена. При 0 отключено.',
  use_gpu: 'Использование GPU для ускорения. Требует CUDA.',
  streaming: 'Показывать ответ по мере генерации (токен за токеном).',
};

interface ModelSettingsFieldsProps {
  value: ModelSettingsState;
  onChange: (next: ModelSettingsState) => void;
  maxValues?: Partial<ModelSettingsMaxValues>;
  /** Показывать аккордеон «Тонкая настройка» (иначе только поля) */
  accordion?: boolean;
  /** Класс/стиль для тёмной панели (конструктор агентов) — тогда лейблы белые */
  darkPanel?: boolean;
  /** Компактная сетка: уже колонки, несколько полей в строке (в модалке выбора модели в конструкторе) */
  compact?: boolean;
}

function numField(
  key: keyof ModelSettingsState,
  label: string,
  value: number,
  onChange: (v: number) => void,
  min: number,
  max: number,
  step: number,
  defaultVal: number,
  tooltip: string,
  darkPanel: boolean
) {
  return (
    <Box key={key}>
      <TextField
        label={
          <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX} component="span">
            {label}
            <Tooltip title={tooltip} arrow>
              <IconButton size="small" sx={MODEL_SETTINGS_HELP_ICON_BUTTON_SX} onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                <HelpOutlineIcon fontSize="small" color="action" />
              </IconButton>
            </Tooltip>
          </Box>
        }
        type="number"
        value={value}
        onChange={(e) => {
          const v = e.target.value;
          if (v === '') {
            onChange(0);
            return;
          }
          const n = key === 'context_size' || key === 'output_tokens' || key === 'top_k' ? parseInt(v, 10) : parseFloat(v);
          if (!Number.isNaN(n)) onChange(n);
        }}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v === '') {
            onChange(defaultVal);
            return;
          }
          const n = key === 'context_size' || key === 'output_tokens' || key === 'top_k' ? parseInt(v, 10) : parseFloat(v);
          if (Number.isNaN(n) || n < min) onChange(defaultVal);
        }}
        inputProps={{ min, max, step }}
        fullWidth
        size="small"
        sx={darkPanel ? { ...MODEL_SETTINGS_INPUT_SX } : undefined}
      />
    </Box>
  );
}

export default function ModelSettingsFields({
  value,
  onChange,
  maxValues: maxValuesProp,
  accordion = true,
  darkPanel = false,
  compact = false,
}: ModelSettingsFieldsProps) {
  const maxValues = { ...MODEL_SETTINGS_MAX_DEFAULT, ...maxValuesProp };
  const set = (patch: Partial<ModelSettingsState>) => onChange({ ...value, ...patch });

  const gridContent = (
    <Box sx={compact ? MODEL_SETTINGS_GRID_COMPACT_SX : MODEL_SETTINGS_GRID_SX}>
      {numField(
        'context_size',
        'Размер контекста',
        value.context_size,
        (v) => set({ context_size: v }),
        512,
        maxValues.context_size,
        512,
        MODEL_SETTINGS_DEFAULT.context_size,
        TOOLTIPS.context_size,
        darkPanel
      )}
      {numField(
        'output_tokens',
        'max_tokens',
        value.output_tokens,
        (v) => set({ output_tokens: v }),
        64,
        maxValues.output_tokens,
        64,
        MODEL_SETTINGS_DEFAULT.output_tokens,
        TOOLTIPS.output_tokens,
        darkPanel
      )}
      {numField(
        'temperature',
        'Температура',
        value.temperature,
        (v) => set({ temperature: v }),
        0.1,
        maxValues.temperature,
        0.1,
        MODEL_SETTINGS_DEFAULT.temperature,
        TOOLTIPS.temperature,
        darkPanel
      )}
      {numField(
        'top_p',
        'Top-p',
        value.top_p,
        (v) => set({ top_p: v }),
        0.1,
        maxValues.top_p,
        0.05,
        MODEL_SETTINGS_DEFAULT.top_p,
        TOOLTIPS.top_p,
        darkPanel
      )}
      {numField(
        'repeat_penalty',
        'Repeat penalty',
        value.repeat_penalty,
        (v) => set({ repeat_penalty: v }),
        1.0,
        maxValues.repeat_penalty,
        0.05,
        MODEL_SETTINGS_DEFAULT.repeat_penalty,
        TOOLTIPS.repeat_penalty,
        darkPanel
      )}
      {numField(
        'top_k',
        'Top-k',
        value.top_k,
        (v) => set({ top_k: v }),
        1,
        maxValues.top_k,
        1,
        MODEL_SETTINGS_DEFAULT.top_k,
        TOOLTIPS.top_k,
        darkPanel
      )}
      {numField(
        'min_p',
        'Min-p',
        value.min_p,
        (v) => set({ min_p: v }),
        0,
        maxValues.min_p,
        0.01,
        MODEL_SETTINGS_DEFAULT.min_p,
        TOOLTIPS.min_p,
        darkPanel
      )}
      {numField(
        'frequency_penalty',
        'Frequency penalty',
        value.frequency_penalty,
        (v) => set({ frequency_penalty: v }),
        0,
        maxValues.frequency_penalty,
        0.1,
        MODEL_SETTINGS_DEFAULT.frequency_penalty,
        TOOLTIPS.frequency_penalty,
        darkPanel
      )}
      {numField(
        'presence_penalty',
        'Presence penalty',
        value.presence_penalty,
        (v) => set({ presence_penalty: v }),
        0,
        maxValues.presence_penalty,
        0.1,
        MODEL_SETTINGS_DEFAULT.presence_penalty,
        TOOLTIPS.presence_penalty,
        darkPanel
      )}
    </Box>
  );

  const switchRow = (label: string, tooltip: string, checked: boolean, onToggle: (v: boolean) => void) => (
    <Box key={label} sx={MODEL_SETTINGS_SWITCH_ROW_COMPACT_SX}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0, pr: 1 }}>
        <Typography
          variant="caption"
          sx={{
            color: darkPanel ? 'rgba(255,255,255,0.7)' : 'text.secondary',
            fontSize: '0.78rem',
            lineHeight: 1.3,
          }}
        >
          {label}
        </Typography>
        <Tooltip title={tooltip} arrow>
          <HelpOutlineIcon
            sx={{
              fontSize: 12,
              color: darkPanel ? 'rgba(255,255,255,0.25)' : 'action.active',
              cursor: 'help',
              flexShrink: 0,
            }}
          />
        </Tooltip>
      </Box>
      <Switch
        size="small"
        checked={checked}
        onChange={(e) => onToggle(e.target.checked)}
        sx={modelSettingsSwitchSx(darkPanel)}
      />
    </Box>
  );

  const switchList = (
    <Box sx={{ mt: 1.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {switchRow('Использовать GPU', TOOLTIPS.use_gpu, value.use_gpu, (v) => set({ use_gpu: v }))}
      {switchRow('Потоковая генерация', TOOLTIPS.streaming, value.streaming, (v) => set({ streaming: v }))}
    </Box>
  );

  if (accordion) {
    return (
      <>
        <Accordion
          sx={{
            ...MODEL_SETTINGS_ACCORDION_SX,
            ...(darkPanel
              ? {
                  bgcolor: 'rgba(0,0,0,0.2)',
                  color: 'white',
                  '& .MuiAccordionSummary-root': { color: 'rgba(255,255,255,0.9)' },
                  '& .MuiAccordionDetails-root': { color: 'rgba(255,255,255,0.9)' },
                }
              : {}),
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon sx={darkPanel ? { color: 'rgba(255,255,255,0.7)' } : undefined} />}>
            <Box sx={MODEL_SETTINGS_LABEL_WRAPPER_SX}>
              <SettingsIcon />
              <Typography variant="subtitle1">Тонкая настройка</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {gridContent}
            {switchList}
          </AccordionDetails>
        </Accordion>
      </>
    );
  }

  return (
    <Box>
      {gridContent}
      {switchList}
    </Box>
  );
}

export type { ModelSettingsState, ModelSettingsMaxValues };
