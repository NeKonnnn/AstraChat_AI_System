/** События для действий, требующих UI вне глобального обработчика (фокус поиска, вложения). */
export const ASTRA_FOCUS_CHAT_SEARCH = 'astrachat:focus-chat-search';
export const ASTRA_PREFILL_CHAT_INPUT = 'astrachatPrefillChatInput';
export const ASTRA_TRIGGER_ATTACH = 'astrachat:trigger-attach';
export const ASTRA_REQUEST_DELETE_CURRENT_CHAT = 'astrachat:request-delete-current-chat';
export const ASTRA_OPEN_SETTINGS = 'astrachat:open-settings';
export const ASTRA_OPEN_SETTINGS_SECTION = 'astrachat:open-settings-section';
export const ASTRA_OPEN_AGENT_CONSTRUCTOR = 'astrachat:open-agent-constructor';
export const ASTRA_OPEN_TRANSCRIPTION_SIDEBAR = 'astrachat:open-transcription-sidebar';

export function isPrimaryModifier(e: KeyboardEvent | React.KeyboardEvent): boolean {
  return e.ctrlKey || e.metaKey;
}

/** Поля ввода: для этих целей не перехватываем Shift+K / O / Delete (кроме отдельных исключений). */
export function isTypingInField(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return false;
}

export function primaryModifierLabel(): string {
  if (typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
    return '⌘';
  }
  return 'Ctrl';
}

export const hotkeyLabel = {
  newChat: () => `${primaryModifierLabel()}+Shift+K`,
  searchChats: () => `${primaryModifierLabel()}+O`,
  attachFiles: () => `${primaryModifierLabel()}+U`,
  deleteChat: () => `${primaryModifierLabel()}+Del`,
  openSettings: () => 'Alt+S',
  openAgentConstructor: () => 'Alt+A',
  openTranscription: () => 'Alt+T',
} as const;
