import type { ChatInputSuggestion } from '../../chat/inputSuggestions';

export const webSearchSuggestionItems: ChatInputSuggestion[] = [
  {
    id: 'websearch-weather',
    title: 'Погода',
    subtitle: 'актуальные данные из сети',
    content: 'Какая сейчас погода в Москве? Используй поиск в интернете.',
    keywords: ['погода', 'температура', 'осадки', 'weather'],
    source: 'mcp',
    mcpServerId: 'websearch',
  },
  {
    id: 'websearch-news',
    title: 'Новости',
    subtitle: 'последние события',
    content: 'Найди в интернете последние новости по теме: ',
    keywords: ['новости', 'события', 'news'],
    source: 'mcp',
    mcpServerId: 'websearch',
  },
  {
    id: 'websearch-fx',
    title: 'Курс валют',
    subtitle: 'актуальный USD/RUB',
    content: 'Какой сейчас курс USD к рублю? Найди актуальные данные в интернете.',
    keywords: ['курс', 'доллар', 'рубль', 'валюта', 'usd'],
    source: 'mcp',
    mcpServerId: 'websearch',
  },
  {
    id: 'websearch-docs',
    title: 'Документация',
    subtitle: 'поиск в сети',
    content: 'Поищи в интернете официальную документацию и кратко перескажи: ',
    keywords: ['документация', 'docs', 'manual', 'guide'],
    source: 'mcp',
    mcpServerId: 'websearch',
  },
  {
    id: 'websearch-compare',
    title: 'Сравни',
    subtitle: 'найди факты в интернете',
    content: 'Сравни по актуальным данным из интернета: ',
    keywords: ['сравни', 'compare', 'vs', 'разница'],
    source: 'mcp',
    mcpServerId: 'websearch',
  },
];

/** @deprecated Используйте webSearchSuggestionItems */
export const webSearchSuggestionChips = webSearchSuggestionItems.map((s) => s.content);

export function getWebSearchSuggestions(enabledServerIds: string[]): ChatInputSuggestion[] {
  if (!enabledServerIds.includes('websearch')) return [];
  return webSearchSuggestionItems;
}
