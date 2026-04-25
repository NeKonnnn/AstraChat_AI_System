/** Сплошной фон основной рабочей зоны (чат, проект). Боковые панели не затрагиваются. */
export const WORK_ZONE_BACKGROUND_DARK = '#232326';
export const WORK_ZONE_BACKGROUND_LIGHT = '#fafafa';

/**
 * Пилюля поля ввода в тёмной теме при «звёздном» фоне — тот же вид, что и
 * rgba(255,255,255,0.05) поверх WORK_ZONE_BACKGROUND_DARK (не заливка всей зоны).
 */
export const CHAT_INPUT_SURFACE_DARK = '#454545';
export const CHAT_INPUT_BORDER_DARK = 'rgba(255, 255, 255, 0.14)';

/** Аналогично для светлой темы: rgba(0,0,0,0.05) на WORK_ZONE_BACKGROUND_LIGHT */
export const CHAT_INPUT_SURFACE_LIGHT = '#ededed';
export const CHAT_INPUT_BORDER_LIGHT = 'rgba(0, 0, 0, 0.1)';

/** Режим фона рабочей зоны (настройки → Интерфейс). */
export const WORK_ZONE_BG_MODE_KEY = 'work_zone_bg_mode';
export const WORK_ZONE_BG_CUSTOM_IMAGE_KEY = 'work_zone_bg_custom_image';

export type WorkZoneBgMode = 'default' | 'starry' | 'snowfall' | 'custom';

export function getWorkZoneCustomImage(): string | null {
  if (typeof window === 'undefined') return null;
  const value = localStorage.getItem(WORK_ZONE_BG_CUSTOM_IMAGE_KEY);
  return value && value.trim() ? value : null;
}

export function getWorkZoneBgMode(): WorkZoneBgMode {
  if (typeof window === 'undefined') return 'default';
  const v = localStorage.getItem(WORK_ZONE_BG_MODE_KEY);
  if (v === 'starry' || v === 'snowfall') return v;
  if (v === 'custom' && getWorkZoneCustomImage()) return 'custom';
  return 'default';
}

/** Не стандартный фон: нужны z-index, непрозрачная пилюля ввода. */
export function isWorkZoneAnimatedMode(mode: WorkZoneBgMode): boolean {
  return mode === 'starry' || mode === 'snowfall';
}

/** Базовый цвет под «звёздным» небом (canvas рисует поверх). */
export const STARRY_ZONE_BASE_DARK = '#000000';
export const STARRY_ZONE_BASE_LIGHT = '#000000';

/** Тёмно-синий под снегопадом (canvas рисует градиент поверх). */
export const SNOWFALL_ZONE_BASE_DARK = '#0a1426';
export const SNOWFALL_ZONE_BASE_LIGHT = '#0d1830';

export function getWorkZoneBackgroundColor(isDark: boolean, mode: WorkZoneBgMode): string {
  if (mode === 'default') return isDark ? WORK_ZONE_BACKGROUND_DARK : WORK_ZONE_BACKGROUND_LIGHT;
  if (mode === 'starry') return isDark ? STARRY_ZONE_BASE_DARK : STARRY_ZONE_BASE_LIGHT;
  if (mode === 'custom') return isDark ? WORK_ZONE_BACKGROUND_DARK : WORK_ZONE_BACKGROUND_LIGHT;
  return isDark ? SNOWFALL_ZONE_BASE_DARK : SNOWFALL_ZONE_BASE_LIGHT;
}
