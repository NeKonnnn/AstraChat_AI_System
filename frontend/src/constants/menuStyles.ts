import type { SxProps, Theme } from '@mui/material';

/**
 * Общие стили для выпадающих меню и подменю в приложении.
 * Единое место для цветов и скругления — используется в Sidebar,
 * MoveToFolderAndProjectMenus, App (тема) и других компонентах с меню.
 *
 * Числовые константы (MENU_MIN_WIDTH_PX, MENU_ICON_*, SIDEBAR_*) заданы в пикселях.
 * В компонентах их нужно подставлять с единицей 'px', например: minWidth: `${MENU_MIN_WIDTH_PX}px`
 * — иначе MUI может интерпретировать число как единицы темы (spacing).
 */

/** Скругление углов у контейнеров меню и подменю в пикселях. Один раз задаём — везде одинаково. */
export const MENU_BORDER_RADIUS_PX = 18;

/** Минимальная ширина выпадающего меню и подменю, px. */
export const MENU_MIN_WIDTH_PX = 40;

/** Скругление подсветки пункта при наведении (подушечка, не во всю ширину). */
export const MENU_ITEM_HOVER_RADIUS_PX = 12;
/** Горизонтальный отступ подсветки от краёв меню (чтобы не была полной полосой). */
export const MENU_ITEM_HOVER_MARGIN_PX = 4;

/** Минимальная ширина области иконки в пунктах меню, px. */
export const MENU_ICON_MIN_WIDTH = 22;
/** Отступ справа от иконки до текста в пунктах меню, px. */
export const MENU_ICON_TO_TEXT_GAP_PX = 4;
/** Размер иконок в меню/подменю (чуть крупнее текста ~14px). */
export const MENU_ICON_FONT_SIZE_PX = 20;
/** Размер шрифта текста действий в меню/подменю (как в нейминге чатов). */
export const MENU_ACTION_TEXT_SIZE = '0.82rem';
/** Единая компактная ширина контекстных меню и подменю, px. */
export const MENU_COMPACT_PANEL_WIDTH_PX = 206;

/**
 * Панель «Дополнительные действия» (шестерёнка) у поля ввода чата/проекта —
 * шире компактного меню, чтобы «Подключить/Отключить Базу Знаний» умещались в одну строку.
 */
export const CHAT_GEAR_MENU_PANEL_WIDTH_PX = 272;

/** Зазор между иконкой и текстом в списке сайдбара (проекты, чаты), px. */
export const SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX = 4;
/** Размер аватарки-иконки проекта в сайдбаре, px. Минимальная ширина колонки иконок в списке = SIDEBAR_PROJECT_AVATAR_SIZE + 4. */
export const SIDEBAR_PROJECT_AVATAR_SIZE = 18;

/** Минимальная высота строки действия в левом/правом rail (чат, поиск, кнопки панели). */
export const SIDEBAR_CONTROL_HEIGHT_PX = 36;
/** Скругление строк секций сайдбара (MUI borderRadius theme unit). */
export const SIDEBAR_CONTROL_RADIUS = 2;
/** Горизонтальный padding строки в rail (MUI spacing). */
export const SIDEBAR_CONTROL_PX = 2;

/**
 * Левый внутренний отступ у строк с ведущей иконкой (проекты, «Новый чат», поиск):
 * чуть меньше {@link SIDEBAR_CONTROL_PX}, чтобы глиф визуально совпадал с текстом строк ниже.
 */
export const SIDEBAR_ICON_LEADING_PL = 1.75;

/** Колонка ведущей иконки в списке сайдбара (проекты, «Новый чат», поиск) — как у MUI ListItemIcon + отступ до текста. */
export const SIDEBAR_LIST_LEADING_ICON_SX = {
  color: '#ffffff',
  minWidth: `${SIDEBAR_PROJECT_AVATAR_SIZE + 4}px`,
  marginRight: `${SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX}px`,
  justifyContent: 'flex-start',
} as const;

/** Скрыть полосу прокрутки, оставить прокрутку колесом/тачпадом (сайдбары, конструктор агента). */
export const SIDEBAR_HIDE_SCROLLBAR_SX = {
  scrollbarWidth: 'none',
  msOverflowStyle: 'none',
  '&::-webkit-scrollbar': {
    display: 'none',
  },
} as const;

/** Стиль ListItemButton как у строк чата — для левой и правой боковых панелей. */
export const SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX = {
  borderRadius: 2,
  backgroundColor: 'transparent',
  '&:hover': {
    backgroundColor: 'rgba(255,255,255,0.08)',
  },
  transition: 'all 0.2s ease',
  py: 0,
  minHeight: SIDEBAR_CONTROL_HEIGHT_PX,
  px: SIDEBAR_CONTROL_PX,
} as const;

