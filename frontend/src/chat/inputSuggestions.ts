export interface ChatInputSuggestion {
  id: string;
  title: string;
  subtitle?: string;
  content: string;
  keywords?: string[];
  source?: 'general' | 'mcp' | 'rag';
  mcpServerId?: string;
}

export const generalChatSuggestions: ChatInputSuggestion[] = [
  {
    id: 'explain-simple',
    title: 'Объясни',
    subtitle: 'простыми словами',
    content: 'Объясни простыми словами: ',
    keywords: ['объясни', 'просто', 'понятно'],
    source: 'general',
  },
  {
    id: 'write-code',
    title: 'Напиши код',
    subtitle: 'с комментариями',
    content: 'Напиши код на Python с комментариями для задачи: ',
    keywords: ['код', 'python', 'программа', 'скрипт'],
    source: 'general',
  },
  {
    id: 'summarize',
    title: 'Кратко перескажи',
    subtitle: 'главное из текста',
    content: 'Кратко перескажи главное из следующего текста:\n\n',
    keywords: ['перескажи', 'резюме', 'кратко', 'суть'],
    source: 'general',
  },
  {
    id: 'plan',
    title: 'Составь план',
    subtitle: 'пошаговый',
    content: 'Составь пошаговый план для: ',
    keywords: ['план', 'шаги', 'организовать'],
    source: 'general',
  },
  {
    id: 'translate',
    title: 'Переведи',
    subtitle: 'на английский',
    content: 'Переведи на английский язык:\n\n',
    keywords: ['перевод', 'английский', 'translate'],
    source: 'general',
  },
  {
    id: 'brainstorm',
    title: 'Идеи',
    subtitle: 'варианты решения',
    content: 'Предложи несколько вариантов решения для: ',
    keywords: ['идеи', 'варианты', 'brainstorm'],
    source: 'general',
  },
];

export function shuffleSuggestions<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

export function pickVisibleSuggestions(
  suggestions: ChatInputSuggestion[],
  inputValue: string,
  maxVisible: number,
): ChatInputSuggestion[] {
  const matched = filterChatInputSuggestions(suggestions, inputValue);
  if (inputValue.trim()) {
    return matched.slice(0, maxVisible);
  }

  const contextual = matched.filter((s) => s.source === 'rag' || s.source === 'mcp');
  const general = matched.filter((s) => s.source !== 'rag' && s.source !== 'mcp');
  const picked = shuffleSuggestions(contextual).slice(0, maxVisible);
  if (picked.length < maxVisible) {
    picked.push(...shuffleSuggestions(general).slice(0, maxVisible - picked.length));
  }
  return picked;
}

export function filterChatInputSuggestions(
  suggestions: ChatInputSuggestion[],
  inputValue: string,
): ChatInputSuggestion[] {
  const trimmed = inputValue.trim();
  if (!trimmed) return suggestions;
  const query = trimmed.toLowerCase();
  return suggestions.filter((item) => {
    const haystack = [
      item.title,
      item.subtitle ?? '',
      item.content,
      ...(item.keywords ?? []),
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
}
