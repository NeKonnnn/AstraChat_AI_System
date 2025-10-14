"""
Агент-оркестратор для выбора подходящих агентов
"""

import logging
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent
from .document_agent import DocumentAgent
from .web_search_agent import WebSearchAgent
from .calculation_agent import CalculationAgent
from .memory_agent import MemoryAgent
from .mcp_agent import MCPAgent
from .langgraph_agent import LangGraphAgent

logger = logging.getLogger(__name__)

class OrchestratorAgent(BaseAgent):
    """Агент-оркестратор, который выбирает подходящего агента для задачи"""
    
    def __init__(self):
        super().__init__(
            name="orchestrator",
            description="Агент-оркестратор для выбора подходящих агентов"
        )
        
        # Инициализируем специализированных агентов
        self.agents = {
            "document": DocumentAgent(),
            "web_search": WebSearchAgent(),
            "calculation": CalculationAgent(),
            "memory": MemoryAgent(),
            "mcp": MCPAgent(),
            "langgraph": LangGraphAgent()
        }
        
        # Статус активности агентов (по умолчанию все активны)
        self.agent_status = {
            agent_name: True for agent_name in self.agents.keys()
        }
        
        self.capabilities = [
            "routing", "task_distribution", "agent_coordination"
        ]
    
    async def process_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка сообщения через выбор подходящего агента"""
        try:
            # Определяем подходящего агента
            selected_agent = self._select_agent(message, context)
            
            if selected_agent:
                logger.info(f"АГЕНТНАЯ АРХИТЕКТУРА: Выбран агент '{selected_agent.name}' для обработки запроса")
                logger.info(f"Описание агента: {selected_agent.description}")
                logger.info(f"Возможности агента: {', '.join(selected_agent.capabilities)}")
                
                # Выбираем оптимальную модель для этого агента и задачи
                optimal_model = await self._select_optimal_model(message, selected_agent.name)
                if optimal_model:
                    logger.info("=" * 80)
                    logger.info(f"ВЫБОР МОДЕЛИ: {optimal_model}")
                    logger.info(f" Агент: {selected_agent.name}")
                    logger.info(f" Задача: {message[:50]}{'...' if len(message) > 50 else ''}")
                    logger.info("=" * 80)
                    # Добавляем выбранную модель в контекст
                    if context is None:
                        context = {}
                    context['selected_model'] = optimal_model
                else:
                    logger.info("=" * 80)
                    logger.info(f"ВЫБОР МОДЕЛИ: Используем текущую модель по умолчанию")
                    logger.info(f"Агент: {selected_agent.name}")
                    logger.info("=" * 80)
                
                # Обрабатываем сообщение через выбранного агента
                response = await selected_agent.process_message(message, context)
                
                # Отладочная информация только в логах (не в ответе)
                return response
            else:
                # Если ни один агент не подходит, используем общий подход
                logger.info("АГЕНТНАЯ АРХИТЕКТУРА: Ни один специализированный агент не подходит, используем общий подход")
                response = await self._handle_general_message(message, context)
                
                # Отладочная информация только в логах (не в ответе)
                return response
                
        except Exception as e:
            logger.error(f"Ошибка в оркестраторе: {e}")
            return f"Произошла ошибка при обработке запроса: {str(e)}"
    
    def can_handle(self, message: str, context: Dict[str, Any] = None) -> bool:
        """Оркестратор может обработать любое сообщение"""
        return True
    
    async def _select_optimal_model(self, message: str, agent_name: str) -> Optional[str]:
        """Выбор оптимальной модели для агента и задачи"""
        try:
            # Получаем список доступных моделей
            import requests
            try:
                logger.debug("Запрашиваем список моделей с http://localhost:8000/api/models")
                response = requests.get('http://localhost:8000/api/models', timeout=2)
                
                if response.status_code != 200:
                    logger.warning(f"Не удалось получить список моделей, статус: {response.status_code}")
                    return None
                
                models_data = response.json()
                logger.debug(f"Получен ответ от API: {models_data}")
                
                models_list = models_data.get('models', [])
                
                if not models_list or len(models_list) == 0:
                    logger.info("Нет доступных моделей для выбора")
                    return None
                
                # Извлекаем имена файлов моделей
                available_models = [model.get('name') if isinstance(model, dict) else model for model in models_list]
                logger.debug(f"Извлечены имена моделей: {available_models}")
                
                # Если только одна модель, используем её
                if len(available_models) == 1:
                    logger.info(f"Доступна только одна модель: {available_models[0]}")
                    return available_models[0]
                
                logger.info(f"Доступно моделей: {len(available_models)}")
                
                # Используем LLM для выбора оптимальной модели
                from backend.agent import ask_agent
                
                # Формируем описание моделей
                models_list = "\n".join([f"{i+1}. {model}" for i, model in enumerate(available_models)])
                
                # Описание специализаций агентов
                agent_specializations = {
                    "document": "работа с документами, анализ текстов",
                    "web_search": "поиск актуальной информации в интернете",
                    "calculation": "математические вычисления, формулы",
                    "memory": "сохранение информации",
                    "mcp": "работа с внешними сервисами",
                    "langgraph": "сложные многошаговые задачи"
                }
                
                agent_spec = agent_specializations.get(agent_name, "общие задачи")
                
                # Формируем промпт для выбора модели
                selection_prompt = f"""Ты - система выбора оптимальной AI модели. Выбери наиболее подходящую модель для задачи.

