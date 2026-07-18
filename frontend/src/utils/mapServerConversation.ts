import { getApiUrl } from '../config/api';
import type { Chat, Message, MessageFeedback, MultiLLMResponseSlot } from '../contexts/AppContext';
import { normalizeMcpToolCallList } from '../mcp/utils/normalizeToolCall';

function mapFeedbackFromMeta(raw: unknown): MessageFeedback | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const fb = raw as Record<string, unknown>;
  const rating = fb.rating === 'like' || fb.rating === 'dislike' ? fb.rating : null;
  if (!rating) return undefined;
  const tags = Array.isArray(fb.tags) ? fb.tags.map((t) => String(t)) : [];
  const comment = typeof fb.comment === 'string' ? fb.comment : undefined;
  const updatedAt =
    typeof fb.updated_at === 'string'
      ? fb.updated_at
      : typeof fb.updatedAt === 'string'
        ? fb.updatedAt
        : undefined;
  return {
    rating,
    ...(tags.length ? { tags } : {}),
    ...(comment ? { comment } : {}),
    ...(updatedAt ? { updatedAt } : {}),
  };
}

export function mapInlineAttachmentRecords(
  raw: unknown,
): NonNullable<Message['inlineAttachments']> | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;
  const items = raw
    .filter((a): a is Record<string, unknown> => Boolean(a) && typeof a === 'object')
    .map((a) => {
      const contentType = a.contentType === 'image' ? ('image' as const) : ('text' as const);
      const dataUri = a.data_uri ? String(a.data_uri) : undefined;
      const minioObject = a.minio_object ? String(a.minio_object) : undefined;
      const minioBucket = a.minio_bucket ? String(a.minio_bucket) : undefined;
      let preview: string | undefined;
      if (contentType === 'image' && dataUri) {
        preview = dataUri;
      } else if (contentType === 'image' && minioObject && minioBucket) {
        preview = getApiUrl(
          `/api/documents/inline-file?bucket=${encodeURIComponent(minioBucket)}&object=${encodeURIComponent(minioObject)}`,
        );
      }
      return {
        name: String(a.name || 'file'),
        contentType,
        ...(preview ? { preview } : {}),
        ...(typeof a.size === 'number' && a.size > 0 ? { size: a.size } : {}),
      };
    });
  return items.length > 0 ? items : undefined;
}

