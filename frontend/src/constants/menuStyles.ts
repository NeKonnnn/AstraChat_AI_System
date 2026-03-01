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
