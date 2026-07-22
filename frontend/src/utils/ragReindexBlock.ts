export interface RagReindexStatusPayload {
  memory: { reindexing: boolean };
  project: { reindexing: boolean };
  kb: { reindexing: boolean };
  any_reindexing: boolean;
  agent_has_kb: boolean;
  project_has_documents: boolean;
  message: string;
}

export const RAG_REINDEX_BLOCK_PLACEHOLDER =
  'Идёт перечанковка документов — дождитесь завершения';

export interface RagSendBlockContext {
  libraryEnabled: boolean;
  /** С сервера: в текущем проекте есть документы в project-rag. */
  projectHasDocuments: boolean;
  /** С сервера: у выбранного агента есть KB-документы в сторе. */
  agentHasKb: boolean;
}

/** Блокировать отправку, если перечанковка затрагивает активный для чата RAG-источник. */
export function shouldBlockRagSend(
  status: RagReindexStatusPayload | null | undefined,
  ctx: RagSendBlockContext,
): boolean {
  if (!status) return false;
  if (status.memory?.reindexing && ctx.libraryEnabled) return true;
  if (status.project?.reindexing && ctx.projectHasDocuments) return true;
  if (status.kb?.reindexing && ctx.agentHasKb) return true;
  return false;
}

export function ragReindexBlockMessage(
  status: RagReindexStatusPayload | null | undefined,
): string {
  const msg = status?.message?.trim();
  return msg || RAG_REINDEX_BLOCK_PLACEHOLDER;
}