export function mapServerConversationToChat(conversation: any): Chat {
  const messages: Message[] = Array.isArray(conversation?.messages)
    ? conversation.messages.map((msg: any) => {
        const rawContent = String(msg?.content || '');
        const metadata = msg?.metadata && typeof msg.metadata === 'object' ? msg.metadata : {};
        const reasoningContent = String(
          metadata?.reasoning_content || metadata?.reasoning || '',
        ).trim();
        const hasThinkTag = /<think>/i.test(rawContent);
        const mergedContent =
          reasoningContent && !hasThinkTag
            ? `<think>${reasoningContent}</think>\n\n${rawContent}`
            : rawContent;

        const rawInline = metadata?.inline_attachments;
        const inlineAttachments = mapInlineAttachmentRecords(rawInline);

        const rawImageVariants = metadata?.image_variants;
        const inlineAttachmentVariants = Array.isArray(rawImageVariants)
          ? rawImageVariants
              .map((block: unknown) =>
                block && typeof block === 'object'
                  ? mapInlineAttachmentRecords((block as Record<string, unknown>).inline_attachments)
                  : undefined,
              )
              .filter((v): v is NonNullable<Message['inlineAttachments']> => Boolean(v?.length))
          : undefined;
        const currentImageVariantIndex =
          typeof metadata?.current_image_variant_index === 'number'
            ? metadata.current_image_variant_index
            : undefined;
        const rawAltResponses = Array.isArray(metadata?.alternative_responses)
          ? metadata.alternative_responses.map((v: unknown) => String(v ?? ''))
          : Array.isArray(metadata?.alternativeResponses)
            ? metadata.alternativeResponses.map((v: unknown) => String(v ?? ''))
            : undefined;
        const currentAltIndex =
          typeof metadata?.current_response_index === 'number'
            ? metadata.current_response_index
            : typeof metadata?.currentResponseIndex === 'number'
              ? metadata.currentResponseIndex
              : undefined;

        const mcpToolCalls = normalizeMcpToolCallList(metadata?.mcp_tool_calls);
        const rawMultiResponses = Array.isArray(metadata?.multi_llm_responses)
          ? metadata.multi_llm_responses
          : Array.isArray(metadata?.multiLLMResponses)
            ? metadata.multiLLMResponses
            : [];
        const multiLLMResponses: MultiLLMResponseSlot[] = rawMultiResponses
          .filter((slot: unknown) => slot && typeof slot === 'object')
          .map((slot: Record<string, unknown>) => {
            const rawAlternatives = Array.isArray(slot.alternativeResponses)
              ? slot.alternativeResponses
              : Array.isArray(slot.alternative_responses)
                ? slot.alternative_responses
                : undefined;
            const currentResponseIndexRaw =
              typeof slot.currentResponseIndex === 'number'
                ? slot.currentResponseIndex
                : typeof slot.current_response_index === 'number'
                  ? slot.current_response_index
                  : undefined;
            const slotFeedback = mapFeedbackFromMeta(slot.feedback);
            return {
              model: String(slot.model || 'unknown'),
              content: String(slot.content || ''),
              isStreaming: false,
              error: Boolean(slot.error),
              ...(rawAlternatives
                ? { alternativeResponses: rawAlternatives.map((v: unknown) => String(v ?? '')) }
                : {}),
              ...(typeof currentResponseIndexRaw === 'number'
                ? { currentResponseIndex: currentResponseIndexRaw }
                : {}),
              ...(slotFeedback ? { feedback: slotFeedback } : {}),
            };
          });

        const messageFeedback = mapFeedbackFromMeta(metadata?.feedback);

        return {
          id: String(msg?.message_id || `msg_${Math.random().toString(36).slice(2, 14)}`),
          role: msg?.role === 'assistant' ? 'assistant' : 'user',
          content: mergedContent,
          timestamp: String(msg?.timestamp || new Date().toISOString()),
          isStreaming: false,
          ...(reasoningContent ? { reasoningContent } : {}),
          ...(inlineAttachments?.length ? { inlineAttachments } : {}),
          ...(inlineAttachmentVariants?.length ? { inlineAttachmentVariants } : {}),
          ...(rawAltResponses?.length ? { alternativeResponses: rawAltResponses } : {}),
          ...(typeof currentAltIndex === 'number'
            ? { currentResponseIndex: currentAltIndex }
            : typeof currentImageVariantIndex === 'number'
              ? { currentResponseIndex: currentImageVariantIndex }
              : rawAltResponses && rawAltResponses.length > 1
                ? { currentResponseIndex: rawAltResponses.length - 1 }
                : {}),
          ...(mcpToolCalls.length ? { mcpToolCalls } : {}),
          ...(multiLLMResponses.length ? { multiLLMResponses } : {}),
          ...(messageFeedback ? { feedback: messageFeedback } : {}),
        } as Message;
      })
    : [];

  const firstUserContent =
    messages.find((m) => m.role === 'user')?.content?.slice(0, 60) || 'Новый чат';

  const storedTitle = conversation?.title ? String(conversation.title).trim() : '';

  return {
    id: String(conversation?.conversation_id || Date.now().toString()),
    title: storedTitle || firstUserContent,
    messages,
    createdAt: String(conversation?.created_at || new Date().toISOString()),
    updatedAt: String(conversation?.updated_at || new Date().toISOString()),
    projectId: conversation?.project_id ? String(conversation.project_id) : undefined,
    ...(conversation?.metadata?.hidden_from_sidebar_until_user_message
      ? { hiddenFromSidebarUntilUserMessage: true }
      : {}),
  };
}