/** Иконки в строках rail: белые, крупнее глиф (без увеличения высоты кнопки). */
export const SIDEBAR_LIST_ICON_SX = {
  fontSize: '1.375rem',
  color: '#ffffff',
  flexShrink: 0,
} as const;

/**
 * Размер глифа кнопки меню rail (левый/правый): как у «Новый чат» / «Поиск» визуально (меньше полного 1.375rem).
 */
export const SIDEBAR_RAIL_MENU_TOGGLE_GLYPH_SIZE = '1rem';

/**
 * Область нажатия иконки в узком rail — как у `IconButton` кнопки меню (40×40 px).
 */
export const SIDEBAR_RAIL_ICON_HIT_PX = 40;

/**
 * Только иконка в свернутой колонке rail: квадрат {@link SIDEBAR_RAIL_ICON_HIT_PX} со скруглением `borderRadius: 1`,
 * фон hover как у кнопки меню rail (без смены цвета иконки на primary).
 */
export function getSidebarRailCollapsedListItemButtonSx(isDarkMode: boolean): SxProps<Theme> {
  return {
    ...SIDEBAR_CHAT_ROW_LIST_ITEM_BUTTON_SX,
    flex: 'none',
    width: SIDEBAR_RAIL_ICON_HIT_PX,
    height: SIDEBAR_RAIL_ICON_HIT_PX,
    minWidth: SIDEBAR_RAIL_ICON_HIT_PX,
    minHeight: SIDEBAR_RAIL_ICON_HIT_PX,
    maxWidth: SIDEBAR_RAIL_ICON_HIT_PX,
    maxHeight: SIDEBAR_RAIL_ICON_HIT_PX,
    mx: 'auto',
    px: 0,
    py: 0,
    borderRadius: 1,
    justifyContent: 'center',
    alignItems: 'center',
    '&:hover': {
      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
    },
    '& .MuiTouchRipple-root': {
      borderRadius: 1,
    },
  };
}

/** Обводка круга вокруг иконки/эмодзи проекта (толще 1.5px — лучше видно на тёмном фоне). */
export function getProjectAvatarOutlineBorder(sizePx: number): string {
  return sizePx <= 22 ? '2.25px' : '2.75px';
}

export function getProjectAvatarOutlineBox(sizePx: number, iconColor: string): Record<string, string | number> {
  const w = `${sizePx}px`;
  return {
    width: w,
    height: w,
    bgcolor: 'transparent',
    border: `${getProjectAvatarOutlineBorder(sizePx)} solid`,
    borderColor: iconColor,
    color: iconColor,
    boxSizing: 'border-box',
  };
}

/** Визуально утолщает контур MUI-иконки (деньги, папка и т.д.) за счёт лёгкого ореола currentColor. */
export function getProjectIconGlyphSx(fontSizePx: number, iconColor: string) {
  // Слишком сильный «ореол» делает пиктограмму жирной и съедает детали.
  // Делаем мягче: чуть меньше увеличение и меньше теней.
  const bump = fontSizePx <= 14 ? 1.03 : 1.02;
  const s = fontSizePx <= 14 ? 0.24 : 0.3;
  return {
    fontSize: `${Math.max(10, Math.round(fontSizePx * bump))}px`,
    filter: `drop-shadow(0 0 ${s}px ${iconColor}) drop-shadow(${s}px 0 0 ${iconColor}) drop-shadow(-${s}px 0 0 ${iconColor})`,
  };
}

/** Цвет выделения пункта меню при наведении (тёмная тема). Задаётся здесь и в theme.palette.action.hover. */
export const MENU_ITEM_HOVER_DARK = 'rgba(255,255,255,0.1)';
/** Цвет выделения пункта меню при наведении (светлая тема). */
export const MENU_ITEM_HOVER_LIGHT = 'rgba(0,0,0,0.08)';

export interface MenuColors {
  menuBg: string;
  menuBorder: string;
  menuItemColor: string;
  menuItemHover: string;
  menuDividerBorder: string;
  menuDisabledColor: string;
}

/** Цвета оформления меню и подменю в зависимости от темы. */
export function getMenuColors(isDarkMode: boolean): MenuColors {
  return {
    menuBg: isDarkMode ? 'rgba(30, 30, 30, 0.95)' : 'rgba(255, 255, 255, 0.95)',
    menuBorder: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    menuItemColor: isDarkMode ? 'white' : '#333',
    menuItemHover: isDarkMode ? MENU_ITEM_HOVER_DARK : MENU_ITEM_HOVER_LIGHT,
    menuDividerBorder: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
    menuDisabledColor: isDarkMode ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
  };
}

