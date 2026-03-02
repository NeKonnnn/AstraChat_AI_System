/** Ключ в localStorage для пользовательского цвета боковых панелей. Пустая строка = цвет по умолчанию. */
export const SIDEBAR_PANEL_COLOR_KEY = 'sidebar_panel_color';

/** Градиент по умолчанию для левой и правой боковых панелей. */
export const DEFAULT_SIDEBAR_GRADIENT = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

export function getSidebarPanelBackground(): string {
  if (typeof window === 'undefined') return DEFAULT_SIDEBAR_GRADIENT;
  const saved = localStorage.getItem(SIDEBAR_PANEL_COLOR_KEY);
  return saved || DEFAULT_SIDEBAR_GRADIENT;
}
