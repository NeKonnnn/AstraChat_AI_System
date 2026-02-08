"""
LangGraph Orchestrator - главный оркестратор агентной архитектуры
Использует LangGraph StateGraph для планирования и выполнения задач
Все инструменты импортируются из backend/tools/
"""

import logging
import json
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# Импортируем все инструменты из backend/tools
try:
    from backend.tools import get_all_tools, get_tools_info
except ModuleNotFoundError:
    # Если запущено из backend/, используем относительный импорт
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from tools import get_all_tools, get_tools_info

logger = logging.getLogger(__name__)

# ============================================================================
# Утилита для получения правильной версии ask_agent
# ============================================================================

def _get_ask_agent():
    """
    Получить ask_agent_llm_svc для работы через llm-svc без загрузки модели
    """
    try:
        from backend.agent_llm_svc import ask_agent
        logger.debug("[LangGraph] Используется ask_agent из agent_llm_svc")
        return ask_agent
    except ModuleNotFoundError:
        from agent_llm_svc import ask_agent
        logger.debug("[LangGraph] Используется ask_agent_llm_svc (относительный импорт)")
        return ask_agent

# ============================================================================
# Определение состояния оркестратора
# ============================================================================

class OrchestratorState(TypedDict):
    """Состояние LangGraph оркестратора"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_query: str
    plan: Optional[List[Dict[str, Any]]]
    current_step: int
    tool_results: List[Dict[str, Any]]
    final_answer: Optional[str]
    error: Optional[str]
    context: Dict[str, Any]


# ============================================================================
# LangGraph Orchestrator
# ============================================================================

class LangGraphOrchestrator:
    """
    Главный оркестратор на основе LangGraph.
    Управляет планированием и выполнением задач через StateGraph.
    Использует инструменты из backend/tools/
    """
    
    def __init__(self):
        # Загружаем все инструменты из backend/tools
        self.tools = get_all_tools()
        self.tools_info = get_tools_info()
        
        logger.info(f"╔═══════════════════════════════════════════════════════════╗")
        logger.info(f"║  LangGraph Orchestrator - Инициализация                   ║")
        logger.info(f"╠═══════════════════════════════════════════════════════════╣")
        logger.info(f"║  Загружено инструментов: {len(self.tools):<30}            ║")
        logger.info(f"║  Категории:                                               ║")
        for category, count in self.tools_info['categories'].items():
            logger.info(f"║    - {category:<20} {count:<25} ║")
        logger.info(f"╚═══════════════════════════════════════════════════════════╝")
        
        # Создаем словарь инструментов по именам для быстрого доступа
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        
        # Статус активности инструментов (для управления через UI)
        self.tool_status = {tool.name: True for tool in self.tools}
        
        # Статус активности оркестратора (по умолчанию включен)
        self.orchestrator_active = True
        
        # Создаем ToolNode для LangGraph
        self.tool_node = ToolNode(self.tools)
        
        # НЕ используем checkpoint - он блокирует event loop и вызывает проблемы с сериализацией
        self.checkpointer = None
        
        # Создаем граф
        self.graph = self._build_graph()
        self.compiled_graph = None
        
        logger.info("LangGraph Orchestrator успешно инициализирован")
    
    def _build_graph(self) -> StateGraph:
        """Построение StateGraph для оркестрации"""
        
        logger.info("Построение StateGraph...")
        
        # Создаем граф с нашим состоянием
        workflow = StateGraph(OrchestratorState)
        
        # Добавляем узлы
        workflow.add_node("planner", self._plan_task)
        workflow.add_node("executor", self._execute_tools)
        workflow.add_node("aggregator", self._aggregate_results)
        
        # Добавляем ребра
        workflow.add_edge(START, "planner")
        workflow.add_conditional_edges(
            "planner",
            self._should_execute_tools,
            {
                "execute": "executor",
                "direct": "aggregator"
            }
        )
        workflow.add_edge("executor", "aggregator")
        workflow.add_edge("aggregator", END)
        
        logger.info("StateGraph построен: planner -> [executor] -> aggregator")
        
        return workflow
    
    def _get_active_tools_description(self) -> str:
        """Получение описания активных инструментов"""
        active_tools = []
        
        for tool in self.tools:
            if self.tool_status.get(tool.name, True):
                active_tools.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(active_tools)
    
    def _plan_task(self, state: OrchestratorState) -> OrchestratorState:
        """
        Узел планирования: анализирует запрос и создает план выполнения
        """
        try:
            user_query = state.get("user_query", "")
            context = state.get("context", {})
            logger.info(f"\n{'='*70}")
            logger.info(f"[PLANNER] Планирование задачи")
            logger.info(f"[PLANNER] Запрос: {user_query[:100]}...")
            logger.info(f"[PLANNER] Контекст при входе: streaming={context.get('streaming', False)}, has_callback={context.get('stream_callback') is not None}")
            logger.info(f"{'='*70}")
            
            # Получаем список активных инструментов
            active_tool_names = [name for name, active in self.tool_status.items() if active]
            logger.info(f"[PLANNER] Активных инструментов: {len(active_tool_names)}/{len(self.tools)}")
            
            # Получаем информацию о доступных документах из контекста
            doc_processor = context.get("doc_processor")
            available_docs = []
            if doc_processor:
                try:
                    available_docs = doc_processor.get_document_list()
                    logger.info(f"[PLANNER] Доступно документов: {len(available_docs)}")
                    logger.debug(f"[PLANNER] Список документов: {available_docs}")
                except Exception as e:
                    logger.warning(f"[PLANNER] Не удалось получить список документов: {e}")
            
            # Используем LLM для анализа и планирования
            ask_agent = _get_ask_agent()
            
            tools_description = self._get_active_tools_description()
            
            # Логируем доступные инструменты для отладки
            logger.info(f"[PLANNER] Описание инструментов (длина: {len(tools_description)} символов):")
            logger.debug(f"[PLANNER] Полное описание инструментов:\n{tools_description}")
            
            # Формируем контекстную информацию о документах
            docs_context = ""
            if available_docs:
                docs_context = f"""
