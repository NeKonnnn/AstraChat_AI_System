import type { ChatInputSuggestion } from '../../chat/inputSuggestions';
import { getAtlassianSuggestions } from './atlassianSuggestions';
import { getWebSearchSuggestions } from './webSearchSuggestions';

/** Подсказки для всех включённых MCP-серверов. */
export function getMcpSuggestions(enabledServerIds: string[]): ChatInputSuggestion[] {
  return [
    ...getAtlassianSuggestions(enabledServerIds),
    ...getWebSearchSuggestions(enabledServerIds),
  ];
}
