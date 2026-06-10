export const atlassianSuggestionChips = [
  'Мои открытые задачи в Jira',
  'Поиск в Confluence: onboarding',
  'Создай задачу в Jira с описанием',
];

export function getAtlassianSuggestions(enabledServerIds: string[]): string[] {
  if (!enabledServerIds.includes('atlassian')) return [];
  return atlassianSuggestionChips;
}
