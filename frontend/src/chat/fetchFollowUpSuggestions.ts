import { getApiUrl, getAuthFetchHeaders } from '../config/api';
import type { ChatInputSuggestion } from './inputSuggestions';
import type { Message } from '../contexts/AppContext';
import { extractReasoningBlock } from '../utils/reasoningSplit';
export interface FollowUpApiSuggestion {
  id?: string;
  title: string;
  subtitle?: string;
  content: string;
}

export function mapFollowUpApiSuggestions(items: FollowUpApiSuggestion[]): ChatInputSuggestion[] {
  return items
    .filter((item) => item.title?.trim() && item.content?.trim())
    .slice(0, 3)
    .map((item, index) => ({
      id: item.id || `follow-up-${index}`,
      title: item.title.trim(),
      subtitle: item.subtitle?.trim() || undefined,
      content: item.content.trim(),
      source: 'general' as const,
    }));
}

export function buildFollowUpHistory(messages: Message[]): Array<{ role: 'user' | 'assistant'; content: string }> {
  return messages
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && !m.isStreaming)
    .map((m) => {
      const parsed = m.role === 'assistant' ? extractReasoningBlock(m.content || '', false) : null;
      const content = (parsed?.visibleContent ?? m.content ?? '').trim();
      return {
        role: m.role,
        content,
      };
    })
    .filter((m) => m.content.length > 0);
}
export async function fetchFollowUpSuggestions(params: {
  messages: Message[];
  modelPath?: string | null;
  signal?: AbortSignal;
}): Promise<ChatInputSuggestion[]> {
  const history = buildFollowUpHistory(params.messages);
  if (history.length === 0) return [];

  const response = await fetch(getApiUrl('/api/chat/follow-up-suggestions'), {
    method: 'POST',
    headers: getAuthFetchHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      messages: history,
      model_path: params.modelPath || null,
    }),
    signal: params.signal,
  });

  if (!response.ok) return [];
  const data = await response.json();
  const raw = Array.isArray(data.suggestions) ? data.suggestions : [];
  return mapFollowUpApiSuggestions(raw);
}
