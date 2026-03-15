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

/** Зазор между иконкой и текстом в списке сайдбара (проекты, чаты), px. */
export const SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX = 4;
/** Размер аватарки-иконки проекта в сайдбаре, px. Минимальная ширина колонки иконок в списке = SIDEBAR_PROJECT_AVATAR_SIZE + 4. */
export const SIDEBAR_PROJECT_AVATAR_SIZE = 18;

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

/** Цвет подсветки пункта выпадающего списка (выбран / hover). */
export const DROPDOWN_ITEM_HOVER_BG = 'rgba(255,255,255,0.10)';

/** Общий стиль пункта в выпадающем списке (без учёта selected — его задают в компоненте). */
export const DROPDOWN_ITEM_SX = {
  px: 1.5,
  py: 0.85,
  fontSize: '0.82rem',
  cursor: 'pointer',
  borderRadius: '10px',
  mx: 0.5,
  transition: 'all 0.12s',
  '&:hover': { bgcolor: DROPDOWN_ITEM_HOVER_BG, color: 'white' },
};

// ─── Поля ввода и триггеры (переиспользуемые по всему проекту) ───

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
/** Размер шрифта полей. */
export const FIELD_FONT_SIZE = '0.82rem';

/** Стиль для MUI TextField (поля ввода по всему проекту). */
export const FORM_FIELD_INPUT_SX = {
  '& .MuiOutlinedInput-root': {
    bgcolor: FIELD_BG,
    color: FIELD_TEXT,
    fontSize: FIELD_FONT_SIZE,
    '& fieldset': { borderColor: FIELD_BORDER },
    '&:hover fieldset': { borderColor: FIELD_BORDER_HOVER },
    '&.Mui-focused fieldset': { borderColor: FIELD_FOCUS },
  },
  '& .MuiInputBase-input': { color: FIELD_TEXT },
  '& .MuiInputBase-input::placeholder': { color: FIELD_PLACEHOLDER },
};

/** Стиль кнопки-триггера, выглядящей как поле (выпадающие списки, выбор модели и т.п.). */
export const FORM_FIELD_TRIGGER_SX = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  px: 1.5,
  py: 1,
  borderRadius: '10px',
  bgcolor: FIELD_BG,
  border: `1px solid ${FIELD_BORDER}`,
  cursor: 'pointer',
  userSelect: 'none' as const,
  transition: 'background 0.15s, border-color 0.15s',
  fontSize: FIELD_FONT_SIZE,
  color: FIELD_TEXT,
  '&:hover': {
    borderColor: FIELD_BORDER_HOVER,
    bgcolor: FIELD_BG_HOVER,
  },
};
