import { useEffect, useRef } from 'react';
import type { Message } from '../contexts/AppContext';
import { fetchFollowUpSuggestions } from '../chat/fetchFollowUpSuggestions';
import type { FollowUpShowScope } from '../chat/followUpSettings';
import { LAST_SELECTED_MODEL_PATH_STORAGE_KEY } from '../utils/modelThinking';

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

  useEffect(() => {
    fetchedRef.current.clear();
    inflightRef.current.clear();
    prevStreamingRef.current.clear();
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current.clear();
  }, [chatId]);

  useEffect(() => {
    if (!enabled) return;
    fetchedRef.current.clear();
  }, [enabled, chatId]);

  useEffect(() => {
    if (!enabled || !chatId) return;

    for (const message of messages) {
      const wasStreaming = prevStreamingRef.current.get(message.id) ?? false;
      const nowStreaming = Boolean(message.isStreaming);
      const key = requestKey(chatId, message.id);

      if (nowStreaming && message.role === 'assistant') {
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

      inflightRef.current.add(key);
      fetchedRef.current.add(key);

      const controller = new AbortController();
      abortControllersRef.current.set(key, controller);

      const historyEndIndex = messages.findIndex((m) => m.id === message.id);
      const historyMessages = historyEndIndex >= 0 ? messages.slice(0, historyEndIndex + 1) : messages;
      const modelPath = localStorage.getItem(LAST_SELECTED_MODEL_PATH_STORAGE_KEY) || null;

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
    }
  }, [messages, chatId, enabled, showScope, patchMessageFields]);

  useEffect(() => {
    if (enabled) return;
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current.clear();
    inflightRef.current.clear();
  }, [enabled]);

  useEffect(() => {
    return () => {
      abortControllersRef.current.forEach((controller) => controller.abort());
      abortControllersRef.current.clear();
      inflightRef.current.clear();
    };
  }, [chatId]);
}
