import type { ChatInputSuggestion } from '../../chat/inputSuggestions';

export const atlassianSuggestionItems: ChatInputSuggestion[] = [
  {
    id: 'atlassian-jira-open',
    title: 'Мои задачи',
    subtitle: 'открытые в Jira',
    content: 'Покажи мои открытые задачи в Jira',
    keywords: ['jira', 'задачи', 'issues'],
    source: 'mcp',
    mcpServerId: 'atlassian',
  },
  {
    id: 'atlassian-confluence',
    title: 'Confluence',
    subtitle: 'поиск по базе знаний',
    content: 'Найди в Confluence информацию по теме: onboarding',
    keywords: ['confluence', 'wiki', 'документы'],
    source: 'mcp',
    mcpServerId: 'atlassian',
  },
  {
    id: 'atlassian-create-issue',
    title: 'Создай задачу',
    subtitle: 'в Jira',
    content: 'Создай задачу в Jira с описанием: ',
    keywords: ['создай', 'issue', 'ticket'],
    source: 'mcp',
    mcpServerId: 'atlassian',
  },
];

/** @deprecated Используйте atlassianSuggestionItems */
export const atlassianSuggestionChips = atlassianSuggestionItems.map((s) => s.content);

export function getAtlassianSuggestions(enabledServerIds: string[]): ChatInputSuggestion[] {
  if (!enabledServerIds.includes('atlassian')) return [];
  return atlassianSuggestionItems;
}
