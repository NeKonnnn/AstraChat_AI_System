export type ModelThinkingMode = 'auto' | 'thinking' | 'fast';

export const MODEL_THINKING_MODE_STORAGE_KEY = 'model_thinking_mode';
export const LAST_SELECTED_MODEL_PATH_STORAGE_KEY = 'last_selected_model_path';

export function isThinkingCapableModel(modelPathOrName: string | null | undefined): boolean {
  const normalized = (modelPathOrName || '').toLowerCase();
  if (!normalized) return false;

  return (
    normalized.includes('qwen3') ||
    normalized.includes('deepseek-r1') ||
    normalized.includes('reasoner') ||
    normalized.includes('thinking')
  );
}

export function resolveEnableThinkingByMode(
  mode: ModelThinkingMode,
  modelPathOrName: string | null | undefined,
): boolean {
  if (mode === 'thinking') return true;
  if (mode === 'fast') return false;
  return isThinkingCapableModel(modelPathOrName);
}

