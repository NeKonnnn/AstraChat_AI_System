import { getApiUrl } from '../config/api';
import type { Chat, Message } from '../contexts/AppContext';

export type ImageCreationItem = {
  id: string;
  message_id?: string;
  conversation_id?: string;
  conversation_title?: string;
  prompt?: string;
  name?: string;
  created_at?: string;
  preview_url?: string | null;
  image_gen_preset_label?: string | null;
};

function extractPromptFromContent(content: string): string | undefined {
  const match = content.match(/по запросу:\s*«([^»]+)»/i);
  return match?.[1]?.trim() || undefined;
}

function isGeneratedAssistantImage(msg: Message, att: NonNullable<Message['inlineAttachments']>[number]): boolean {
  if (att.contentType !== 'image' || !att.preview) return false;
  if (att.name?.startsWith('generated_')) return true;
  const content = msg.content || '';
  return content.includes('Сгенерировал изображение') || content.includes('image_generation');
}

export function extractCreationsFromChats(chats: Chat[]): ImageCreationItem[] {
  const items: ImageCreationItem[] = [];
  for (const chat of chats) {
    for (const msg of chat.messages) {
      if (msg.role !== 'assistant') continue;
      const variantLists =
        msg.inlineAttachmentVariants?.length
          ? msg.inlineAttachmentVariants
          : msg.inlineAttachments?.length
            ? [msg.inlineAttachments]
            : [];
      variantLists.forEach((attachments, vidx) => {
        attachments.forEach((att, idx) => {
          if (!isGeneratedAssistantImage(msg, att)) return;
          items.push({
            id: `${msg.id}:${vidx}:${idx}`,
            message_id: msg.id,
            conversation_id: chat.id,
            conversation_title: chat.title,
            prompt: extractPromptFromContent(msg.content) || att.name,
            name: att.name || `generated_${idx + 1}.png`,
            created_at: msg.timestamp,
            preview_url: att.preview || null,
          });
        });
      });
    }
  }
  items.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  return items;
}

export function mergeCreationItems(
  apiItems: ImageCreationItem[],
  localItems: ImageCreationItem[],
): ImageCreationItem[] {
  const preferPreviewUrl = (
    primary?: string | null,
    fallback?: string | null,
  ): string | null | undefined => {
    const candidates = [primary, fallback];
    for (const url of candidates) {
      if (url && (url.startsWith('data:') || url.startsWith('blob:'))) return url;
    }
    return primary || fallback || null;
  };

  const byId = new Map<string, ImageCreationItem>();
  for (const item of apiItems) {
    byId.set(item.id, item);
  }
  for (const item of localItems) {
    const existing = byId.get(item.id);
    if (!existing) {
      byId.set(item.id, item);
      continue;
    }
    byId.set(item.id, {
      ...existing,
      preview_url: preferPreviewUrl(existing.preview_url, item.preview_url) ?? existing.preview_url,
      prompt: existing.prompt || item.prompt,
    });
  }
  const merged = Array.from(byId.values());
  merged.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')));
  return merged;
}

export function resolveCreationPreviewSrc(previewUrl?: string | null): string | null {
  if (!previewUrl) return null;
  if (
    previewUrl.startsWith('data:') ||
    previewUrl.startsWith('blob:') ||
    /^https?:\/\//i.test(previewUrl)
  ) {
    return previewUrl;
  }
  return getApiUrl(previewUrl);
}