ДОСТУПНЫЕ ДОКУМЕНТЫ:
- Загружено документов: {len(available_docs)}
- Названия: {', '.join(available_docs[:3])}{'...' if len(available_docs) > 3 else ''}

Если запрос касается анализа документов, поиска информации в файлах или подсчета элементов в документах, используй инструмент 'search_documents' с соответствующим поисковым запросом.
"""
            
            planning_prompt = f"""Ты - система планирования задач AI-ассистента. Твоя задача - определить, какие инструменты нужны для выполнения запроса пользователя.

ВАЖНЫЕ ПРАВИЛА:
1. ВСЕГДА используй инструменты, если запрос требует:
   - Поиска информации (в документах, в интернете)
   - Вычислений или расчетов
   - Создания, улучшения или анализа промптов
   - Работы с файлами или документами
   - Сохранения информации в память
   - Любых специальных действий, которые выходят за рамки простого разговора

2. Используй прямой ответ БЕЗ инструментов ТОЛЬКО для:
   - Простых приветствий ("Привет", "Как дела?")
   - Общих вопросов о том, как работает система
   - Простых разговорных фраз без конкретной задачи

{docs_context}

Доступные инструменты:
{tools_description}

Запрос пользователя: "{user_query}"

Проанализируй запрос и определи:
1. Нужны ли специальные инструменты для выполнения задачи?
2. Если да, какие инструменты и в каком порядке нужно использовать?

Ответь СТРОГО в формате JSON:
{{
    "needs_tools": true/false,
    "plan": [
        {{"tool": "название_инструмента", "input": "что передать инструменту"}},
        ...
    ],
    "reasoning": "краткое объяснение"
}}

Примеры:

1. Запрос: "Найди информацию о Python в документах"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "search_documents", "input": "Python"}}
    ],
    "reasoning": "Нужен поиск в документах"
}}

2. Запрос: "Сколько всего идей в файле? Назови первые 3 из них!"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "search_documents", "input": "идеи"}}
    ],
    "reasoning": "Нужен поиск идей в документах"
}}

3. Запрос: "Какая погода в Москве?"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "web_search", "input": "погода в Москве"}}
    ],
    "reasoning": "Нужна актуальная информация из интернета"
}}

4. Запрос: "Посчитай 15 * 7 + 3"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "calculate", "input": "15 * 7 + 3"}}
    ],
    "reasoning": "Нужно математическое вычисление"
}}

5. Запрос: "Привет, как дела?"
{{
    "needs_tools": false,
    "plan": [],
    "reasoning": "Простой разговорный запрос, не требует инструментов"
}}

6. Запрос: "Напиши мне промпт для создания статьи"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "enhance_prompt", "input": "создание статьи"}}
    ],
    "reasoning": "Нужно создать промпт - используем инструмент enhance_prompt"
}}

7. Запрос: "Создай промпт для анализа данных"
{{
    "needs_tools": true,
    "plan": [
        {{"tool": "enhance_prompt", "input": "анализ данных"}}
    ],
    "reasoning": "Запрос на создание промпта требует использования инструмента"
}}

ПОМНИ: Если запрос содержит слова "промпт", "создай", "напиши промпт", "улучши промпт" - ВСЕГДА используй инструменты!

