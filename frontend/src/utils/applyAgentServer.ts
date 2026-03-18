/**
 * Инициализация агента на сервере в том же порядке, что и выбор глобальной модели:
 * 1) загрузка весов (POST /api/models/load)
 * 2) применение настроек (temperature, max_tokens, …)
 * 3) глобальный системный промпт агента
 */
import { getApiUrl } from '../config/api';

const SETTINGS_KEYS = [
  'context_size',
  'output_tokens',
  'temperature',
  'top_p',
  'repeat_penalty',
  'top_k',
  'min_p',
  'frequency_penalty',
  'presence_penalty',
  'use_gpu',
  'streaming',
] as const;

function sanitizeModelPath(p: string): string {
  let s = p.trim().replace(/\s+/g, '');
  if (/^1lm-svc:\/\//i.test(s)) {
    s = 'llm-svc://' + s.slice(10);
  }
  return s;
}

export async function applyAgentModelAndSettings(
  token: string,
  opts: {
    system_prompt: string;
    model_path?: string | null;
    model_settings?: Record<string, unknown> | null;
  }
): Promise<{ ok: true } | { ok: false; message: string }> {
  const authHeaders: HeadersInit = { Authorization: `Bearer ${token}` };
  const jsonHeaders: HeadersInit = { 'Content-Type': 'application/json', ...authHeaders };

  let mp = typeof opts.model_path === 'string' ? sanitizeModelPath(opts.model_path) : '';
  if (mp && !mp.startsWith('llm-svc://') && !mp.includes('/') && !mp.toLowerCase().endsWith('.gguf')) {
    mp = `llm-svc://${mp}`;
  }

  // ── 1. Веса модели (как при выборе «Модели» в селекторе) ──
  if (mp) {
    const loadRes = await fetch(getApiUrl('/api/models/load'), {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ model_path: mp }),
    });
    const loadData = (await loadRes.json().catch(() => ({}))) as {
      success?: boolean;
      message?: string;
      detail?: string;
    };
    if (!loadRes.ok || !loadData.success) {
      return {
        ok: false,
        message: loadData.message || loadData.detail || 'Не удалось загрузить модель агента',
      };
    }
  }

  // ── 2. Настройки генерации (после загрузки весов) ──
  const raw = opts.model_settings;
  if (raw && typeof raw === 'object') {
    let base: Record<string, unknown> = {};
    try {
      const sr = await fetch(getApiUrl('/api/models/settings'), { headers: authHeaders });
      if (sr.ok) base = (await sr.json()) as Record<string, unknown>;
    } catch {
      /* */
    }
    const merged: Record<string, unknown> = { ...base };
    for (const k of SETTINGS_KEYS) {
      if (raw[k] !== undefined && raw[k] !== null) merged[k] = raw[k];
    }
    const setRes = await fetch(getApiUrl('/api/models/settings'), {
      method: 'PUT',
      headers: jsonHeaders,
      body: JSON.stringify(merged),
    });
    if (!setRes.ok) {
      const t = await setRes.text();
      return { ok: false, message: t || 'Настройки модели: ошибка' };
    }
  }

  // ── 3. Системный промпт агента ──
  const promptRes = await fetch(getApiUrl('/api/context-prompts/global'), {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify({ prompt: opts.system_prompt || '' }),
  });
  if (!promptRes.ok) {
    const t = await promptRes.text();
    return { ok: false, message: t || 'Промпт: ошибка' };
  }

  return { ok: true };
}
