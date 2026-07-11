import type { ChatInputSuggestion } from './inputSuggestions';
import { generalChatSuggestions } from './inputSuggestions';
import { getRagSuggestions } from './ragSuggestions';
import { getMcpSuggestions } from '../mcp/plugins/mcpSuggestions';

/**
 * Собирает умные подсказки: контекстные (RAG, MCP) + общие.
 * При включённой библиотеке RAG-подсказки идут первыми, затем MCP.
 */
export function getChatInputSuggestions(
  enabledMcpServerIds: string[],
  ragActive = false,
): ChatInputSuggestion[] {
  const contextual = [
    ...getRagSuggestions(ragActive),
    ...getMcpSuggestions(enabledMcpServerIds),
  ];
  if (contextual.length === 0) {
    return generalChatSuggestions;
  }
  const contextualIds = new Set(contextual.map((s) => s.id));
  const generalWithoutDupes = generalChatSuggestions.filter((g) => !contextualIds.has(g.id));
  return [...contextual, ...generalWithoutDupes];
}
