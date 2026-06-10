/** Отладочные логи прикрепления файлов через «+». Ищите в консоли браузера: [ChatAttach] */
const CHAT_ATTACH_DEBUG = true;

export function logChatAttach(stage: string, data?: Record<string, unknown>): void {
  if (!CHAT_ATTACH_DEBUG) return;
  const payload = data ? { stage, ...data } : { stage };
  // eslint-disable-next-line no-console
  console.info('[ChatAttach]', JSON.stringify(payload, null, 0));
}

export function logChatAttachError(stage: string, error: unknown, data?: Record<string, unknown>): void {
  if (!CHAT_ATTACH_DEBUG) return;
  const err =
    error instanceof Error
      ? { name: error.name, message: error.message, stack: error.stack?.split('\n').slice(0, 4).join(' | ') }
      : { message: String(error) };
  // eslint-disable-next-line no-console
  console.error('[ChatAttach]', JSON.stringify({ stage, error: err, ...data }, null, 0));
}
