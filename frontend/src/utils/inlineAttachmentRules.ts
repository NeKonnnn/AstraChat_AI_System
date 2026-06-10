import { formatFileSize } from './inlineImage';

export const INLINE_ATTACH_ALLOWED_TYPES_LABEL =
  'PDF (.pdf), Word (.docx), Excel (.xlsx, .xls), текст (.txt), изображения (.jpg, .jpeg, .png, .webp, .gif)';

/** Лимит для inline-вложений через «+» (фронт и POST /api/documents/attach). */
export const INLINE_ATTACHMENT_MAX_BYTES = 50 * 1024 * 1024;
export const INLINE_ATTACHMENT_MAX_SIZE_MB = 50;

const IMAGE_MIME_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'];
const DOC_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-excel',
  'text/plain',
];

export function getInlineAttachmentExtension(filename: string): string {
  const name = filename || '';
  const dot = name.lastIndexOf('.');
  if (dot <= 0 || dot === name.length - 1) return '';
  return name.slice(dot).toLowerCase();
}

export function isInlineAttachFileAllowed(file: File): boolean {
  const isImage = IMAGE_MIME_TYPES.includes(file.type) || /\.(jpe?g|png|webp|gif)$/i.test(file.name);
  const isDoc = DOC_MIME_TYPES.includes(file.type) || /\.(pdf|docx|xlsx|xls|txt)$/i.test(file.name);
  return isImage || isDoc;
}

export function isInlineAttachFileTooLarge(file: File): boolean {
  return file.size > INLINE_ATTACHMENT_MAX_BYTES;
}

export function isInlineAttachSizeErrorMessage(detail: string): boolean {
  return /размер|size|413|превышает|too large|limit/i.test(detail);
}

export function buildUnsupportedInlineAttachMessage(filename: string): string {
  const ext = getInlineAttachmentExtension(filename);
  const extLabel = ext || 'без расширения';
  return `Данный тип файлов ${extLabel} не поддерживается. Допускаются следующие файлы: ${INLINE_ATTACH_ALLOWED_TYPES_LABEL}.`;
}

export function buildOversizedInlineAttachMessage(filename: string, fileSize?: number): string {
  const sizePart = typeof fileSize === 'number' && fileSize > 0 ? ` (${formatFileSize(fileSize)})` : '';
  return `Размер файла «${filename}»${sizePart} превышает допустимый лимит. Допустимый размер файла — до ${INLINE_ATTACHMENT_MAX_SIZE_MB} МБ.`;
}
