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
        logger.info(f"║  Загружено инструментов: {len(self.tools):<30} ║")
        logger.info(f"║  Категории:                                               ║")
        for category, count in self.tools_info['categories'].items():
            logger.info(f"║    - {category:<20} {count:<25} ║")
        logger.info(f"╚═══════════════════════════════════════════════════════════╝")
        
        # Создаем словарь инструментов по именам для быстрого доступа
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        
        # Статус активности инструментов (для управления через UI)
        self.tool_status = {tool.name: True for tool in self.tools}
        
        # Создаем ToolNode для LangGraph
        self.tool_node = ToolNode(self.tools)
        
        # Checkpoint для сохранения состояния между вызовами
        self.checkpointer = MemorySaver()
        
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
            try:
                from backend.agent import ask_agent
            except ModuleNotFoundError:
                from agent import ask_agent
            
            tools_description = self._get_active_tools_description()
            
            # Формируем контекстную информацию о документах
            docs_context = ""
            if available_docs:
                docs_context = f"""
ДОСТУПНЫЕ ДОКУМЕНТЫ:
- Загружено документов: {len(available_docs)}
- Названия: {', '.join(available_docs[:3])}{'...' if len(available_docs) > 3 else ''}

ВАЖНО: Если запрос касается анализа документов, поиска информации в файлах или подсчета элементов в документах, используй инструмент 'search_documents' с соответствующим поисковым запросом.
"""
            
            planning_prompt = f"""Ты - система планирования задач AI-ассистента. Проанализируй запрос пользователя и определи:
1. Нужны ли специальные инструменты для выполнения задачи?
2. Если да, какие инструменты и в каком порядке нужно использовать?

{docs_context}

Доступные инструменты:
{tools_description}

Запрос пользователя: "{user_query}"

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
            
            logger.info(f"[PLANNER] Получен ответ от LLM (длина: {len(response)} символов)")
            logger.debug(f"[PLANNER] Полный ответ LLM: {response}")
            
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
                
                logger.info(f"[PLANNER] План успешно создан:")
                logger.info(f"[PLANNER]   - Нужны инструменты: {needs_tools}")
                logger.info(f"[PLANNER]   - Шагов в плане: {len(plan)}")
                logger.info(f"[PLANNER]   - Обоснование: {reasoning}")
                
                if plan:
                    logger.info(f"[PLANNER] Детали плана:")
                    for i, step in enumerate(plan, 1):
                        tool_name = step.get('tool', 'UNKNOWN')
                        tool_input = step.get('input', '')[:80]
                        logger.info(f"[PLANNER]   {i}. Инструмент: '{tool_name}'")
                        logger.info(f"[PLANNER]      Входные данные: {tool_input}...")
                else:
                    logger.info(f"[PLANNER] План пуст - инструменты не требуются")
                
                state["plan"] = plan if needs_tools else []
                state["current_step"] = 0
                state["tool_results"] = []
                
            except json.JSONDecodeError as e:
                logger.error(f"[PLANNER] Ошибка парсинга JSON: {e}")
                logger.error(f"[PLANNER] Ответ LLM: {response}")
                # Fallback: считаем что инструменты не нужны
                state["plan"] = []
                state["current_step"] = 0
                state["tool_results"] = []
            
            return state
            
        except Exception as e:
            logger.error(f"[PLANNER] Ошибка планирования: {e}")
            import traceback
            logger.error(traceback.format_exc())
            state["error"] = f"Ошибка планирования: {str(e)}"
            state["plan"] = []
            return state
    
    def _should_execute_tools(self, state: OrchestratorState) -> str:
        """Условное ребро: определяет нужно ли выполнять инструменты"""
        plan = state.get("plan", [])
        
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
            
            logger.info(f"\n{'='*70}")
            logger.info(f"[EXECUTOR] 🔧 Выполнение инструментов")
            logger.info(f"[EXECUTOR] Всего шагов: {len(plan)}")
            logger.info(f"{'='*70}")
            
            for i, step in enumerate(plan, 1):
                tool_name = step.get("tool")
                tool_input = step.get("input")
                
                logger.info(f"\n[EXECUTOR] Шаг {i}/{len(plan)}: {tool_name}")
                logger.info(f"[EXECUTOR] Вход: {tool_input[:100]}...")
                
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
                
                logger.info(f"[EXECUTOR] ✓ Инструмент найден, запускаем...")
                
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
            
            logger.info(f"\n{'='*70}")
            logger.info(f"[AGGREGATOR] Формирование финального ответа")
            logger.info(f"[AGGREGATOR] Результатов инструментов: {len(tool_results)}")
            logger.info(f"{'='*70}")
            
            try:
                from backend.agent import ask_agent
            except ModuleNotFoundError:
                from agent import ask_agent
            
            # Если инструменты не использовались, даем прямой ответ
            if not tool_results:
                logger.info(f"[AGGREGATOR] Инструменты не использовались, прямой ответ")
                
                final_answer = ask_agent(
                    user_query,
                    history=state.get("context", {}).get("history", []),
                    streaming=False,
                    model_path=state.get("context", {}).get("selected_model")
                )
                
                state["final_answer"] = final_answer
                logger.info(f"[AGGREGATOR] Ответ сформирован: {len(final_answer)} символов")
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
            
            final_answer = ask_agent(
                aggregation_prompt,
                history=[],
                streaming=False,
                model_path=state.get("context", {}).get("selected_model")
            )
            
            state["final_answer"] = final_answer
            logger.info(f"[AGGREGATOR] Финальный ответ сформирован: {len(final_answer)} символов")
            
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
            logger.info(f"\n{'#'*70}")
            logger.info(f"# LangGraph Orchestrator - Обработка запроса")
            logger.info(f"# Запрос: {message[:100]}...")
            logger.info(f"{'#'*70}\n")
            
            # Компилируем граф если еще не скомпилирован
            if self.compiled_graph is None:
                self.compiled_graph = self.graph.compile(checkpointer=self.checkpointer)
                logger.info("Граф скомпилирован")
            
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
            config = {"configurable": {"thread_id": "default"}}
            final_state = self.compiled_graph.invoke(initial_state, config)
            
            # Проверяем результат
            if final_state.get("error"):
                error_msg = final_state["error"]
                logger.error(f"Ошибка выполнения: {error_msg}")
                return f"Произошла ошибка: {error_msg}"
            
            final_answer = final_state.get("final_answer")
            if final_answer:
                logger.info(f"\n{'#'*70}")
                logger.info(f"# Задача успешно выполнена")
                logger.info(f"# Ответ: {len(final_answer)} символов")
                logger.info(f"{'#'*70}\n")
                return final_answer
            else:
                logger.warning("Финальный ответ не сформирован")
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
        # Группируем инструменты по категориям (агентам) с инструкциями
        agents_map = {
            "DocumentAgent": {
                "name": "DocumentAgent",
                "description": "Поиск и анализ информации в загруженных документах",
                "capabilities": ["search_documents"],
                "agent_id": "document_agent",
                "instructions": {
                    "search_documents": "Используй этот инструмент для поиска информации в загруженных документах. Передавай ключевые слова или фразы для поиска. Пример: 'Python программирование', 'машинное обучение', 'алгоритмы'"
                },
                "usage_examples": [
                    "Найди информацию о Python в документах",
                    "Поищи данные о машинном обучении",
                    "Найди все упоминания алгоритмов"
                ]
            },
            "WebSearchAgent": {
                "name": "WebSearchAgent", 
                "description": "Поиск информации в интернете",
                "capabilities": ["web_search"],
                "agent_id": "web_search_agent",
                "instructions": {
                    "web_search": "Используй этот инструмент для поиска актуальной информации в интернете. Передавай конкретные поисковые запросы. Пример: 'погода в Москве', 'новости технологий', 'курс доллара'"
                },
                "usage_examples": [
                    "Какая погода в Москве?",
                    "Найди последние новости о ИИ",
                    "Какой курс доллара сегодня?"
                ]
            },
            "CalculationAgent": {
                "name": "CalculationAgent",
                "description": "Выполнение математических вычислений",
                "capabilities": ["calculate"],
                "agent_id": "calculation_agent",
                "instructions": {
                    "calculate": "Используй этот инструмент для выполнения математических вычислений. Передавай математические выражения в текстовом виде. Поддерживаются: +, -, *, /, **, sqrt(), sin(), cos(), log() и другие функции"
                },
                "usage_examples": [
                    "Посчитай 15 * 7 + 3",
                    "Вычисли квадратный корень из 144",
                    "Найди площадь круга с радиусом 5"
                ]
            },
            "MemoryAgent": {
                "name": "MemoryAgent",
                "description": "Сохранение важной информации в долговременную память",
                "capabilities": ["save_memory"],
                "agent_id": "memory_agent",
                "instructions": {
                    "save_memory": "Используй этот инструмент для сохранения важной информации в долговременную память системы. Передавай содержание для сохранения и категорию (general, important, personal, work). Пример: 'Пользователь предпочитает Python для программирования'"
                },
                "usage_examples": [
                    "Запомни, что я работаю программистом",
                    "Сохрани информацию о моих предпочтениях",
                    "Запиши важные факты о проекте"
                ]
            }
        }
        
        # Формируем список агентов с их инструментами и инструкциями
        result = []
        for agent_id, agent_info in agents_map.items():
            # Проверяем какие инструменты из этого агента доступны
            agent_tools = []
            for capability in agent_info["capabilities"]:
                if capability in self.tools_by_name:
                    tool = self.tools_by_name[capability]
                    agent_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "is_active": self.tool_status.get(tool.name, True),
                        "instruction": agent_info["instructions"].get(capability, "Нет инструкции")
                    })
            
            # Если у агента есть хотя бы один инструмент, добавляем его
            if agent_tools:
                # Агент активен если хотя бы один его инструмент активен
                is_active = any(t["is_active"] for t in agent_tools)
                
                result.append({
                    "name": agent_info["name"],
                    "description": agent_info["description"],
                    "capabilities": agent_info["capabilities"],
                    "tools_count": len(agent_tools),
                    "is_active": is_active,
                    "agent_id": agent_info["agent_id"],
                    "tools": agent_tools,
                    "usage_examples": agent_info["usage_examples"]
                })
        
        logger.debug(f"[API] Возвращаем {len(result)} агентов с инструкциями для фронтенда")
        return result
    
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
            "memory_agent": ["save_memory"]
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
