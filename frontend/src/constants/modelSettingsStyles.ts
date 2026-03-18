/**
 * Общие стили для панелей «Настройка выбранной модели» и «Настройка модели агента».
 * Используется в Настройках → Модели и в Конструкторе агентов.
 */

import type { SxProps, Theme } from '@mui/material';
import { FORM_FIELD_INPUT_SX } from './menuStyles';

/** Радиус, отступы, высота, шрифт полей — править в menuStyles: `AGENT_CONSTRUCTOR_FIELD_*`. */
export {
  AGENT_CONSTRUCTOR_FIELD_RADIUS_PX,
  AGENT_CONSTRUCTOR_FIELD_PADDING_X_PX,
  AGENT_CONSTRUCTOR_FIELD_PADDING_Y_PX,
  AGENT_CONSTRUCTOR_FIELD_MIN_HEIGHT_PX,
  AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
  AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT,
} from './menuStyles';

/** Заголовок секции (иконка + текст) */
export const MODEL_SETTINGS_SECTION_TITLE_SX: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  gap: 1,
};

/** Карточка/блок секции настроек модели */
export const MODEL_SETTINGS_CARD_SX: SxProps<Theme> = {
  mb: 3,
};

/** Контент карточки */
export const MODEL_SETTINGS_CARD_CONTENT_SX: SxProps<Theme> = {};

/** Аккордеон «Тонкая настройка» */
export const MODEL_SETTINGS_ACCORDION_SX: SxProps<Theme> = {
  mt: 2,
  '&::before': { display: 'none' },
  '&.Mui-expanded': { margin: 0 },
  '& .MuiAccordionSummary-root': { minHeight: 48 },
  '& .MuiAccordionDetails-root': { pt: 0, pb: 2 },
};

/** Сетка полей (размер контекста, температура, top_p и т.д.) */
export const MODEL_SETTINGS_GRID_SX: SxProps<Theme> = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
  gap: 2,
};

/** Компактная сетка: ровно 2 поля в строке (модалка конструктора агента) */
export const MODEL_SETTINGS_GRID_COMPACT_SX: SxProps<Theme> = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
  gap: 1.5,
};

/** Обёртка для лейбла с тултипом (иконка HelpOutline) */
export const MODEL_SETTINGS_LABEL_WRAPPER_SX: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  gap: 0.5,
};

/** Стиль иконки помощи в лейбле */
export const MODEL_SETTINGS_HELP_ICON_BUTTON_SX: SxProps<Theme> = {
  p: 0,
  opacity: 0.7,
  '&:hover': {
    opacity: 1,
    '& .MuiSvgIcon-root': {
      color: 'primary.main',
    },
  },
};

/**
 * Числовые поля «Тонкая настройка» — те же размеры/шрифт, что поле «Имя» в конструкторе
 * (см. AGENT_CONSTRUCTOR_FIELD_* в menuStyles.ts).
 */
export const MODEL_SETTINGS_INPUT_SX: SxProps<Theme> = {
  ...FORM_FIELD_INPUT_SX,
  '& .MuiInputLabel-root': { color: 'rgba(255,255,255,0.7)' },
};

/** Слайдер (температура, top_p и т.д.) */
export const MODEL_SETTINGS_SLIDER_SX: SxProps<Theme> = {
  color: '#2196f3',
  '& .MuiSlider-thumb': { color: '#2196f3' },
  '& .MuiSlider-track': { color: '#2196f3' },
};

/** Строка переключателя (ListItem с Switch): use_gpu, streaming — старый вариант */
export const MODEL_SETTINGS_SWITCH_ROW_SX: SxProps<Theme> = {
  px: 0,
  py: 2,
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

/** Компактная строка как в «Артефакты» конструктора агента */
export const MODEL_SETTINGS_SWITCH_ROW_COMPACT_SX: SxProps<Theme> = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  py: 0.25,
  minHeight: 0,
};

export function modelSettingsSwitchSx(dark: boolean): SxProps<Theme> {
  return {
    '& .MuiSwitch-switchBase.Mui-checked': { color: '#2196f3' },
    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: 'rgba(33,150,243,0.5)' },
    '& .MuiSwitch-track': { bgcolor: dark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.25)' },
    transform: 'scale(0.82)',
    transformOrigin: 'center right',
  };
}

/** Разделитель между переключателями */
export const MODEL_SETTINGS_DIVIDER_SX: SxProps<Theme> = {};

/** Кнопка «Восстановить настройки» */
export const MODEL_SETTINGS_RESET_BUTTON_SX: SxProps<Theme> = {
  mt: 3,
};

/** Тип настроек модели (как в API /api/models/settings) */
export interface ModelSettingsState {
  context_size: number;
  output_tokens: number;
  temperature: number;
  top_p: number;
  repeat_penalty: number;
  top_k: number;
  min_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  use_gpu: boolean;
  streaming: boolean;
  streaming_speed: number;
}

/** Максимальные/рекомендуемые значения для полей */
export interface ModelSettingsMaxValues {
  context_size: number;
  output_tokens: number;
  temperature: number;
  top_p: number;
  repeat_penalty: number;
  top_k: number;
  min_p: number;
  frequency_penalty: number;
  presence_penalty: number;
}

export const MODEL_SETTINGS_DEFAULT: ModelSettingsState = {
  context_size: 2048,
  output_tokens: 512,
  temperature: 0.7,
  top_p: 0.95,
  repeat_penalty: 1.05,
  top_k: 40,
  min_p: 0.05,
  frequency_penalty: 0.0,
  presence_penalty: 0.0,
  use_gpu: false,
  streaming: true,
  streaming_speed: 50,
};

export const MODEL_SETTINGS_MAX_DEFAULT: ModelSettingsMaxValues = {
  context_size: 32768,
  output_tokens: 8192,
  temperature: 2.0,
  top_p: 1.0,
  repeat_penalty: 2.0,
  top_k: 200,
  min_p: 1.0,
  frequency_penalty: 2.0,
  presence_penalty: 2.0,
};
