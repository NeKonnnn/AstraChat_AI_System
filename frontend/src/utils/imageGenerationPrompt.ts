/** Эвристика: сообщение похоже на запрос генерации картинки (как на бэкенде). */
export function isLikelyImageGenerationPrompt(text: string): boolean {
  const t = (text || '').trim();
  if (!t) return false;
  if (/^(?:\/image|\/img)\s+/i.test(t)) return true;
  if (
    /^(?:пожалуйста\s+)?(?:нарисуй|нарисуйте|сгенерируй|создай|сделай|draw|generate|create|make|paint)\b/i.test(
      t,
    )
  ) {
    return true;
  }
  return false;
}