Твой ответ (ТОЛЬКО JSON):"""
            
            # Логируем запрос
            logger.info(f"[PLANNER] Запрос пользователя: {user_query}")
            logger.info(f"[PLANNER] Доступно инструментов: {len(self.tools_info['tools'])}")
            logger.debug(f"[PLANNER] Список инструментов: {[t['name'] for t in self.tools_info['tools']]}")
            
            # Получаем ответ от LLM
            logger.info(f"[PLANNER] Отправляем запрос к LLM для планирования...")
            response = ask_agent(
                planning_prompt,
                history=[],
                streaming=False,
                max_tokens=500,
                model_path=state.get("context", {}).get("selected_model")
            )
            
            logger.info(f"[PLANNER] Получен ответ от LLM (длина: {len(response) if response else 0} символов)")
            logger.debug(f"[PLANNER] Полный ответ LLM: {response}")
            
            # Проверяем, что ответ не пустой и не является ошибкой
            if not response or response is None:
                logger.error(f"[PLANNER] Ответ LLM пустой или None")
                state["plan"] = []
                state["current_step"] = 0
                state["tool_results"] = []
                state["context"] = context
                return state
            
            # Проверяем, не является ли ответ сообщением об ошибке
            if "Извините" in response or "Ошибка" in response or "превышено время" in response:
                logger.error(f"[PLANNER] LLM вернул ошибку: {response[:200]}")
                state["plan"] = []
                state["current_step"] = 0
                state["tool_results"] = []
                state["context"] = context
                state["error"] = response
                return state
            
            # Парсим JSON ответ
            try:
                # Убираем markdown форматирование если есть
                logger.info(f"[PLANNER] Парсинг ответа LLM...")
                response_clean = response.strip()
                if response_clean.startswith("```"):
                    logger.debug(f"[PLANNER] Обнаружен markdown, удаляем...")
                    response_clean = response_clean.split("```")[1]
                    if response_clean.startswith("json"):
                        response_clean = response_clean[4:]
                response_clean = response_clean.strip()
                
                logger.debug(f"[PLANNER] Очищенный JSON: {response_clean[:200]}...")
                plan_data = json.loads(response_clean)
                
                needs_tools = plan_data.get("needs_tools", False)
                plan = plan_data.get("plan", [])
                reasoning = plan_data.get("reasoning", "")
                
                # ВАЛИДАЦИЯ: Если есть план, но needs_tools=False - исправляем
                if plan and len(plan) > 0 and not needs_tools:
                    logger.warning(f"[PLANNER] ОШИБКА ЛОГИКИ: есть план из {len(plan)} инструментов, но needs_tools=False. Исправляем на True.")
                    needs_tools = True
                
                # ВАЛИДАЦИЯ: Если needs_tools=True, но план пустой - исправляем
                if needs_tools and (not plan or len(plan) == 0):
                    logger.warning(f"[PLANNER] ОШИБКА ЛОГИКИ: needs_tools=True, но план пустой. Исправляем на False.")
                    needs_tools = False
                    reasoning = "План пустой, используем прямой ответ"
                
                logger.info(f"[PLANNER] После валидации: needs_tools={needs_tools}, plan_length={len(plan) if plan else 0}")
                
                # Подробное логирование выбора агента/инструмента
                logger.info(f"\n{'='*70}")
                logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                logger.info(f"║  ОРКЕСТРАТОР: РЕШЕНИЕ ПРИНЯТО                             ║")
                logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                logger.info(f"║  Запрос пользователя: {user_query[:60]:<60}               ║")
                logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                logger.info(f"║  РЕШЕНИЕ: {'Использовать инструменты' if needs_tools else 'Прямой ответ без инструментов':<50} ║")
                logger.info(f"║  ОБОСНОВАНИЕ: {reasoning[:50]:<50} ║")
                logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                
                if plan:
                    logger.info(f"║  ВЫБРАННЫЕ ИНСТРУМЕНТЫ/АГЕНТЫ: {len(plan)} шт.            ║")
                    logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                    for i, step in enumerate(plan, 1):
                        if not step:
                            logger.warning(f"║  Шаг {i}: ПУСТОЙ (None)                                    ║")
                            continue
                        tool_name = step.get('tool', 'UNKNOWN') if isinstance(step, dict) else 'UNKNOWN'
                        tool_input = step.get('input', '') if isinstance(step, dict) else ''
                        tool_input_str = str(tool_input)[:50] if tool_input else 'пусто'
                        
                        # Определяем тип агента по имени инструмента
                        agent_type = "Неизвестный"
                        if 'summarize' in tool_name.lower() or 'extract_key' in tool_name.lower() or 'bullet' in tool_name.lower():
                            agent_type = "SummarizationAgent (Агент суммаризации)"
                        elif 'prompt' in tool_name.lower() or 'enhance' in tool_name.lower() or 'analyze' in tool_name.lower():
                            agent_type = "PromptEnhancementAgent (Агент улучшения промптов)"
                        elif 'document' in tool_name.lower() or 'search_documents' in tool_name.lower():
                            agent_type = "DocumentAgent (Агент работы с документами)"
                        elif 'web_search' in tool_name.lower() or 'search_web' in tool_name.lower():
                            agent_type = "WebSearchAgent (Агент веб-поиска)"
                        elif 'calculate' in tool_name.lower():
                            agent_type = "CalculationAgent (Агент вычислений)"
                        elif 'memory' in tool_name.lower() or 'save_memory' in tool_name.lower():
                            agent_type = "MemoryAgent (Агент памяти)"
                        elif 'mcp' in tool_name.lower():
                            agent_type = "🔌 MCPAgent (MCP агент)"
                        
                        logger.info(f"║  {i}. {agent_type:<55} ║")
                        logger.info(f"║     └─ 🔧 Инструмент: '{tool_name}'")
                        logger.info(f"║     └─ 📥 Входные данные: {tool_input_str}...")
                        if i < len(plan):
                            logger.info(f"║")
                else:
                    logger.info(f"║  РЕЖИМ: Прямой ответ LLM (без агентов)                    ║")
                    logger.info(f"║  ПРИЧИНА: {reasoning[:50]:<50} ║")
                
                logger.info(f"╚═══════════════════════════════════════════════════════════╝")
                logger.info(f"{'='*70}\n")
                
                state["plan"] = plan if needs_tools else []
                state["current_step"] = 0
                state["tool_results"] = []
                # Явно сохраняем context обратно в state
                state["context"] = context
                
                logger.info(f"[PLANNER] Контекст при выходе: streaming={context.get('streaming', False)}")
                
            except json.JSONDecodeError as e:
                logger.error(f"[PLANNER] Ошибка парсинга JSON: {e}")
                logger.error(f"[PLANNER] Ответ LLM: {response}")
                # Fallback: считаем что инструменты не нужны
                state["plan"] = []
                state["current_step"] = 0
                state["tool_results"] = []
                # Сохраняем context даже при ошибке
                state["context"] = context
            
            return state
            
        except Exception as e:
            logger.error(f"[PLANNER] Ошибка планирования: {e}")
            import traceback
            logger.error(traceback.format_exc())
            state["error"] = f"Ошибка планирования: {str(e)}"
            state["plan"] = []
            # Сохраняем context даже при критической ошибке
            state["context"] = state.get("context", {})
            return state
    
    def _should_execute_tools(self, state: OrchestratorState) -> str:
        """Условное ребро: определяет нужно ли выполнять инструменты"""
        plan = state.get("plan", [])
        context = state.get("context", {})
        
        logger.info(f"[ROUTER] Проверка context: streaming={context.get('streaming', False)}, has_callback={context.get('stream_callback') is not None}")
        
        if plan and len(plan) > 0:
            logger.info(f"[ROUTER] Переход к выполнению инструментов ({len(plan)} шагов)")
            return "execute"
        else:
            logger.info(f"[ROUTER] Прямой переход к ответу (инструменты не нужны)")
            return "direct"
    
    def _execute_tools(self, state: OrchestratorState) -> OrchestratorState:
        """
        Узел выполнения: последовательно выполняет инструменты из плана
        """
        try:
            plan = state.get("plan", [])
            tool_results = state.get("tool_results", [])
            context = state.get("context", {})
            socket_id = context.get("socket_id")
            
            # Получаем sio из tool_context (не из state, так как sio не сериализуется)
            try:
                from backend.tools.prompt_tools import set_tool_context, get_tool_context
            except ModuleNotFoundError:
                from tools.prompt_tools import set_tool_context, get_tool_context
            
            # Получаем расширенный контекст с несериализуемыми объектами
            extended_context = get_tool_context()
            sio = extended_context.get("sio")
            
            logger.info(f"[EXECUTOR] Контекст перед установкой: streaming={context.get('streaming', False)}, has_callback={context.get('stream_callback') is not None}")
            
            # Объединяем контексты - context из state + extended_context из tool_context
            merged_context = {**extended_context, **context}
            set_tool_context(merged_context)
            logger.info(f"[EXECUTOR] Установлен контекст для инструментов")
            
            logger.info(f"\n{'='*70}")
            logger.info(f"[EXECUTOR] Выполнение инструментов")
            logger.info(f"[EXECUTOR] Всего шагов: {len(plan)}")
            logger.info(f"{'='*70}")
            
            for i, step in enumerate(plan, 1):
                tool_name = step.get("tool") if step else None
                tool_input = step.get("input") if step else ""
                
                # Проверяем, что step не None
                if not step or not tool_name:
                    logger.error(f"[EXECUTOR] Шаг {i} некорректен: step={step}")
                    tool_results.append({
                        "tool": "unknown",
                        "input": "",
                        "output": f"Ошибка: некорректный шаг плана {i}",
                        "success": False
                    })
                    continue
                
                # Определяем тип агента по имени инструмента
                agent_type = "Неизвестный агент"
                if 'summarize' in tool_name.lower() or 'extract_key' in tool_name.lower() or 'bullet' in tool_name.lower():
                    agent_type = "SummarizationAgent (Агент суммаризации)"
                elif 'prompt' in tool_name.lower() or 'enhance' in tool_name.lower() or 'analyze' in tool_name.lower():
                    agent_type = "PromptEnhancementAgent (Агент улучшения промптов)"
                elif 'document' in tool_name.lower() or 'search_documents' in tool_name.lower():
                    agent_type = "DocumentAgent (Агент работы с документами)"
                elif 'web_search' in tool_name.lower() or 'search_web' in tool_name.lower():
                    agent_type = "WebSearchAgent (Агент веб-поиска)"
                elif 'calculate' in tool_name.lower():
                    agent_type = "CalculationAgent (Агент вычислений)"
                elif 'memory' in tool_name.lower() or 'save_memory' in tool_name.lower():
                    agent_type = "MemoryAgent (Агент памяти)"
                elif 'mcp' in tool_name.lower():
                    agent_type = "MCPAgent (MCP агент)"
                
                logger.info(f"\n{'='*70}")
                logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                logger.info(f"║  ВЫПОЛНЕНИЕ: Шаг {i}/{len(plan)}                          ║")
                logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                logger.info(f"║  АГЕНТ: {agent_type:<50} ║")
                logger.info(f"║  ИНСТРУМЕНТ: '{tool_name}'")
                logger.info(f"║  ВХОДНЫЕ ДАННЫЕ: {str(tool_input)[:50] if tool_input else 'пусто'}...")
                logger.info(f"╚═══════════════════════════════════════════════════════════╝")
                logger.info(f"{'='*70}")
                
                # Отправляем heartbeat для каждого инструмента
                # Не используем asyncio.create_task в синхронном контексте
                # Вместо этого логируем - события будут отправлены из async контекста в main.py
                if sio and socket_id:
                    logger.info(f"[EXECUTOR] Heartbeat: Выполняю инструмент {tool_name} ({i}/{len(plan)})...")
                    # События отправляются из async контекста в main.py через chat_thinking
                
                # Проверяем что инструмент активен
                logger.debug(f"[EXECUTOR] Проверка статуса инструмента '{tool_name}'...")
                is_active = self.tool_status.get(tool_name, False)
                logger.debug(f"[EXECUTOR] Статус инструмента '{tool_name}': {'активен' if is_active else 'неактивен'}")
                
                if not is_active:
                    logger.warning(f"[EXECUTOR] Инструмент '{tool_name}' неактивен, пропускаем")
                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": f"Инструмент '{tool_name}' неактивен",
                        "success": False
                    })
                    continue
                
                # Получаем инструмент
                logger.debug(f"[EXECUTOR] Поиск инструмента '{tool_name}' в словаре...")
                logger.debug(f"[EXECUTOR] Доступные инструменты: {list(self.tools_by_name.keys())}")
                tool = self.tools_by_name.get(tool_name)
                if not tool:
                    logger.error(f"[EXECUTOR] Инструмент '{tool_name}' не найден в словаре!")
                    logger.error(f"[EXECUTOR] Возможно опечатка? Похожие: {[t for t in self.tools_by_name.keys() if tool_name.lower() in t.lower() or t.lower() in tool_name.lower()]}")
                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": f"Инструмент '{tool_name}' не найден",
                        "success": False
                    })
                    continue
                
                logger.info(f"[EXECUTOR] Инструмент найден, запускаем...")
                
                # Выполняем инструмент
                try:
                    # Для инструментов агентов передаем контекст
                    if tool_name in ["search_documents", "web_search", "calculate", "save_memory"]:
                        # Эти инструменты используют агентов, которые могут нуждаться в контексте
                        result = tool.func(tool_input)
                    else:
                        # Обычные инструменты
                        result = tool.func(tool_input)
                    
                    logger.info(f"[EXECUTOR] Результат: {str(result)[:200]}...")
                    
                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": result,
                        "success": True
                    })
                    
                    logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                    logger.info(f"║  ШАГ {i}/{len(plan)} ЗАВЕРШЕН УСПЕШНО                     ║")
                    logger.info(f"║  Результат: {len(str(result))} символов")
                    logger.info(f"╚═══════════════════════════════════════════════════════════╝\n")
                    
                except Exception as e:
                    logger.error(f"[EXECUTOR] Ошибка выполнения '{tool_name}': {e}")
                    tool_results.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": f"Ошибка: {str(e)}",
                        "success": False
                    })
            
            state["tool_results"] = tool_results
            logger.info(f"[EXECUTOR] Выполнено {len(tool_results)} инструментов")
            
            return state
            
        except Exception as e:
            logger.error(f"[EXECUTOR] Критическая ошибка: {e}")
            import traceback
            logger.error(traceback.format_exc())
            state["error"] = f"Ошибка выполнения инструментов: {str(e)}"
            return state
    
    def _aggregate_results(self, state: OrchestratorState) -> OrchestratorState:
        """
        Узел агрегации: формирует финальный ответ на основе результатов
        """
        try:
            user_query = state.get("user_query", "")
            tool_results = state.get("tool_results", [])
            context = state.get("context", {})
            socket_id = context.get("socket_id")
            
            # Получаем sio из tool_context (не из state, так как sio не сериализуется)
            try:
                from backend.tools.prompt_tools import get_tool_context
            except ModuleNotFoundError:
                from tools.prompt_tools import get_tool_context
            
            extended_context = get_tool_context()
            sio = extended_context.get("sio")
            streaming = context.get("streaming", False)
            # Получаем stream_callback из extended_context (не из context!)
            stream_callback_async = extended_context.get("stream_callback")
            
            logger.info(f"\n{'='*70}")
            logger.info(f"[AGGREGATOR] Формирование финального ответа")
            logger.info(f"[AGGREGATOR] Результатов инструментов: {len(tool_results)}")
            logger.info(f"[AGGREGATOR] Стриминг: {'включен' if streaming else 'выключен'}")
            logger.info(f"[AGGREGATOR] Stream callback: {'есть' if stream_callback_async else 'нет'}")
            logger.info(f"{'='*70}")
            
            # Отправляем heartbeat если есть socket
            # Не используем asyncio.create_task в синхронном контексте
            if sio and socket_id:
                logger.info(f"[AGGREGATOR] Heartbeat: Формирую финальный ответ...")
                # События отправляются из async контекста в main.py через chat_thinking
            
            ask_agent = _get_ask_agent()
            
            # Создаем синхронный wrapper для async callback
            stream_callback_sync = None
            if streaming and stream_callback_async:
                import asyncio
                
                def sync_wrapper(chunk: str, accumulated: str):
                    try:
                        # Получаем текущий event loop
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            logger.warning("Нет активного event loop для stream callback")
                            return True
                        
                        if loop.is_running():
                            # Если loop запущен, используем run_coroutine_threadsafe
                            future = asyncio.run_coroutine_threadsafe(
                                stream_callback_async(chunk, accumulated),
                                loop
                            )
                            # Не ждем результат - просто запускаем в фоне
                        else:
                            # Если loop не запущен, используем run_until_complete
                            loop.run_until_complete(stream_callback_async(chunk, accumulated))
                        return True
                    except asyncio.CancelledError:
                        logger.warning("Stream callback был отменен")
                        return False  # Прекращаем генерацию
                    except Exception as e:
                        logger.error(f"Ошибка в stream callback: {e}")
                        return True
                
                stream_callback_sync = sync_wrapper
            
            # Если инструменты не использовались, даем прямой ответ
            if not tool_results:
                logger.info(f"\n{'='*70}")
                logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                logger.info(f"║  ФИНАЛЬНОЕ РЕШЕНИЕ ОРКЕСТРАТОРА                           ║")
                logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                logger.info(f"║  ИСПОЛЬЗОВАН: Прямой ответ LLM (без агентов)              ║")
                logger.info(f"║  РЕШЕНИЕ: Инструменты не требуются, отвечаю напрямую")
                logger.info(f"║  СТРИМИНГ: {'включен' if streaming else 'выключен'}")
                logger.info(f"╚═══════════════════════════════════════════════════════════╝")
                logger.info(f"{'='*70}\n")
                
                if sio and socket_id:
                    logger.info(f"[AGGREGATOR] Heartbeat: Генерирую ответ...")
                    # События отправляются из async контекста в main.py через chat_thinking
                
                final_answer = ask_agent(
                    user_query,
                    history=context.get("history", []),
                    streaming=streaming,
                    stream_callback=stream_callback_sync if streaming else None,
                    model_path=context.get("selected_model")
                )
                
                # Проверяем, не была ли генерация отменена
                if final_answer is None:
                    logger.warning(f"[AGGREGATOR] Генерация была отменена пользователем")
                    state["final_answer"] = ""  # Пустой ответ при отмене
                    state["error"] = "Генерация была отменена пользователем"
                    return state
                
                state["final_answer"] = final_answer
                logger.info(f"[AGGREGATOR] Ответ сформирован: {len(final_answer)} символов")
                logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                logger.info(f"║  ГЕНЕРАЦИЯ ЗАВЕРШЕНА: {len(final_answer)} символов")
                logger.info(f"╚═══════════════════════════════════════════════════════════╝\n")
                return state
            
            # Проверяем, являются ли результаты инструментов уже готовыми финальными ответами
            # Инструменты, которые возвращают готовые ответы (не требуют дополнительной агрегации)
            final_answer_tools = {
                'enhance_prompt',
                'improve_existing_prompt', 
                'analyze_prompt',
                'summarize_text',
                'summarize_document', 
                'extract_key_points',        
                'create_bullet_summary',     
                'summarize_conversation',   
                'text_summarization' 
            }
            
            # Если есть только один успешный результат от инструмента, который возвращает готовый ответ
            successful_results = [r for r in tool_results if r.get("success", False)]
            if len(successful_results) == 1:
                tool_name = successful_results[0].get("tool", "")
                output = successful_results[0].get("output", "")
                
                # Проверяем, является ли это инструментом, который возвращает готовый ответ
                if tool_name in final_answer_tools and len(output) > 50:
                    # Определяем тип агента
                    agent_type = "Неизвестный агент"
                    if 'summarize' in tool_name.lower() or 'extract_key' in tool_name.lower() or 'bullet' in tool_name.lower():
                        agent_type = "SummarizationAgent"
                    elif 'prompt' in tool_name.lower() or 'enhance' in tool_name.lower() or 'analyze' in tool_name.lower():
                        agent_type = "PromptEnhancementAgent"
                    
                    logger.info(f"\n{'='*70}")
                    logger.info(f"╔═══════════════════════════════════════════════════════════╗")
                    logger.info(f"║  ФИНАЛЬНОЕ РЕШЕНИЕ ОРКЕСТРАТОРА                           ║")
                    logger.info(f"╠═══════════════════════════════════════════════════════════╣")
                    logger.info(f"║  ИСПОЛЬЗОВАН: {agent_type:<50} ║")
                    logger.info(f"║  ИНСТРУМЕНТ: '{tool_name}'")
                    logger.info(f"║  РЕЗУЛЬТАТ: {len(output)} символов")
                    logger.info(f"║  РЕШЕНИЕ: Агент вернул готовый ответ, используем его напрямую")
                    logger.info(f"╚═══════════════════════════════════════════════════════════╝")
                    logger.info(f"{'='*70}\n")
                    
                    state["final_answer"] = output
                    return state
            
            # Формируем контекст из результатов инструментов
            context_parts = []
            for result in tool_results:
                tool_name = result.get("tool")
                output = result.get("output")
                success = result.get("success")
                
                if success:
                    context_parts.append(f"Результат инструмента '{tool_name}':\n{output}\n")
                else:
                    context_parts.append(f"Инструмент '{tool_name}' завершился с ошибкой: {output}\n")
            
            context_str = "\n".join(context_parts)
            
            aggregation_prompt = f"""На основе результатов выполнения инструментов, сформируй полный и понятный ответ на запрос пользователя.

