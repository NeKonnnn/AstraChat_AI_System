export type ModelThinkingMode = 'auto' | 'thinking' | 'fast';

export const MODEL_THINKING_MODE_STORAGE_KEY = 'model_thinking_mode';
export const LAST_SELECTED_MODEL_PATH_STORAGE_KEY = 'last_selected_model_path';

const PLACEHOLDER_MODEL_PATHS = new Set(['llm-svc', 'llm-svc://', 'local', 'default']);

/** Путь считается выбранной моделью, а не заглушкой провайдера (llm-svc без model_id). */
export function isValidSelectedModelPath(path: string | null | undefined): boolean {
  const raw = (path || '').trim();
  if (!raw) return false;

  const lower = raw.toLowerCase();
  if (PLACEHOLDER_MODEL_PATHS.has(lower)) return false;

  if (lower.startsWith('llm-svc://')) {
    const rest = raw.slice('llm-svc://'.length).replace(/^\/+/, '');
    return Boolean(rest);
  }

  if (raw.includes('/')) {
    const modelPart = raw.split('/').slice(1).join('/').trim();
    return Boolean(modelPart);
  }

  if (lower.endsWith('.gguf')) return true;
  if (raw.length > 2 && raw[1] === ':') return true;
  if (raw.startsWith('/') && raw.length > 1) return true;

  return false;
}

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

