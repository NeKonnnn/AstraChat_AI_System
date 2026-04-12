/**
 * Отображаемые русские названия оркестраторных агентов (ответ /api/agent/agents).
 * Совпадают с логикой backend: backend/agents/langgraph_orchestrator.py get_available_tools.
 */
const AGENT_ID_TITLE_RU: Record<string, string> = {
  document_agent: 'Поиск и работа с документами',
  prompt_enhancement_agent: 'Промпты для нейросети',
  system_agent: 'Система и команды',
  summarization_agent: 'Краткие пересказы и саммари',
  general_agent: 'Универсальные инструменты',
};

/** Если agent_id не пришёл — по типичному англ. имени из API. */
const NAME_KEY_TITLE_RU: Record<string, string> = {
  documentagent: 'Поиск и работа с документами',
  promptagent: 'Промпты для нейросети',
  systemagent: 'Система и команды',
  summarizationagent: 'Краткие пересказы и саммари',
  generalagent: 'Универсальные инструменты',
};

/**
 * Короткое русское имя агента по функционалу (для списка «Все агенты»).
 */
export function getOrchestratorAgentTitleRu(agentId: string, apiName: string): string {
  const id = (agentId || '').trim();
  if (id && AGENT_ID_TITLE_RU[id]) return AGENT_ID_TITLE_RU[id];
  const nameKey = (apiName || '').replace(/\s+/g, '').toLowerCase();
  if (nameKey && NAME_KEY_TITLE_RU[nameKey]) return NAME_KEY_TITLE_RU[nameKey];
  return (apiName || 'Агент').trim() || 'Агент';
}
