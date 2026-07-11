/** Геометрия нижнего тулбара ChatInputBar (classic / compact). */

export const CHAT_INPUT_TOOLBAR_PAD_CLASSIC = 1.5;
export const CHAT_INPUT_TOOLBAR_PAD_COMPACT = 2;
export const CHAT_INPUT_TOOLBAR_BTN_PX = 36;
export const CHAT_INPUT_TOOLBAR_GAP = 0.25;

/** Примерная ширина «пилюли» библиотека/агент/MCP между «+» и «Инструменты». */
export function estimateLibraryClusterWidthPx(
  libraryActive: boolean,
  agentActive: boolean,
  mcpActive: boolean,
  mcpLabel = '',
): number {
  if (!libraryActive && !agentActive && !mcpActive) return 0;

  let width = 0;
  const addSegment = (segmentPx: number) => {
    if (width > 0) width += 1;
    width += segmentPx;
  };

  if (libraryActive) addSegment(36);
  if (agentActive) addSegment(36);
  if (mcpActive) {
    const labelExtra = Math.min(88, Math.max(0, mcpLabel.length) * 6.5);
    addSegment(36 + labelExtra);
  }

  return width;
}

/** Отступ слева (в единицах theme.spacing), чтобы выровнять блок под кнопкой «Инструменты». */
export function getToolsButtonInsetSp(
  inputStyle: 'classic' | 'compact',
  libraryClusterWidthPx: number,
  hasAttachButton = true,
): number {
  const pxUnit = 8;
  const shellPadSp = inputStyle === 'classic' ? CHAT_INPUT_TOOLBAR_PAD_CLASSIC : CHAT_INPUT_TOOLBAR_PAD_COMPACT;
  let offsetPx = shellPadSp * pxUnit;

  if (hasAttachButton) {
    offsetPx += CHAT_INPUT_TOOLBAR_BTN_PX + CHAT_INPUT_TOOLBAR_GAP * pxUnit;
  }
  if (libraryClusterWidthPx > 0) {
    offsetPx += libraryClusterWidthPx + CHAT_INPUT_TOOLBAR_GAP * pxUnit;
  }

  return offsetPx / pxUnit;
}
