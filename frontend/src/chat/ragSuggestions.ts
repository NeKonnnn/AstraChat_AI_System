import type { ChatInputSuggestion } from './inputSuggestions';

export const ragSuggestionItems: ChatInputSuggestion[] = [
  {
    id: 'rag-summary',
    title: 'Краткое саммари',
    subtitle: 'по документам из библиотеки',
    content: 'Сделай краткое саммари по документам из библиотеки знаний.',
    keywords: ['саммари', 'резюме', 'summary', 'кратко', 'документ'],
    source: 'rag',
  },
  {
    id: 'rag-find',
    title: 'Найди в библиотеке',
    subtitle: 'информацию по теме',
    content: 'Найди в библиотеке знаний информацию по теме: ',
    keywords: ['найди', 'поиск', 'библиотека', 'документы'],
    source: 'rag',
  },
  {
    id: 'rag-key-points',
    title: 'Ключевые выводы',
    subtitle: 'из загруженных материалов',
    content: 'Какие ключевые выводы можно сделать из документов в библиотеке?',
    keywords: ['выводы', 'главное', 'суть', 'ключевое'],
    source: 'rag',
  },
  {
    id: 'rag-quotes',
    title: 'Цитаты',
    subtitle: 'со ссылкой на источник',
    content: 'Приведи цитаты из документов библиотеки по вопросу: ',
    keywords: ['цитата', 'источник', 'ссылка', 'цитаты'],
    source: 'rag',
  },
  {
    id: 'rag-topics',
    title: 'Темы документов',
    subtitle: 'что есть в библиотеке',
    content: 'Перечисли основные темы, которые освещены в документах библиотеки.',
    keywords: ['темы', 'содержание', 'оглавление', 'список'],
    source: 'rag',
  },
  {
    id: 'rag-compare',
    title: 'Сравни',
    subtitle: 'данные из разных документов',
    content: 'Сравни информацию из документов библиотеки по теме: ',
    keywords: ['сравни', 'разница', 'противоречия', 'сопоставь'],
    source: 'rag',
  },
];

export function getRagSuggestions(ragActive: boolean): ChatInputSuggestion[] {
  if (!ragActive) return [];
  return ragSuggestionItems;
}
