/** Теги причин дизлайка (синхрон с backend/services/user_feedback_context.py). */

export type MessageFeedbackRating = 'like' | 'dislike';

export interface MessageFeedback {
  rating: MessageFeedbackRating;
  tags?: string[];
  comment?: string;
  updatedAt?: string;
}

export const DISLIKE_FEEDBACK_TAGS: Array<{ id: string; label: string }> = [
  { id: 'did_not_follow_instructions', label: 'Не полностью следовал инструкциям' },
  { id: 'dislike_style', label: 'Не нравится стиль' },
  { id: 'inaccurate', label: 'Неточный / фактические ошибки' },
  { id: 'too_verbose', label: 'Слишком длинный / многословный' },
  { id: 'too_short', label: 'Слишком короткий / неполный' },
  { id: 'irrelevant', label: 'Нерелевантный ответ' },
  { id: 'biased', label: 'Пристрастный' },
  { id: 'safety_or_legal', label: 'Вопросы безопасности или правовых рисков' },
  { id: 'other', label: 'Другое' },
];