Запрос пользователя: "{user_query}"

Результаты инструментов:
{context_str}

Сформируй связный ответ, используя предоставленную информацию. Если были ошибки, упомяни о них.

Твой ответ:"""
            
            if sio and socket_id:
                logger.info(f"[AGGREGATOR] Heartbeat: Генерирую финальный ответ на основе результатов...")
                # События отправляются из async контекста в main.py через chat_thinking
            
            logger.info(f"\n{'='*70}")
            logger.info(f"╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"║  ФИНАЛЬНОЕ РЕШЕНИЕ ОРКЕСТРАТОРА                           ║")
            logger.info(f"╠═══════════════════════════════════════════════════════════╣")
            logger.info(f"║  ИСПОЛЬЗОВАН: LangGraph Aggregator (Агрегатор)            ║")
            logger.info(f"║  РЕЗУЛЬТАТОВ ИНСТРУМЕНТОВ: {len(tool_results)}")
            logger.info(f"║  РЕШЕНИЕ: Агрегирую результаты всех инструментов")
            logger.info(f"║  СТРИМИНГ: {'включен' if streaming else 'выключен'}")
            logger.info(f"╚═══════════════════════════════════════════════════════════╝")
            logger.info(f"{'='*70}\n")
            
            final_answer = ask_agent(
                aggregation_prompt,
                history=[],
                streaming=streaming,
                stream_callback=stream_callback_sync if streaming else None,
                model_path=context.get("selected_model")
            )
            
            # Проверяем, не была ли генерация отменена
            if final_answer is None:
                logger.warning(f"[AGGREGATOR] Генерация была отменена пользователем")
                state["final_answer"] = ""  # Пустой ответ при отмене
                state["error"] = "Генерация была отменена пользователем"
                return state
            
            state["final_answer"] = final_answer
            logger.info(f"[AGGREGATOR] Финальный ответ сформирован: {len(final_answer)} символов")
            logger.info(f"╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"║  АГРЕГАЦИЯ ЗАВЕРШЕНА: {len(final_answer)} символов")
            logger.info(f"╚═══════════════════════════════════════════════════════════╝\n")
            
            return state
            
        except Exception as e:
            logger.error(f"[AGGREGATOR] Ошибка агрегации: {e}")
            import traceback
            logger.error(traceback.format_exc())
            state["error"] = f"Ошибка формирования ответа: {str(e)}"
            return state
    
    async def process_message(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Основной метод для обработки сообщений через LangGraph
        
        Args:
            message: Сообщение пользователя
            history: История диалога
            context: Дополнительный контекст (doc_processor, selected_model и т.д.)
            
        Returns:
            Ответ системы
        """
        try:
            logger.info("="*70)
            logger.info("╔═══════════════════════════════════════════════════════════╗")
            logger.info("║  LANGGRAPH ORCHESTRATOR - НАЧАЛО ОБРАБОТКИ                ║")
            logger.info("╠═══════════════════════════════════════════════════════════╣")
            logger.info(f"║  Запрос пользователя: {message[:60]:<60} ║")
            logger.info(f"║  История: {len(history) if history else 0} сообщений")
            streaming_status = 'включен' if (context and context.get('streaming', False)) else 'выключен'
            logger.info(f"║  Стриминг: {streaming_status}")
            logger.info("╠═══════════════════════════════════════════════════════════╣")
            logger.info("║  ОРКЕСТРАТОР АНАЛИЗИРУЕТ ЗАПРОС И ВЫБИРАЕТ АГЕНТОВ        ║")
            logger.info("╚═══════════════════════════════════════════════════════════╝")
            logger.info("="*70)
            
            # Компилируем граф если еще не скомпилирован
            logger.info("[process_message] Проверка compiled_graph...")
            if self.compiled_graph is None:
                logger.info("[process_message] Граф не скомпилирован, начинаем компиляцию...")
                self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
                logger.info("[process_message] Граф скомпилирован успешно")
            else:
                logger.info("[process_message] Граф уже скомпилирован, используем существующий")
            
            # Начальное состояние
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "user_query": message,
                "plan": None,
                "current_step": 0,
                "tool_results": [],
                "final_answer": None,
                "error": None,
                "context": context or {}
            }
            
            # Запускаем граф
            logger.info("[process_message] Подготовка конфигурации для запуска графа...")
            config = {"configurable": {"thread_id": "default"}}
            logger.info("[process_message] Запуск compiled_graph.invoke...")
            
            # invoke - синхронный метод, но внутри вызываются асинхронные функции
            # Нужно создать event loop в отдельном потоке для асинхронных операций
            import asyncio
            import concurrent.futures
            import threading
            
            def run_invoke_with_loop():
                """Запускает invoke в новом event loop в отдельном потоке"""
                # ИСПРАВЛЕНИЕ: Не создаем новый loop - invoke синхронный и не нужен loop
                try:
                    logger.info("[process_message/Thread] Запуск invoke (синхронный метод)...")
                    logger.info("[process_message/Thread] initial_state keys: " + str(list(initial_state.keys())))
                    logger.info("[process_message/Thread] user_query: " + str(initial_state.get("user_query", "")[:100]))
                    
                    # Запускаем invoke - это синхронный метод LangGraph
                    result = self.compiled_graph.invoke(initial_state, config)
                    
                    logger.info("[process_message/Thread] ✓ invoke завершен успешно")
                    logger.info("[process_message/Thread] result keys: " + str(list(result.keys()) if isinstance(result, dict) else "не dict"))
                    logger.info("[process_message/Thread] final_answer длина: " + str(len(result.get("final_answer", "")) if isinstance(result, dict) else 0))
                    
                    return result
                except Exception as e:
                    logger.error(f"[process_message/Thread] Ошибка в invoke: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Возвращаем состояние с ошибкой вместо raise
                    return {
                        "error": str(e),
                        "final_answer": None,
                        "user_query": initial_state.get("user_query", ""),
                        "context": initial_state.get("context", {})
                    }
            
            # Запускаем в отдельном потоке с новым event loop
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                logger.info("[process_message] Запуск invoke в ThreadPoolExecutor с новым event loop...")
                try:
                    # ИСПРАВЛЕНИЕ: Добавляем таймаут для предотвращения зависания
                    future = loop.run_in_executor(executor, run_invoke_with_loop)
                    final_state = await asyncio.wait_for(future, timeout=300.0)  # 5 минут таймаут
                    logger.info("[process_message] compiled_graph.invoke завершен, получен final_state")
                except asyncio.TimeoutError:
                    logger.error("[process_message] TIMEOUT: Граф не завершился за 300 секунд")
                    return "Извините, обработка запроса заняла слишком много времени. Попробуйте упростить запрос."
                except Exception as e:
                    logger.error(f"[process_message] Ошибка при выполнении графа: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return f"Произошла ошибка при обработке запроса: {str(e)}"
            
            # Проверяем результат
            logger.info("[process_message] Проверка результата графа...")
            logger.info(f"[process_message] final_state type: {type(final_state)}")
            logger.info(f"[process_message] final_state keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'не dict'}")
            
            if final_state.get("error"):
                error_msg = final_state["error"]
                logger.error(f"[process_message] Ошибка выполнения: {error_msg}")
                return f"Произошла ошибка: {error_msg}"
            
            final_answer = final_state.get("final_answer")
            logger.info(f"[process_message] final_answer: {'есть' if final_answer else 'НЕТ'}, длина: {len(final_answer) if final_answer else 0}")
            
            if final_answer:
                logger.info("="*70)
                logger.info("╔═══════════════════════════════════════════════════════════╗")
                logger.info("║ЗАДАЧА УСПЕШНО ВЫПОЛНЕНА                                   ║")
                logger.info(f"║Ответ: {len(final_answer)} символов")
                logger.info(f"║Первые 200 символов: {final_answer[:200]}...")
                logger.info("╚═══════════════════════════════════════════════════════════╝")
                logger.info("="*70)
                return final_answer
            else:
                logger.warning("="*70)
                logger.warning("╔═══════════════════════════════════════════════════════════╗")
                logger.warning("║ФИНАЛЬНЫЙ ОТВЕТ НЕ СФОРМИРОВАН                             ║")
                logger.warning(f"║  final_state keys: {list(final_state.keys())}")
                logger.warning(f"║  tool_results: {len(final_state.get('tool_results', []))}")
                logger.warning("╚═══════════════════════════════════════════════════════════╝")
                logger.warning("="*70)
                return "Не удалось получить ответ на ваш запрос."
                
        except Exception as e:
            logger.error(f"Критическая ошибка в process_message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Произошла критическая ошибка: {str(e)}"
    
    # ========================================================================
    # Методы управления инструментами (для UI)
    # ========================================================================
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Получение списка всех доступных агентов с инструкциями по использованию инструментов
        Возвращает структуру совместимую с фронтендом
        """
        # Группируем инструменты по категориям (агентам) на основе их имен
        agents_map = {}
        
        # Проходим по всем загруженным инструментам и группируем их
        for tool in self.tools:
            tool_name = tool.name
            
            # Определяем категорию агента на основе имени инструмента
            if "search_documents" in tool_name or "document" in tool_name.lower():
                agent_id = "document_agent"
                agent_name = "DocumentAgent"
                description = "Поиск и анализ информации в загруженных документах"
                capabilities = ["search_documents"]
                usage_examples = [
                    "Найди информацию о Python в документах",
                    "Поищи данные о машинном обучении",
                    "Найди все упоминания алгоритмов"
                ]
            elif "web_search" in tool_name or "search_web" in tool_name:
                agent_id = "web_search_agent"
                agent_name = "WebSearchAgent"
                description = "Поиск информации в интернете"
                capabilities = ["web_search"]
                usage_examples = [
                    "Какая погода в Москве?",
                    "Найди последние новости о ИИ",
                    "Какой курс доллара сегодня?"
                ]
            elif "calculate" in tool_name or "calculation" in tool_name.lower():
                agent_id = "calculation_agent"
                agent_name = "CalculationAgent"
                description = "Выполнение математических вычислений"
                capabilities = ["calculate"]
                usage_examples = [
                    "Посчитай 15 * 7 + 3",
                    "Вычисли квадратный корень из 144",
                    "Найди площадь круга с радиусом 5"
                ]
            elif "memory" in tool_name.lower() or "save_memory" in tool_name:
                agent_id = "memory_agent"
                agent_name = "MemoryAgent"
                description = "Сохранение важной информации в долговременную память"
                capabilities = ["save_memory"]
                usage_examples = [
                    "Запомни, что я работаю программистом",
                    "Сохрани информацию о моих предпочтениях",
                    "Запиши важные факты о проекте"
                ]
            elif ("prompt" in tool_name.lower() and "file" not in tool_name.lower() and "system" not in tool_name.lower()) or \
                 "prompt_engineering" in tool_name or \
                 "enhance_prompt" in tool_name or \
                 "improve_existing_prompt" in tool_name or \
                 "analyze_prompt" in tool_name or \
                 "save_prompt" in tool_name:
                agent_id = "prompt_engineer"
                agent_name = "PromptEngineer"
                description = "Создание, улучшение и анализ промптов для LLM"
                capabilities = ["prompt_creation", "prompt_enhancement", "prompt_analysis", "prompt_optimization"]
                usage_examples = [
                    "Создай промпт для анализа данных",
                    "Улучши этот промпт: [текст промпта]",
                    "Проанализируй качество моего промпта",
                    "Помоги написать промпт для [задача]"
                ]
            elif "file" in tool_name.lower() or "read_file" in tool_name:
                agent_id = "file_agent"
                agent_name = "FileAgent"
                description = "Работа с файлами и файловой системой"
                capabilities = ["file_operations"]
                usage_examples = [
                    "Прочитай содержимое файла",
                    "Создай новый файл",
                    "Найди файлы по имени"
                ]
            elif "system" in tool_name.lower() or "execute" in tool_name.lower():
                agent_id = "system_agent"
                agent_name = "SystemAgent"
                description = "Работа с системой и выполнение команд"
                capabilities = ["system_commands"]
                usage_examples = [
                    "Выполни системную команду",
                    "Покажи информацию о системе",
                    "Проверь статус процессов"
                ]
            else:
                # Для неизвестных инструментов создаем общий агент
                agent_id = "general_agent"
                agent_name = "GeneralAgent"
                description = "Общие инструменты и функции"
                capabilities = ["general_tools"]
                usage_examples = [
                    "Использование различных инструментов",
                    "Выполнение специальных задач"
                ]
            
            # Создаем агента если его еще нет
            if agent_id not in agents_map:
                agents_map[agent_id] = {
                    "name": agent_name,
                    "description": description,
                    "capabilities": capabilities,
                    "agent_id": agent_id,
                    "instructions": {},
                    "usage_examples": usage_examples,
                    "tools": []
                }
            
            # Добавляем инструмент к агенту
            agents_map[agent_id]["tools"].append({
                "name": tool.name,
                "description": tool.description,
                "is_active": self.tool_status.get(tool.name, True),
                "instruction": f"Используй этот инструмент: {tool.description}"
            })
        
        # Формируем список агентов
        result = []
        for agent_id, agent_info in agents_map.items():
            # Агент активен если хотя бы один его инструмент активен
            is_active = any(t["is_active"] for t in agent_info["tools"])
            
            result.append({
                "name": agent_info["name"],
                "description": agent_info["description"],
                "capabilities": agent_info["capabilities"],
                "tools_count": len(agent_info["tools"]),
                "is_active": is_active,
                "agent_id": agent_info["agent_id"],
                "tools": agent_info["tools"],
                "usage_examples": agent_info["usage_examples"]
            })
        
        logger.debug(f"[API] Возвращаем {len(result)} агентов с {sum(len(a['tools']) for a in result)} инструментами для фронтенда")
        return result
    
    def set_orchestrator_status(self, is_active: bool):
        """
        Установка статуса активности оркестратора
        
        Args:
            is_active: True - оркестратор активен, False - отключен
        """
        self.orchestrator_active = is_active
        logger.info(f"Оркестратор {'включен' if is_active else 'отключен'}")
    
    def is_orchestrator_active(self) -> bool:
        """Проверка активности оркестратора"""
        return getattr(self, 'orchestrator_active', True)
    
    def set_tool_status(self, tool_name: str, is_active: bool):
        """
        Установка статуса активности инструмента или агента
        Если передан agent_id, активирует/деактивирует все инструменты агента
        """
        # Маппинг agent_id -> список инструментов
        agent_tools_map = {
            "document_agent": ["search_documents"],
            "web_search_agent": ["web_search"],
            "calculation_agent": ["calculate"],
            "memory_agent": ["save_memory"],
            "prompt_engineer": ["prompt_engineering", "enhance_prompt", "improve_existing_prompt", "analyze_prompt_quality", "save_prompt_to_gallery"]
        }
        
        # Проверяем, это agent_id или tool_name
        if tool_name in agent_tools_map:
            # Это agent_id, активируем/деактивируем все его инструменты
            tools_to_update = agent_tools_map[tool_name]
            logger.info(f"Обновление статуса агента '{tool_name}': {is_active}")
            for tool in tools_to_update:
                if tool in self.tool_status:
                    self.tool_status[tool] = is_active
                    logger.info(f"  - Инструмент '{tool}' {'активирован' if is_active else 'деактивирован'}")
        elif tool_name in self.tool_status:
            # Это конкретный инструмент
            self.tool_status[tool_name] = is_active
            logger.info(f"Инструмент '{tool_name}' {'активирован' if is_active else 'деактивирован'}")
        else:
            logger.warning(f"Инструмент или агент '{tool_name}' не найден")
    
    def get_tool_status(self, tool_name: str) -> bool:
        """Получение статуса активности инструмента"""
        return self.tool_status.get(tool_name, False)
    
    def get_all_tool_statuses(self) -> Dict[str, bool]:
        """Получение статусов всех инструментов"""
        return self.tool_status.copy()


# ============================================================================
# Глобальный экземпляр оркестратора
# ============================================================================

_langgraph_orchestrator: Optional[LangGraphOrchestrator] = None


def initialize_langgraph_orchestrator():
    """Инициализация глобального экземпляра LangGraph оркестратора"""
    global _langgraph_orchestrator
    
    if _langgraph_orchestrator is None:
        logger.info("Инициализация глобального LangGraph Orchestrator...")
        _langgraph_orchestrator = LangGraphOrchestrator()
        logger.info("Глобальный LangGraph Orchestrator инициализирован")
        return True
    else:
        logger.info("LangGraph Orchestrator уже инициализирован")
        return False


def get_langgraph_orchestrator() -> Optional[LangGraphOrchestrator]:
    """Получение глобального экземпляра LangGraph оркестратора"""
    return _langgraph_orchestrator