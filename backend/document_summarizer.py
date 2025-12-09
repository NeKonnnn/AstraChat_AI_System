"""
Модуль для суммаризации больших документов
Использует подход иерархической суммаризации для ускорения поиска
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentSummarizer:
    """
    Класс для создания многоуровневых суммаризаций документов
    
    Стратегия:
    1. Level 0: Оригинальные чанки (chunk_size=1500)
    2. Level 1: Промежуточные суммаризации (объединение 5-10 чанков)
    3. Level 2: Финальная суммаризация всего документа
    
    Это позволяет:
    - Быстро найти релевантный раздел через Level 2/1
    - Получить детали из Level 0
    - Использовать полный контекст при необходимости
    """
    
    def __init__(self, llm_function=None, max_chunk_size=1500, intermediate_summary_chunks=8):
        """
        Args:
            llm_function: Функция для вызова LLM (опционально)
            max_chunk_size: Максимальный размер чанка
            intermediate_summary_chunks: Количество чанков для промежуточной суммаризации
        """
        self.llm_function = llm_function
        self.max_chunk_size = max_chunk_size
        self.intermediate_summary_chunks = intermediate_summary_chunks
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=200,
            length_function=len,
        )
    
    async def create_hierarchical_summary_async(
        self, 
        text: str, 
        doc_name: str,
        create_full_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Создание иерархической структуры документа с суммаризациями
        
        Args:
            text: Полный текст документа
            doc_name: Имя документа
            create_full_summary: Создавать ли финальную суммаризацию через LLM
            
        Returns:
            dict: {
                "full_text": str,
                "level_0_chunks": List[dict],  # Оригинальные чанки
                "level_1_summaries": List[dict],  # Промежуточные суммаризации
                "level_2_summary": str,  # Финальная суммаризация документа
                "metadata": dict
            }
        """
        logger.info(f"Создание иерархической структуры для документа '{doc_name}'")
        logger.info(f"Размер документа: {len(text)} символов")
        
        # Level 0: Разбиваем на чанки
        chunks = self.text_splitter.split_text(text)
        if not chunks:
            chunks = [text] if text else [f"[Документ: {doc_name}]"]
        
        level_0_chunks = [
            {
                "content": chunk,
                "chunk_index": i,
                "level": 0,
                "doc_name": doc_name
            }
            for i, chunk in enumerate(chunks)
        ]
        
        logger.info(f"Level 0: Создано {len(level_0_chunks)} оригинальных чанков")
        
        # Level 1: Создаем промежуточные суммаризации
        # Объединяем каждые N чанков в одну промежуточную суммаризацию
        level_1_summaries = []
        
        for i in range(0, len(level_0_chunks), self.intermediate_summary_chunks):
            batch = level_0_chunks[i:i + self.intermediate_summary_chunks]
            
            # Объединяем содержимое чанков
            combined_text = "\n\n".join([c["content"] for c in batch])
            
            # Создаем краткую метаинформацию
            chunk_range = f"чанки {batch[0]['chunk_index']}-{batch[-1]['chunk_index']}"
            
            # Для промежуточных суммаризаций используем простое объединение с маркерами
            # (без вызова LLM для скорости)
            intermediate_summary = {
                "content": f"[РАЗДЕЛ ДОКУМЕНТА '{doc_name}' ({chunk_range})]\n\n{combined_text[:3000]}...",  # Первые 3000 символов
                "summary_index": len(level_1_summaries),
                "level": 1,
                "chunk_range": (batch[0]['chunk_index'], batch[-1]['chunk_index']),
                "doc_name": doc_name
            }
            
            level_1_summaries.append(intermediate_summary)
        
        logger.info(f"Level 1: Создано {len(level_1_summaries)} промежуточных суммаризаций")
        
        # Level 2: Финальная суммаризация всего документа
        level_2_summary = ""
        
        if create_full_summary and self.llm_function:
            try:
                # Создаем краткое содержание документа через LLM
                logger.info("Level 2: Создание финальной суммаризации через LLM...")
                
                # Используем первые и последние чанки + промежуточные части
                summary_text = ""
                
                # Первые 3 чанка
                summary_text += "=== НАЧАЛО ДОКУМЕНТА ===\n"
                for chunk in level_0_chunks[:3]:
                    summary_text += chunk["content"] + "\n\n"
                
                # Средние чанки (выборочно)
                if len(level_0_chunks) > 10:
                    summary_text += "\n=== ОСНОВНАЯ ЧАСТЬ ===\n"
                    step = max(1, len(level_0_chunks) // 5)
                    for i in range(3, len(level_0_chunks) - 3, step):
                        summary_text += level_0_chunks[i]["content"][:500] + "...\n\n"
                
                # Последние 3 чанка
                summary_text += "\n=== КОНЕЦ ДОКУМЕНТА ===\n"
                for chunk in level_0_chunks[-3:]:
                    summary_text += chunk["content"] + "\n\n"
                
                # Ограничиваем размер до 15000 символов для LLM
                if len(summary_text) > 15000:
                    summary_text = summary_text[:15000] + "\n\n[...обрезано...]"
                
                # Запрос к LLM для создания суммаризации
                prompt = f"""Создай структурированное краткое содержание следующего документа.
Включи:
1. Основную тему документа
2. Ключевые разделы и темы
3. Важные факты и данные
4. Выводы (если есть)

Документ "{doc_name}":

{summary_text}

Краткое содержание (на русском):"""
                
                # Вызываем LLM (асинхронно, если возможно)
                try:
                    if asyncio.iscoroutinefunction(self.llm_function):
                        level_2_summary = await self.llm_function(prompt, streaming=False)
                    else:
                        level_2_summary = self.llm_function(prompt, streaming=False)
                    
                    logger.info(f"Level 2: Суммаризация создана ({len(level_2_summary)} символов)")
                except Exception as llm_error:
                    logger.warning(f"Ошибка при создании суммаризации через LLM: {llm_error}")
                    # Fallback: используем начало документа
                    level_2_summary = f"[КРАТКОЕ СОДЕРЖАНИЕ '{doc_name}']\n\n" + text[:2000] + "..."
            
            except Exception as e:
                logger.error(f"Ошибка при создании Level 2 суммаризации: {e}")
                # Fallback
                level_2_summary = f"[ДОКУМЕНТ '{doc_name}']\n\n" + text[:2000] + "..."
        else:
            # Без LLM - используем начало документа
            level_2_summary = f"[ДОКУМЕНТ '{doc_name}' - {len(text)} символов, {len(chunks)} чанков]\n\n" + text[:2000]
            logger.info("Level 2: Использовано начало документа (LLM не доступен)")
        
        result = {
            "full_text": text,
            "level_0_chunks": level_0_chunks,
            "level_1_summaries": level_1_summaries,
            "level_2_summary": level_2_summary,
            "metadata": {
                "doc_name": doc_name,
                "total_chars": len(text),
                "total_chunks": len(level_0_chunks),
                "total_intermediate_summaries": len(level_1_summaries)
            }
        }
        
        logger.info(f"Иерархическая структура создана для '{doc_name}'")
        logger.info(f"  - Level 0: {len(level_0_chunks)} чанков")
        logger.info(f"  - Level 1: {len(level_1_summaries)} промежуточных суммаризаций")
        logger.info(f"  - Level 2: {len(level_2_summary)} символов финальной суммаризации")
        
        return result
    
    def create_hierarchical_summary(
        self, 
        text: str, 
        doc_name: str,
        create_full_summary: bool = True
    ) -> Dict[str, Any]:
        """Синхронная обертка для create_hierarchical_summary_async"""
        try:
            loop = asyncio.get_running_loop()
            # Если loop запущен, создаем задачу в отдельном потоке
            import threading
            
            result_container = {}
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(
                        self.create_hierarchical_summary_async(text, doc_name, create_full_summary)
                    )
                    result_container['result'] = result
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
            return result_container.get('result')
        except RuntimeError:
            # Нет запущенного loop
            return asyncio.run(self.create_hierarchical_summary_async(text, doc_name, create_full_summary))


class OptimizedDocumentIndex:
    """
    Оптимизированный индекс для быстрого поиска по документам
    
    Использует:
    1. Иерархическую суммаризацию для быстрого поиска
    2. Кэширование векторов
    3. Адаптивную стратегию поиска
    """
    
    def __init__(self, embeddings_model, vector_repo):
        self.embeddings_model = embeddings_model
        self.vector_repo = vector_repo
        
        # Кэш для быстрого доступа
        # {doc_name: {"level_0": [...], "level_1": [...], "level_2": str, "vectors_cached": bool}}
        self.document_cache = {}
    
    async def index_document_hierarchical_async(
        self,
        hierarchical_doc: Dict[str, Any],
        document_id: int
    ) -> bool:
        """
        Индексирование документа с иерархической структурой
        
        Args:
            hierarchical_doc: Результат от DocumentSummarizer.create_hierarchical_summary_async
            document_id: ID документа в БД
            
        Returns:
            bool: Успешность индексирования
        """
        doc_name = hierarchical_doc["metadata"]["doc_name"]
        logger.info(f"Индексирование документа '{doc_name}' с иерархией")
        
        try:
            # Индексируем ТОЛЬКО:
            # 1. Level 2 (финальная суммаризация) - 1 вектор
            # 2. Level 1 (промежуточные суммаризации) - N векторов (обычно 3-10)
            # 3. Выборочно Level 0 (каждый 3-й чанк) - для детального поиска
            
            vectors_to_save = []
            
            # Level 2: Финальная суммаризация (САМЫЙ ВАЖНЫЙ)
            level_2_embedding = self.embeddings_model.embed_query(hierarchical_doc["level_2_summary"])
            vectors_to_save.append({
                "embedding": level_2_embedding,
                "content": hierarchical_doc["level_2_summary"],
                "chunk_index": -2,  # Специальный индекс для Level 2
                "metadata": {"level": 2, "doc_name": doc_name, "type": "full_summary"}
            })
            
            # Level 1: Промежуточные суммаризации
            for summary in hierarchical_doc["level_1_summaries"]:
                embedding = self.embeddings_model.embed_query(summary["content"][:1000])  # Первые 1000 символов
                vectors_to_save.append({
                    "embedding": embedding,
                    "content": summary["content"],
                    "chunk_index": -1,  # Специальный индекс для Level 1
                    "metadata": {
                        "level": 1,
                        "doc_name": doc_name,
                        "summary_index": summary["summary_index"],
                        "chunk_range": summary["chunk_range"],
                        "type": "intermediate_summary"
                    }
                })
            
            # Level 0: Индексируем каждый 2-й чанк (для детального поиска)
            # Это уменьшает количество векторов в 2 раза, обеспечивая хорошее покрытие документа
            level_0_chunks = hierarchical_doc["level_0_chunks"]
            for i, chunk in enumerate(level_0_chunks):
                if i % 2 == 0 or i == 0 or i == len(level_0_chunks) - 1:  # Первый, последний, и каждый 2-й
                    embedding = self.embeddings_model.embed_query(chunk["content"])
                    vectors_to_save.append({
                        "embedding": embedding,
                        "content": chunk["content"],
                        "chunk_index": chunk["chunk_index"],
                        "metadata": {"level": 0, "doc_name": doc_name, "type": "detail_chunk"}
                    })
            
            logger.info(f"Сохранение {len(vectors_to_save)} векторов вместо {len(level_0_chunks)}")
            logger.info(f"  - Level 2: 1 вектор")
            logger.info(f"  - Level 1: {len(hierarchical_doc['level_1_summaries'])} векторов")
            logger.info(f"  - Level 0: ~{len([v for v in vectors_to_save if v['metadata'].get('level') == 0])} векторов (выборочно)")
            
            # Сохраняем в pgvector
            from backend.database.postgresql.models import DocumentVector
            
            saved_count = 0
            for vector_data in vectors_to_save:
                try:
                    vector = DocumentVector(
                        document_id=document_id,
                        chunk_index=vector_data["chunk_index"],
                        embedding=vector_data["embedding"],
                        content=vector_data["content"],
                        metadata={
                            **vector_data["metadata"],
                            "source": doc_name
                        }
                    )
                    
                    vector_id = await self.vector_repo.create_vector(vector)
                    if vector_id:
                        saved_count += 1
                except Exception as e:
                    logger.warning(f"Ошибка при сохранении вектора: {e}")
                    continue
            
            logger.info(f"Успешно сохранено {saved_count}/{len(vectors_to_save)} векторов")
            
            # Обновляем кэш
            self.document_cache[doc_name] = {
                "level_0": level_0_chunks,
                "level_1": hierarchical_doc["level_1_summaries"],
                "level_2": hierarchical_doc["level_2_summary"],
                "vectors_cached": True,
                "metadata": hierarchical_doc["metadata"]
            }
            
            return saved_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка при индексировании документа '{doc_name}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def smart_search_async(
        self,
        query: str,
        k: int = 12,
        search_strategy: str = "auto"
    ) -> List[Dict[str, Any]]:
        """
        Умный поиск с адаптивной стратегией
        
        Args:
            query: Поисковый запрос
            k: Количество результатов
            search_strategy: "auto", "summary", "detailed"
        
        Returns:
            List[Dict]: Результаты поиска
        """
        logger.info(f"Умный поиск: '{query[:50]}...' (стратегия: {search_strategy})")
        
        # Определяем стратегию автоматически
        if search_strategy == "auto":
            query_lower = query.lower()
            summary_keywords = [
                'саммари', 'summary', 'краткое содержание', 'обзор', 'резюме',
                'о чем документ', 'основная тема', 'содержание документа'
            ]
            
            if any(keyword in query_lower for keyword in summary_keywords):
                search_strategy = "summary"
            else:
                search_strategy = "detailed"
        
        logger.info(f"Выбрана стратегия: {search_strategy}")
        
        # Генерируем эмбеддинг запроса
        query_embedding = self.embeddings_model.embed_query(query)
        
        if search_strategy == "summary":
            # БЫСТРЫЙ ПОИСК: только по Level 2 и Level 1
            # Получаем больше результатов для фильтрации
            limit_search = k * 3
            results_all = await self.vector_repo.similarity_search(
                query_embedding,
                limit=limit_search
            )
            
            # Фильтруем по Level 2 и Level 1
            results_l2 = []
            results_l1 = []
            for vector, similarity in results_all:
                vector_type = vector.metadata.get("type", "")
                if vector_type == "full_summary":
                    results_l2.append((vector, similarity))
                elif vector_type == "intermediate_summary":
                    results_l1.append((vector, similarity))
            
            # Берем топ результатов
            results_l2 = results_l2[:min(k, 3)]
            results_l1 = results_l1[:k]
            
            # Объединяем результаты
            all_results = results_l2 + results_l1
            logger.info(f"Найдено результатов (summary): L2={len(results_l2)}, L1={len(results_l1)}")
        
        else:
            # ДЕТАЛЬНЫЙ ПОИСК: по всем уровням с приоритетом Level 0
            results = await self.vector_repo.similarity_search(
                query_embedding,
                limit=k * 3  # Берем больше для лучшего покрытия больших документов
            )
            all_results = results
            logger.info(f"Найдено результатов (detailed): {len(all_results)}")
        
        # Форматируем результаты
        # Используем ВСЕ найденные результаты для лучшего покрытия больших документов
        formatted_results = []
        for vector, similarity in all_results:  # Убрали [:k] - используем все найденные
            result = {
                "content": vector.content,
                "source": vector.metadata.get("source", "unknown"),
                "chunk": vector.chunk_index,
                "similarity": similarity,
                "level": vector.metadata.get("level", 0),
                "type": vector.metadata.get("type", "unknown")
            }
            formatted_results.append(result)
        
        logger.info(f"Умный поиск вернул {len(formatted_results)} результатов")
        return formatted_results