// ─── Поле «Имя» (конструктор агентов): размеры «окошка» и текст — эталон для полей ввода и триггеров выпадающих списков ───

/** Фон полей ввода и кнопок-триггеров (тёмная тема). */
export const FIELD_BG = 'rgba(0,0,0,0.25)';
/** Рамка полей (цвет). */
export const FIELD_BORDER = 'rgba(255,255,255,0.15)';
/** Рамка при наведении. */
export const FIELD_BORDER_HOVER = 'rgba(255,255,255,0.3)';
/** Фон при наведении (триггеры). */
export const FIELD_BG_HOVER = 'rgba(0,0,0,0.35)';
/** Рамка при фокусе. */
export const FIELD_FOCUS = 'rgba(33,150,243,0.7)';
/** Цвет текста. */
export const FIELD_TEXT = 'white';
/** Цвет плейсхолдера / пустого триггера. */
export const FIELD_PLACEHOLDER = 'rgba(255,255,255,0.35)';

/** Скругление рамки поля ввода и кнопки-триггера (px). Как у полей на странице входа. */
export const AGENT_CONSTRUCTOR_FIELD_RADIUS_PX = 10;
/** Горизонтальный внутренний отступ (px). */
export const AGENT_CONSTRUCTOR_FIELD_PADDING_X_PX = 12;
/** Вертикальный внутренний отступ (px). */
export const AGENT_CONSTRUCTOR_FIELD_PADDING_Y_PX = 8;
/** Минимальная высота видимой области поля/триггера (px). */
export const AGENT_CONSTRUCTOR_FIELD_MIN_HEIGHT_PX = 40;
/** Размер шрифта текста внутри поля и в триггере. */
export const AGENT_CONSTRUCTOR_FIELD_FONT_SIZE = '0.82rem';
/** Межстрочный интервал текста в поле/триггере. */
export const AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT = 1.43;

/** @deprecated используйте AGENT_CONSTRUCTOR_FIELD_FONT_SIZE */
export const FIELD_FONT_SIZE = AGENT_CONSTRUCTOR_FIELD_FONT_SIZE;

/** Текст выбранного значения в кнопке-триггере (как в поле «Имя»). */
export const FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX = {
  color: FIELD_TEXT,
  fontWeight: 500,
  fontSize: AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
  lineHeight: AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT,
} as const;

/** Плейсхолдер в триггере (пустое значение). */
export const FORM_FIELD_TRIGGER_PLACEHOLDER_TYPOGRAPHY_SX = {
  ...FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX,
  color: FIELD_PLACEHOLDER,
} as const;

/** Длинный текст в триггере (модель и т.п.) — обрезка с многоточием. */
export const FORM_FIELD_TRIGGER_VALUE_ELLIPSIS_SX = {
  ...FORM_FIELD_TRIGGER_VALUE_TYPOGRAPHY_SX,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  flex: 1,
  minWidth: 0,
  pr: 1,
} as const;

/**
 * MUI TextField outlined: как на странице входа (рамка default/hover/focus 2px + primary),
 * фон поля — всегда {@link FIELD_BG} (как в конструкторе агентов).
 * @param isDarkMode — цвета рамки и подписи как у LoginPage (тёмная/светлая тема).
 */
export function getFormFieldInputSx(isDarkMode: boolean): SxProps<Theme> {
  const borderDefault = isDarkMode ? 'rgba(255,255,255,0.23)' : 'rgba(0,0,0,0.23)';
  const borderHover = isDarkMode ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
  const labelColor = isDarkMode ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)';
  const inputColor = isDarkMode ? '#fff' : 'rgba(0,0,0,0.87)';
  const placeholderColor = isDarkMode ? FIELD_PLACEHOLDER : 'rgba(0,0,0,0.4)';

  return {
    '& .MuiOutlinedInput-root': {
      borderRadius: `${AGENT_CONSTRUCTOR_FIELD_RADIUS_PX}px`,
      minHeight: AGENT_CONSTRUCTOR_FIELD_MIN_HEIGHT_PX,
      bgcolor: FIELD_BG,
      color: inputColor,
      fontSize: AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
      boxSizing: 'border-box' as const,
      '& fieldset': { borderColor: borderDefault },
      '&:hover fieldset': { borderColor: borderHover },
      '&.Mui-focused fieldset': {
        borderColor: 'primary.main',
        borderWidth: '2px',
      },
    },
    '& .MuiOutlinedInput-input': {
      padding: `${AGENT_CONSTRUCTOR_FIELD_PADDING_Y_PX}px ${AGENT_CONSTRUCTOR_FIELD_PADDING_X_PX}px`,
      lineHeight: AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT,
      boxSizing: 'border-box' as const,
    },
    '& .MuiOutlinedInput-root.MuiInputBase-multiline': {
      minHeight: 'unset',
      alignItems: 'stretch',
    },
    '& .MuiOutlinedInput-root.MuiInputBase-multiline .MuiOutlinedInput-input': {
      minHeight: 'unset !important',
    },
    '& .MuiInputBase-input': { color: inputColor },
    '& .MuiInputBase-input::placeholder': { color: placeholderColor, opacity: 1 },
    '& .MuiInputLabel-root': {
      color: labelColor,
      fontSize: AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
      '&.Mui-focused': {
        color: 'primary.main',
      },
    },
  };
}

