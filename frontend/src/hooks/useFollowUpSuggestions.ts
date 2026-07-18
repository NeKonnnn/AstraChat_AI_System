import { useEffect, useRef } from 'react';
import type { Message } from '../contexts/AppContext';
import { fetchFollowUpSuggestions } from '../chat/fetchFollowUpSuggestions';
import type { FollowUpShowScope } from '../chat/followUpSettings';
import { LAST_SELECTED_MODEL_PATH_STORAGE_KEY } from '../utils/modelThinking';

/** Задержка: не занимать LLM follow-up сразу после ответа — иначе «Перегенерировать» ждёт gen_lock. */
const FOLLOW_UP_START_DELAY_MS = 2500;

function isFollowUpEligible(message: Message): boolean {
  if (message.role !== 'assistant') return false;
  if (message.isStreaming) return false;
  if (message.multiLLMResponses?.length) return false;
  if (message.isImageGenerating) return false;
  return Boolean((message.content || '').trim());
}

function requestKey(chatId: string, messageId: string): string {
  return `${chatId}:${messageId}`;
}

function abortAllFollowUps(
  abortControllersRef: { current: Map<string, AbortController> },
  inflightRef: { current: Set<string> },
  fetchedRef: { current: Set<string> },
): void {
  abortControllersRef.current.forEach((controller) => controller.abort());
  abortControllersRef.current.clear();
  inflightRef.current.clear();
  // Позволяем повторить позже, когда чат свободен
  fetchedRef.current.clear();
}

export function useFollowUpSuggestions(params: {
  chatId: string | undefined;
  messages: Message[];
  enabled: boolean;
  showScope: FollowUpShowScope;
  patchMessageFields: (
    chatId: string,
    messageId: string,
    fields: Partial<Pick<Message, 'followUpSuggestions' | 'followUpSuggestionsLoading'>>,
  ) => void;
}): void {
  const { chatId, messages, enabled, showScope, patchMessageFields } = params;
  const inflightRef = useRef<Set<string>>(new Set());
  const fetchedRef = useRef<Set<string>>(new Set());
  const prevStreamingRef = useRef<Map<string, boolean>>(new Map());
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const delayTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const clearDelayTimers = () => {
    delayTimersRef.current.forEach((timer) => clearTimeout(timer));
    delayTimersRef.current.clear();
  };

  useEffect(() => {
    fetchedRef.current.clear();
    inflightRef.current.clear();
    prevStreamingRef.current.clear();
    clearDelayTimers();
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current.clear();
  }, [chatId]);

  useEffect(() => {
    if (!enabled) return;
    fetchedRef.current.clear();
  }, [enabled, chatId]);

  // Перегенерация / новый запрос — немедленно рвём follow-up HTTP
  useEffect(() => {
    const onAbort = () => {
      clearDelayTimers();
      abortAllFollowUps(abortControllersRef, inflightRef, fetchedRef);
    };
    window.addEventListener('astrachat-abort-follow-ups', onAbort);
    return () => window.removeEventListener('astrachat-abort-follow-ups', onAbort);
  }, []);

  useEffect(() => {
    if (!enabled || !chatId) return;

    for (const message of messages) {
      const wasStreaming = prevStreamingRef.current.get(message.id) ?? false;
      const nowStreaming = Boolean(message.isStreaming);
      const key = requestKey(chatId, message.id);

      if (nowStreaming && message.role === 'assistant') {
        const delayTimer = delayTimersRef.current.get(key);
        if (delayTimer) {
          clearTimeout(delayTimer);
          delayTimersRef.current.delete(key);
        }
        const controller = abortControllersRef.current.get(key);
        controller?.abort();
        abortControllersRef.current.delete(key);
        inflightRef.current.delete(key);
        fetchedRef.current.delete(key);
        patchMessageFields(chatId, message.id, {
          followUpSuggestions: undefined,
        });
      }

      if (wasStreaming && !nowStreaming && message.role === 'assistant') {
        fetchedRef.current.delete(key);
        patchMessageFields(chatId, message.id, {
          followUpSuggestions: undefined,
        });
      }

      prevStreamingRef.current.set(message.id, nowStreaming);
    }
  }, [messages, chatId, enabled, patchMessageFields]);

  useEffect(() => {
    if (!enabled || !chatId) return;

    // Пока идёт любой стрим в чате — follow-up не стартуем (один слот LLM).
    if (messages.some((m) => m.isStreaming)) {
      clearDelayTimers();
      return;
    }

    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : undefined;
    const targets =
      showScope === 'last'
        ? lastMessage && isFollowUpEligible(lastMessage)
          ? [lastMessage]
          : []
        : messages.filter(isFollowUpEligible);

    for (const message of targets) {
      const key = requestKey(chatId, message.id);
      if (message.followUpSuggestions?.length) {
        fetchedRef.current.add(key);
        continue;
      }
      if (message.isStreaming) continue;
      if (inflightRef.current.has(key)) continue;
      if (fetchedRef.current.has(key)) continue;
      if (delayTimersRef.current.has(key)) continue;

      const historyEndIndex = messages.findIndex((m) => m.id === message.id);
      const historyMessages = historyEndIndex >= 0 ? messages.slice(0, historyEndIndex + 1) : messages;
      const modelPath = localStorage.getItem(LAST_SELECTED_MODEL_PATH_STORAGE_KEY) || null;

      const timer = setTimeout(() => {
        delayTimersRef.current.delete(key);
        if (inflightRef.current.has(key) || fetchedRef.current.has(key)) return;

        inflightRef.current.add(key);
        fetchedRef.current.add(key);

        const controller = new AbortController();
        abortControllersRef.current.set(key, controller);

        void fetchFollowUpSuggestions({
          messages: historyMessages,
          modelPath,
          signal: controller.signal,
        })
          .then((suggestions) => {
            if (controller.signal.aborted) return;
            patchMessageFields(chatId, message.id, {
              followUpSuggestions: suggestions.length > 0 ? suggestions : undefined,
            });
          })
          .catch(() => {
            if (controller.signal.aborted) return;
            fetchedRef.current.delete(key);
            patchMessageFields(chatId, message.id, {
              followUpSuggestions: undefined,
            });
          })
          .finally(() => {
            inflightRef.current.delete(key);
            abortControllersRef.current.delete(key);
          });
      }, FOLLOW_UP_START_DELAY_MS);

      delayTimersRef.current.set(key, timer);
    }
  }, [messages, chatId, enabled, showScope, patchMessageFields]);

  useEffect(() => {
    if (enabled) return;
    clearDelayTimers();
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current.clear();
    inflightRef.current.clear();
  }, [enabled]);

  useEffect(() => {
    return () => {
      clearDelayTimers();
      abortControllersRef.current.forEach((controller) => controller.abort());
      abortControllersRef.current.clear();
      inflightRef.current.clear();
    };
  }, [chatId]);
}