Доступные модели:
{models_list}

Тип задачи: {agent_spec}
Запрос пользователя: "{message}"

Проанализируй:
1. Сложность задачи
2. Требуемые возможности модели
3. Специализацию задачи

Ответь ТОЛЬКО названием файла модели (например: "Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf"). Ничего больше не пиши!

Выбранная модель:"""
                
                # Отправляем запрос к LLM
                response = ask_agent(
                    selection_prompt,
                    history=[],
                    streaming=False,
                    max_tokens=50
                )
                
                # Извлекаем название модели из ответа
                selected_model = response.strip()
                
                # Проверяем, что выбранная модель есть в списке доступных
                for model in available_models:
                    if model in selected_model or selected_model in model:
                        logger.info(f"LLM выбрал модель: {model}")
                        return model
                
                logger.warning(f"LLM вернул невалидную модель: {selected_model}")
                return None
                
            except requests.RequestException as e:
                logger.error(f"Ошибка при получении списка моделей: {e}")
                logger.error(f"Убедитесь, что backend запущен на http://localhost:8000")
                return None
            except Exception as e:
                logger.error(f"Неожиданная ошибка при запросе моделей: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return None
                
        except Exception as e:
            logger.error(f"Ошибка в выборе оптимальной модели: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _select_agent(self, message: str, context: Dict[str, Any] = None) -> Optional[BaseAgent]:
        """Выбор подходящего агента для задачи с использованием LLM"""
        logger.info(f"АНАЛИЗ ЗАПРОСА: '{message[:100]}{'...' if len(message) > 100 else ''}'")
        
        # Получаем список активных агентов
        active_agents = {name: agent for name, agent in self.agents.items() 
                        if self.agent_status.get(name, True)}
        
        if not active_agents:
            logger.warning("Нет активных агентов!")
            return None
        
        logger.info(f"Активных агентов: {len(active_agents)} из {len(self.agents)}")
        logger.info(f"Активные агенты: {', '.join(active_agents.keys())}")
        
        try:
            # Используем LLM для анализа запроса и выбора агента
            selected_agent = self._llm_based_agent_selection(message, active_agents)
            
            if selected_agent and selected_agent in active_agents:
                logger.info(f"LLM выбрал агента: {selected_agent}")
                return active_agents.get(selected_agent)
            
            # Если LLM не смог выбрать агента, возвращаем None (будет использован общий подход)
            logger.info("LLM не смог выбрать агента, будет использован общий подход")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при LLM-based выборе агента: {e}")
            # При ошибке также возвращаем None (будет использован общий подход)
            return None
    
    def _llm_based_agent_selection(self, message: str, active_agents: Dict[str, BaseAgent]) -> Optional[str]:
        """Выбор агента с использованием LLM (только среди активных)"""
        try:
            # Импортируем ask_agent
            from backend.agent import ask_agent
            
            # Формируем описание только активных агентов
            agent_descriptions = {
                "document": "Агент для работы с загруженными документами\n   Используй для: поиска информации в документах, анализа текстов, работы с файлами",
                "web_search": "Агент для поиска в интернете\n   Используй для: поиска актуальной информации, новостей, погоды, курсов валют",
                "calculation": "Агент для математических вычислений\n   Используй для: любых математических операций, вычислений, формул, расчетов",
                "memory": "Агент для работы с памятью\n   Используй для: сохранения информации, создания заметок, запоминания данных",
                "mcp": "Агент для работы с внешними сервисами через MCP\n   Используй для: работы с файловой системой, браузером, базами данных",
                "langgraph": "Агент для планирования сложных задач\n   Используй для: многошаговых задач, планирования, последовательных действий"
            }
            
            # Формируем список только активных агентов
            agents_list = []
            for i, agent_name in enumerate(active_agents.keys(), 1):
                if agent_name in agent_descriptions:
                    agents_list.append(f"{i}. {agent_name} - {agent_descriptions[agent_name]}")
            
            agents_description = "Доступные агенты:\n\n" + "\n\n".join(agents_list)
            agents_description += "\n\n7. general - Общий подход (прямое обращение к LLM)\n   Используй для: обычных вопросов, диалога, объяснений"
            
            # Формируем промпт для LLM
            valid_agent_names = list(active_agents.keys()) + ["general"]
            agents_str = ", ".join(valid_agent_names)
            
            selection_prompt = f"""Ты - система маршрутизации запросов к агентам. Проанализируй запрос пользователя и выбери ОДИН наиболее подходящий агент.

