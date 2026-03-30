"""Предобработка запроса: нормализация, опционально опечатки, HyDE, multi-query, фильтры."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.rag_query.metadata_filters import extract_filters_from_query
from backend.rag_query.preprocess import normalize_query

logger = logging.getLogger(__name__)


@dataclass
class ProcessedQuery:
    original: str
    normalized: str
    query_for_search: str
    vector_query: Optional[str]
    multi_variants: Optional[List[str]]
    filters: Optional[Dict[str, Any]]


def _hyde_max_chars() -> int:
    try:
        return max(200, min(8000, int(os.getenv("RAG_HYDE_MAX_CHARS", "2000"))))
    except ValueError:
        return 2000


async def _llm_short(prompt: str, system: str, max_tokens: int = 512) -> str:
    from backend.agent_llm_svc import ask_agent

    loop = asyncio.get_running_loop()

    def _call() -> str:
        return ask_agent(
            prompt,
            history=[],
            streaming=False,
            system_prompt=system,
            max_tokens=max_tokens,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return await loop.run_in_executor(ex, _call)


async def process_user_query(
    user_text: str,
    *,
    fix_typos: bool = False,
    multi_query: bool = False,
    hyde: bool = False,
) -> ProcessedQuery:
    original = user_text or ""
    normalized = normalize_query(original)
    q = normalized

    if fix_typos:
        try:
            fixed = await _llm_short(
                "Исправь опечатки, не меняй смысл. Верни только исправленный текст запроса, одной строкой, без комментариев:\n\n"
                + q,
                "Ты нормализуешь пользовательский поисковый запрос.",
                max_tokens=256,
            )
            fixed = (fixed or "").strip().split("\n")[0].strip()
            if 2 < len(fixed) < len(q) * 3 and len(fixed) < 2000:
                q = fixed
        except Exception as e:
            logger.debug("RAG_QUERY_FIX_TYPOS: %s", e)

    filters = extract_filters_from_query(q)
    vector_query: Optional[str] = None
    multi_variants: Optional[List[str]] = None

    if multi_query:
        try:
            raw = await _llm_short(
                'Сгенерируй 3–5 коротких альтернативных формулировок для поиска по базе (тот же смысл и язык, что у запроса). '
                'Верни только JSON вида {"variants":["..."]} без markdown.\n\nЗапрос:\n'
                + q,
                "Отвечай только компактным JSON.",
                max_tokens=400,
            )
            m = re.search(r"\{[\s\S]*\}", raw or "")
            if m:
                data = json.loads(m.group())
                vars_ = data.get("variants") or []
                if isinstance(vars_, list) and vars_:
                    multi_variants = [str(x).strip() for x in vars_[:6] if str(x).strip()]
        except Exception as e:
            logger.debug("RAG_MULTI_QUERY_ENABLED: %s", e)

    # HyDE можно совмещать с multi-query: обогащённый vector_query уходит на первый запрос в merge (см. rag_client).
    if hyde:
        try:
            hyde = await _llm_short(
                "Напиши 1–3 коротких абзаца гипотетического ответа на запрос (как если бы ты знал тему). "
                "Не ссылайся на реальные документы, законы или источники по названию.\n\nЗапрос:\n"
                + q,
                "HyDE: гипотетический текст для плотного поиска.",
                max_tokens=400,
            )
            hyde = (hyde or "").strip()
            if len(hyde) > 30:
                cap = _hyde_max_chars()
                vector_query = f"{q}\n\n{hyde[:cap]}"
        except Exception as e:
            logger.debug("RAG_HYDE_ENABLED: %s", e)

    return ProcessedQuery(
        original=original,
        normalized=normalized,
        query_for_search=q,
        vector_query=vector_query,
        multi_variants=multi_variants,
        filters=filters,
    )