/**
 * По умолчанию — тёмная панель (конструктор, настройки модели с `darkPanel`).
 * Для конструктора с учётом темы приложения используйте {@link getFormFieldInputSx}(isDarkMode).
 */
export const FORM_FIELD_INPUT_SX: SxProps<Theme> = getFormFieldInputSx(true);

/**
 * Кнопка-триггер выпадающего списка: те же размеры и шрифт, что у поля «Имя».
 */
export const FORM_FIELD_TRIGGER_SX = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  boxSizing: 'border-box' as const,
  minHeight: AGENT_CONSTRUCTOR_FIELD_MIN_HEIGHT_PX,
  px: `${AGENT_CONSTRUCTOR_FIELD_PADDING_X_PX}px`,
  py: `${AGENT_CONSTRUCTOR_FIELD_PADDING_Y_PX}px`,
  borderRadius: `${AGENT_CONSTRUCTOR_FIELD_RADIUS_PX}px`,
  bgcolor: FIELD_BG,
  border: `1px solid ${FIELD_BORDER}`,
  cursor: 'pointer',
  userSelect: 'none' as const,
  transition: 'background 0.15s, border-color 0.15s',
  fontSize: AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
  lineHeight: AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT,
  color: FIELD_TEXT,
  '&:hover': {
    borderColor: FIELD_BORDER_HOVER,
    bgcolor: FIELD_BG_HOVER,
  },
};

// ─── Стиль выпадающего окна (кнопка + Popover), как у «Агенты» / «Категория» ───

/** Цвет фона кнопки-триггера выпадающего списка. */
export const DROPDOWN_TRIGGER_BG = 'rgba(0,0,0,0.25)';
/** Цвет фона кнопки при наведении. */
export const DROPDOWN_TRIGGER_BG_HOVER = 'rgba(0,0,0,0.35)';
/** Рамка кнопки-триггера. */
export const DROPDOWN_TRIGGER_BORDER = '1px solid rgba(255,255,255,0.15)';
/** Цвет иконки-шеврона. */
export const DROPDOWN_CHEVRON_COLOR = 'rgba(255,255,255,0.45)';

/** Стиль кнопки, открывающей выпадающий список (Агенты, Категория, Настройки и т.п.). */
export const DROPDOWN_TRIGGER_BUTTON_SX = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  px: 1.5,
  py: 1,
  borderRadius: '10px',
  bgcolor: DROPDOWN_TRIGGER_BG,
  border: DROPDOWN_TRIGGER_BORDER,
  cursor: 'pointer',
  userSelect: 'none' as const,
  transition: 'background 0.15s',
  '&:hover': { bgcolor: DROPDOWN_TRIGGER_BG_HOVER },
};

/** Стиль иконки шеврона в кнопке выпадающего списка (transform задаётся в компоненте по open). */
export const DROPDOWN_CHEVRON_SX = {
  color: DROPDOWN_CHEVRON_COLOR,
  fontSize: 18,
  transition: 'transform 0.2s',
};

/** Фон бумаги (Popover) выпадающего списка — чёрный, не серый (theme.paper = #1e1e1e). */
export const DROPDOWN_PAPER_BG = '#0f1116';
/** Рамка бумаги выпадающего списка. */
export const DROPDOWN_PAPER_BORDER = '1px solid rgba(255,255,255,0.10)';
/** Тень выпадающего окна. */
export const DROPDOWN_PAPER_SHADOW = '0 8px 32px rgba(0,0,0,0.5)';
/** Размытие фона выпадающего окна. */
export const DROPDOWN_PAPER_BLUR = 'blur(12px)';
/** Минимальная ширина выпадающего списка, px. */
export const DROPDOWN_PAPER_MIN_WIDTH_PX = 180;
/** Ширина по умолчанию, если якорь не задан, px. */
export const DROPDOWN_PAPER_DEFAULT_WIDTH_PX = 220;
/** Отступ сверху от кнопки до выпадающего окна (theme spacing). */
export const DROPDOWN_PAPER_MARGIN_TOP = 0.75;

