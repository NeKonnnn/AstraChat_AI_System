import { getAtlassianSuggestions } from './atlassianSuggestions';
import { getWebSearchSuggestions } from './webSearchSuggestions';

/** Объединённые подсказки для всех подключённых MCP-серверов. */
export function getMcpSuggestions(enabledServerIds: string[]): string[] {
  return [
    ...getAtlassianSuggestions(enabledServerIds),
    ...getWebSearchSuggestions(enabledServerIds),
  ];
}
