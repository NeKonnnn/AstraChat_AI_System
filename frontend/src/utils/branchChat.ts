import type { Message, MultiLLMResponseSlot } from '../contexts/AppContext';

function generateMessageId(): string {
  const randomHex = Array.from({ length: 12 }, () =>
    Math.floor(Math.random() * 16).toString(16),
  ).join('');
  return `msg_${randomHex}`;
}

function getMultiLlmSlotDisplayText(slot: MultiLLMResponseSlot): string {
  if (slot.alternativeResponses?.length && slot.currentResponseIndex !== undefined) {
    const i = slot.currentResponseIndex;
    if (i >= 0 && i < slot.alternativeResponses.length) {
      const t = slot.alternativeResponses[i];
      if (t !== undefined) return t;
    }
  }
  return slot.content;
}

function resolveAssistantContentForBranch(
  message: Message,
  multiLlmSlotIndex?: number,
): Pick<Message, 'content' | 'multiLLMResponses' | 'alternativeResponses' | 'currentResponseIndex'> {
  if (multiLlmSlotIndex !== undefined && message.multiLLMResponses?.length) {
    const slot = message.multiLLMResponses[multiLlmSlotIndex];
    if (slot) {
      return {
        content: getMultiLlmSlotDisplayText(slot),
        multiLLMResponses: undefined,
        alternativeResponses: undefined,
        currentResponseIndex: undefined,
      };
    }
  }

  if (message.alternativeResponses?.length) {
    const idx = message.currentResponseIndex ?? 0;
    const alt =
      idx >= 0 && idx < message.alternativeResponses.length
        ? message.alternativeResponses[idx]
        : message.alternativeResponses[0];
    return {
      content: alt ?? message.content,
      multiLLMResponses: undefined,
      alternativeResponses: undefined,
      currentResponseIndex: undefined,
    };
  }

  return {
    content: message.content,
    multiLLMResponses: message.multiLLMResponses,
    alternativeResponses: message.alternativeResponses,
    currentResponseIndex: message.currentResponseIndex,
  };
}

function cloneMessageForBranch(
  message: Message,
  isBranchPoint: boolean,
  multiLlmSlotIndex?: number,
): Message {
  const base: Message = {
    ...message,
    id: generateMessageId(),
    isStreaming: false,
    multiLLMResponses: message.multiLLMResponses
      ? message.multiLLMResponses.map((slot) => ({ ...slot, isStreaming: false }))
      : undefined,
    alternativeResponses: message.alternativeResponses
      ? [...message.alternativeResponses]
      : undefined,
    inlineAttachments: message.inlineAttachments ? [...message.inlineAttachments] : undefined,
    mcpToolCalls: message.mcpToolCalls ? [...message.mcpToolCalls] : undefined,
    documentSearch: message.documentSearch ? { ...message.documentSearch } : undefined,
  };

  if (isBranchPoint && message.role === 'assistant') {
    const resolved = resolveAssistantContentForBranch(message, multiLlmSlotIndex);
    return {
      ...base,
      ...resolved,
      multiLLMResponses: undefined,
    };
  }

  return base;
}

/** Копирует сообщения до указанного включительно, с новыми id. */
export function cloneMessagesForBranch(
  messages: Message[],
  upToIndex: number,
  multiLlmSlotIndex?: number,
): Message[] {
  if (upToIndex < 0 || upToIndex >= messages.length) return [];
  return messages.slice(0, upToIndex + 1).map((message, index) =>
    cloneMessageForBranch(message, index === upToIndex, multiLlmSlotIndex),
  );
}

export function buildBranchChatTitle(sourceTitle: string): string {
  const trimmed = sourceTitle.trim() || 'Чат';
  return `Ветка · ${trimmed.slice(0, 40)}`;
}