{agents_description}

Запрос пользователя: "{message}"

Ответь ТОЛЬКО названием агента ({agents_str}). Ничего больше не пиши!

Выбранный агент:"""
            
            # Отправляем запрос к LLM
            response = ask_agent(
                selection_prompt,
                history=[],
                streaming=False,
                max_tokens=20  # Нужно только название агента
            )
            
            # Извлекаем название агента из ответа
            agent_name = response.strip().lower()
            
            # Проверяем, что ответ валидный и агент активен
            for valid_agent in valid_agent_names:
                if valid_agent in agent_name:
                    logger.info(f"LLM выбрал агента: {valid_agent}")
                    return valid_agent if valid_agent != "general" else None
            
            logger.warning(f"LLM вернул невалидный ответ: {agent_name}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка в LLM-based выборе агента: {e}")
            return None
    
    async def _handle_general_message(self, message: str, context: Dict[str, Any] = None) -> str:
        """Обработка общего сообщения без специализированного агента"""
        try:
            # Используем базовую LLM модель для ответа
            from backend.agent import ask_agent
            
            history = context.get("history", []) if context else []
            
            # Проверяем, выбрана ли модель
            selected_model = context.get("selected_model") if context else None
            
            if selected_model:
                logger.info("=" * 80)
                logger.info(f"ВЫБОР МОДЕЛИ: {selected_model}")
                logger.info(f"Режим: Общий подход (без специализированного агента)")
                logger.info(f"Задача: {message[:50]}{'...' if len(message) > 50 else ''}")
                logger.info("=" * 80)
                response = ask_agent(
                    message,
                    history=history,
                    streaming=False,
                    model_path=selected_model
                )
            else:
                logger.info("=" * 80)
                logger.info(f"ВЫБОР МОДЕЛИ: Используем текущую модель по умолчанию")
                logger.info(f"Режим: Общий подход (без специализированного агента)")
                logger.info(f"Задача: {message[:50]}{'...' if len(message) > 50 else ''}")
                logger.info("=" * 80)
                response = ask_agent(
                    message,
                    history=history,
                    streaming=False
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в общем обработчике: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."
    
    def get_available_agents(self) -> List[Dict[str, Any]]:
        """Получение списка всех агентов с их статусами"""
        agents_info = []
        for agent_name, agent in self.agents.items():
            info = agent.get_info()
            info['is_active'] = self.agent_status.get(agent_name, True)
            info['agent_id'] = agent_name
            agents_info.append(info)
        return agents_info
    
    def set_agent_status(self, agent_name: str, is_active: bool) -> bool:
        """Установка статуса активности агента"""
        if agent_name in self.agents:
            self.agent_status[agent_name] = is_active
            status_text = "активирован" if is_active else "деактивирован"
            logger.info(f"Агент '{agent_name}' {status_text}")
            return True
        else:
            logger.warning(f"Попытка изменить статус несуществующего агента: {agent_name}")
            return False
    
    def get_agent_status(self, agent_name: str) -> Optional[bool]:
        """Получение статуса активности агента"""
        return self.agent_status.get(agent_name)
    
    def get_all_agent_statuses(self) -> Dict[str, bool]:
        """Получение статусов всех агентов"""
        return self.agent_status.copy()
    
    def add_agent(self, agent: BaseAgent):
        """Добавление нового агента в систему"""
        self.agents[agent.name] = agent
        self.agent_status[agent.name] = True  # По умолчанию новый агент активен
        logger.info(f"Добавлен новый агент: {agent.name}")
    
    def remove_agent(self, agent_name: str):
        """Удаление агента из системы"""
        if agent_name in self.agents:
            del self.agents[agent_name]
            if agent_name in self.agent_status:
                del self.agent_status[agent_name]
            logger.info(f"Удален агент: {agent_name}")
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Получение агента по имени"""
        return self.agents.get(agent_name)
