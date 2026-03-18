/**
 * Единый флаг «база знаний в чате»: и классическая KB (use_kb_rag),
 * и библиотека из настроек (use_memory_library_rag). Socket читает оба ключа при отправке.
 */
const KB_KEY = 'use_kb_rag';
const MEM_KEY = 'use_memory_library_rag';

export const KNOWLEDGE_RAG_STORAGE_EVENT = 'astrachat:knowledgeRag';

export function isKnowledgeRagEnabled(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return (
    localStorage.getItem(KB_KEY) === 'true' || localStorage.getItem(MEM_KEY) === 'true'
  );
}

/** Включает/выключает оба флага — LLM получает контекст и из KB, и из библиотеки памяти. */
export function setKnowledgeRagEnabled(enabled: boolean): void {
  const s = String(enabled);
  localStorage.setItem(KB_KEY, s);
  localStorage.setItem(MEM_KEY, s);
  try {
    window.dispatchEvent(
      new CustomEvent(KNOWLEDGE_RAG_STORAGE_EVENT, { detail: { enabled } })
    );
  } catch {
    /* ignore */
  }
}
