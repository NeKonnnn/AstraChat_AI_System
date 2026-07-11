export const webSearchSuggestionChips = [
  'Найди в интернете последние новости по теме',
  'Поищи в сети документацию и кратко перескажи',
  'Какие есть актуальные данные по этому вопросу?',
];

export function getWebSearchSuggestions(enabledServerIds: string[]): string[] {
  if (!enabledServerIds.includes('websearch')) return [];
  return webSearchSuggestionChips;
}
