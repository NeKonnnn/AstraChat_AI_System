/**
 * Общие стили для выпадающих меню и подменю в приложении.
 * Единое место для цветов и скругления — используется в Sidebar,
 * MoveToFolderAndProjectMenus, App (тема) и других компонентах с меню.
 */

/** Скругление углов у контейнеров меню и подменю в пикселях. Один раз задаём — везде одинаково. */
export const MENU_BORDER_RADIUS_PX = 18;

/** Скругление подсветки пункта при наведении (подушечка, не во всю ширину). */
export const MENU_ITEM_HOVER_RADIUS_PX = 12;
/** Горизонтальный отступ подсветки от краёв меню (чтобы не была полной полосой). */
export const MENU_ITEM_HOVER_MARGIN_PX = 4;

/** Минимальная ширина области иконки в пунктах меню (компактно — иконка вплотную к тексту). */
export const MENU_ICON_MIN_WIDTH = 22;
/** Отступ справа от иконки до текста в пунктах меню (в пикселях). Минимальный зазор как на референсе ~2–4px. */
export const MENU_ICON_TO_TEXT_GAP_PX = 2;
/** Размер иконок в меню/подменю (чуть крупнее текста ~14px). */
export const MENU_ICON_FONT_SIZE_PX = 20;

/** Зазор между иконкой и текстом в списке сайдбара (проекты, чаты). */
export const SIDEBAR_LIST_ICON_TO_TEXT_GAP_PX = 4;
/** Размер аватарки-иконки проекта в сайдбаре (пропорционально тексту ~0.8rem). */
export const SIDEBAR_PROJECT_AVATAR_SIZE = 20;

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