/**
 * Общий стиль «окошка» выпадающего меню (фон, рамка, тень, скругление).
 * Используется в конструкторе агентов (Агенты, Категория) и в селекторе «Агент / Модель».
 * background задан явно, чтобы перебить theme.palette.background.paper (серый фон от темы).
 */
export const DROPDOWN_PANEL_SX: Record<string, unknown> = {
  bgcolor: DROPDOWN_PAPER_BG,
  background: `${DROPDOWN_PAPER_BG} !important`,
  backgroundColor: `${DROPDOWN_PAPER_BG} !important`,
  backdropFilter: DROPDOWN_PAPER_BLUR,
  border: DROPDOWN_PAPER_BORDER,
  borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
  boxShadow: DROPDOWN_PAPER_SHADOW,
  overflow: 'hidden',
};

/** Theme-aware стиль «окошка» меню/подменю (dark/light). */
export function getDropdownPanelSx(isDarkMode: boolean): Record<string, unknown> {
  return {
    bgcolor: isDarkMode ? '#0f1116' : 'rgba(255,255,255,0.97)',
    background: isDarkMode ? '#0f1116 !important' : 'rgba(255,255,255,0.97) !important',
    backgroundColor: isDarkMode ? '#0f1116 !important' : 'rgba(255,255,255,0.97) !important',
    backdropFilter: DROPDOWN_PAPER_BLUR,
    border: isDarkMode ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(0,0,0,0.10)',
    borderRadius: `${MENU_BORDER_RADIUS_PX}px`,
    boxShadow: isDarkMode ? '0 8px 32px rgba(0,0,0,0.5)' : '0 8px 24px rgba(0,0,0,0.16)',
    overflow: 'hidden',
  };
}

/**
 * Стиль для slotProps.paper выпадающего Popover (Агенты, Категория, поиск в конструкторе).
 * Ширина подстраивается под ширину якоря (кнопки).
 * background/backgroundColor с !important перебивают theme.palette.background.paper.
 */
export function getDropdownPopoverPaperSx(anchorEl: HTMLElement | null): Record<string, unknown> {
  return {
    ...DROPDOWN_PANEL_SX,
    background: `${DROPDOWN_PAPER_BG} !important`,
    backgroundColor: `${DROPDOWN_PAPER_BG} !important`,
    mt: DROPDOWN_PAPER_MARGIN_TOP,
    minWidth: DROPDOWN_PAPER_MIN_WIDTH_PX,
    width: anchorEl ? `${anchorEl.getBoundingClientRect().width}px` : DROPDOWN_PAPER_DEFAULT_WIDTH_PX,
  };
}

/** Подсветка пункта при hover в тёмной теме (не задавать color: white — ломает светлую панель). */
export const DROPDOWN_ITEM_HOVER_BG_DARK = 'rgba(255,255,255,0.10)';
/** Подсветка пункта при hover в светлой теме. */
export const DROPDOWN_ITEM_HOVER_BG_LIGHT = 'rgba(0,0,0,0.06)';

/** @deprecated Используйте DROPDOWN_ITEM_HOVER_BG_DARK или getDropdownItemSx(). */
export const DROPDOWN_ITEM_HOVER_BG = DROPDOWN_ITEM_HOVER_BG_DARK;

/** Стиль пункта выпадающего списка с учётом темы (hover без принудительного белого текста). */
export function getDropdownItemSx(isDarkMode: boolean): Record<string, unknown> {
  return {
    px: 1.5,
    py: 0.85,
    fontSize: AGENT_CONSTRUCTOR_FIELD_FONT_SIZE,
    lineHeight: AGENT_CONSTRUCTOR_FIELD_LINE_HEIGHT,
    cursor: 'pointer',
    borderRadius: `${AGENT_CONSTRUCTOR_FIELD_RADIUS_PX}px`,
    mx: 0.5,
    transition: 'all 0.12s',
    '&:hover': {
      bgcolor: isDarkMode ? DROPDOWN_ITEM_HOVER_BG_DARK : DROPDOWN_ITEM_HOVER_BG_LIGHT,
    },
  };
}

/**
 * По умолчанию — как для тёмной панели (конструктор, часть модалок).
 * Для меню в светлой теме передавайте getDropdownItemSx(false) или getDropdownItemSx(theme.palette.mode === 'dark').
 */
export const DROPDOWN_ITEM_SX: Record<string, unknown> = getDropdownItemSx(true);
