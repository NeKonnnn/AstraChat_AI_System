"""
Инструменты для работы с агентами
Эти tools вызывают специализированных агентов для выполнения задач
"""

import logging
import asyncio
import json
from typing import Dict, Any, List
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _run_async_agent(agent_class, message: str, context: Dict[str, Any] = None):
    """
    Вспомогательная функция для запуска асинхронных агентов в синхронном контексте
    """
    try:
        # Получаем контекст из глобального состояния если не передан
        if context is None:
            context = _get_global_context()
        
        # Проверяем, есть ли уже запущенный event loop
        try:
            loop = asyncio.get_running_loop()
            # Если есть запущенный loop, создаем задачу
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_in_new_loop, agent_class, message, context)
                return future.result()
        except RuntimeError:
            # Нет запущенного loop, можем использовать asyncio.run
            return _run_in_new_loop(agent_class, message, context)
    except Exception as e:
        logger.error(f"Ошибка в _run_async_agent: {e}")
        return f"Ошибка выполнения агента: {str(e)}"

def _run_in_new_loop(agent_class, message: str, context: Dict[str, Any] = None):
    """Запуск агента в новом event loop"""
    async def _async_wrapper():
        agent = agent_class()
        agent_context = context if context is not None else {"history": []}
        return await agent.process_message(message, agent_context)
    
    return asyncio.run(_async_wrapper())


def _run_async_callable(coro):
    """Запустить async callable в sync-контексте."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return executor.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)

def _get_global_context():
    """Получение глобального контекста из main.py"""
    try:
        import backend.main as main_module
        context = {}
        
        # Получаем doc_processor
        if hasattr(main_module, 'doc_processor'):
            context['doc_processor'] = main_module.doc_processor
        
        # Получаем другие компоненты если нужно
        if hasattr(main_module, 'selected_model'):
            context['selected_model'] = main_module.selected_model
            
        return context
    except Exception as e:
        logger.warning(f"Не удалось получить глобальный контекст: {e}")
        return {}


@tool
def search_documents(query: str) -> str:
    """
    Поиск информации в загруженных документах.
    Используется для поиска по векторному хранилищу документов.
    
    Args:
        query: Поисковый запрос
        
    Returns:
        Найденная информация из документов
    """
    try:
        logger.info(f"[TOOL] search_documents: {query}")
        try:
            from backend.agents.document_agent import DocumentAgent
        except ModuleNotFoundError:
            from agents.document_agent import DocumentAgent
        
        result = _run_async_agent(DocumentAgent, query)
        logger.info(f"[TOOL] search_documents результат: {len(result)} символов")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в search_documents: {e}")
        return f"Ошибка при поиске в документах: {str(e)}"


@tool
def retrieve_rag_context(request: str) -> str:
    """
    Унифицированный retrieval-инструмент для Agentic RAG.
    Поддерживает источники: project, kb, memory, global.

    request можно передать строкой:
      - просто поисковый запрос
      - JSON вида {"query":"...", "stores":["project","kb","memory","global"], "k":6, "strategy":"graph"}
    """
    try:
        from backend.tools.prompt_tools import get_tool_context
        import backend.app_state as state
    except ModuleNotFoundError:
        from tools.prompt_tools import get_tool_context
        import app_state as state

    ctx = get_tool_context() or {}
    rag_client = getattr(state, "rag_client", None)
    if not rag_client:
        return json.dumps({"ok": False, "error": "RAG client unavailable"}, ensure_ascii=False)

    try:
        payload = json.loads(request) if request and request.strip().startswith("{") else {"query": request}
    except Exception:
        payload = {"query": request}

    query = str(payload.get("query") or "").strip()
    if not query:
        return json.dumps({"ok": False, "error": "empty query"}, ensure_ascii=False)

    stores: List[str] = payload.get("stores") or ["project", "kb", "memory", "global"]
    default_k = int(state.get_rag_chat_top_k())
    try:
        k = int(payload.get("k") or default_k)
    except (TypeError, ValueError):
        k = default_k
    k = max(1, min(k, 64))
    strategy = str(payload.get("strategy") or ctx.get("rag_strategy") or "auto")
    project_id = payload.get("project_id") or ctx.get("project_id")

    logger.info(
        "[RAG] agent tool retrieve_rag_context: strategy=%s stores=%s k=%s project_id=%s query_preview=%r",
        strategy,
        stores,
        k,
        project_id,
        (query[:80] + "…") if len(query) > 80 else query,
    )

    async def _run():
        results: List[Dict[str, Any]] = []
        if "project" in stores and project_id:
            try:
                hits = await rag_client.project_rag_search(query, project_id=project_id, k=k, strategy=strategy)
                for c, s, doc_id, chunk_idx in hits:
                    results.append(
                        {"store": "project", "document_id": doc_id, "chunk_index": chunk_idx, "score": float(s), "content": c}
                    )
            except Exception as e:
                logger.warning("retrieve_rag_context project error: %s", e)

        if "kb" in stores:
            try:
                hits = await rag_client.kb_search(query, k=k, strategy=strategy)
                for c, s, doc_id, chunk_idx in hits:
                    results.append(
                        {"store": "kb", "document_id": doc_id, "chunk_index": chunk_idx, "score": float(s), "content": c}
                    )
            except Exception as e:
                logger.warning("retrieve_rag_context kb error: %s", e)

        if "memory" in stores:
            try:
                hits = await rag_client.memory_rag_search(query, k=k, strategy=strategy)
                for c, s, doc_id, chunk_idx in hits:
                    results.append(
                        {"store": "memory", "document_id": doc_id, "chunk_index": chunk_idx, "score": float(s), "content": c}
                    )
            except Exception as e:
                logger.warning("retrieve_rag_context memory error: %s", e)

        if "global" in stores:
            try:
                hits = await rag_client.search(query, k=k, strategy=strategy)
                for c, s, doc_id, chunk_idx in hits:
                    results.append(
                        {"store": "global", "document_id": doc_id, "chunk_index": chunk_idx, "score": float(s), "content": c}
                    )
            except Exception as e:
                logger.warning("retrieve_rag_context global error: %s", e)

        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        top = results[: max(k * 3, 10)]
        return {
            "ok": True,
            "query": query,
            "strategy": strategy,
            "stores": stores,
            "hits": top,
        }

    data = _run_async_callable(_run())
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False)
    return json.dumps({"ok": False, "error": "unexpected tool result"}, ensure_ascii=False)


class AgentTools:
    """Класс для группировки инструментов агентов"""
    
    @staticmethod
    def get_tools():
        """Получение всех инструментов агентов"""
        return [
            search_documents,
            retrieve_rag_context,
        ]