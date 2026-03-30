"""Опциональная проверка «опирается ли ответ на контекст» вторым вызовом LLM."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

import re

def strip_strict_not_found_message(answer: str, replacement: str) -> str:
    """
    Если модель вывела полезный ответ и одновременно добавила стандартную
    формулировку про отсутствие опоры, убираем именно эту формулировку.

    Важно: если ответ СОВПАДАЕТ с replacement целиком, ничего не меняем.
    """
    if not answer:
        return answer
    if not replacement:
        return answer

    ans = str(answer)
    rep = str(replacement)

    ans_stripped = ans.strip()
    rep_stripped = rep.strip()

    # Если ответ по сути "только про отсутствие", не трогаем.
    if ans_stripped == rep_stripped:
        return ans

    # Убираем replacement в случае, когда он добавлен хвостом/внутри.
    if rep_stripped and rep_stripped in ans:
        cleaned = ans.replace(rep, "").strip()
        if cleaned:
            return re.sub(r"[ ]{2,}", " ", cleaned)
        cleaned = ans.replace(rep_stripped, "").strip()
        if cleaned:
            return re.sub(r"[ ]{2,}", " ", cleaned)

    return ans


def post_verify_enabled() -> bool:
    v = os.getenv("RAG_POST_VERIFY", "").strip().lower()
    return v in ("1", "true", "yes", "on")


async def verify_answer_grounded(context_excerpt: str, answer: str) -> bool:
    from backend.agent_llm_svc import ask_agent

    ctx = (context_excerpt or "")[:12000]
    ans = (answer or "")[:8000]
    prompt = (
        "Ниже фрагменты CONTEXT и ответ ассистента. "
        "Можно ли считать, что все конкретные утверждения в ответе обоснованы CONTEXT "
        "(допускаются общие формулировки и перефраз)?\n"
        "Ответь строго одним словом: да или нет.\n\n"
        f"CONTEXT:\n{ctx}\n\nОТВЕТ:\n{ans}"
    )
    loop = asyncio.get_running_loop()

    def _call() -> str:
        return ask_agent(
            prompt,
            history=[],
            streaming=False,
            system_prompt="Ты строгий аудитор: отвечай только «да» или «нет».",
            max_tokens=8,
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            raw = (await loop.run_in_executor(ex, _call) or "").strip().lower()
        return raw.startswith("да") or raw.startswith("yes")
    except Exception as e:
        logger.warning("RAG_POST_VERIFY LLM error: %s", e)
        return True


async def maybe_replace_ungrounded(
    context_excerpt: str,
    answer: str,
    replacement: str,
) -> str:
    cleaned_answer = strip_strict_not_found_message(answer, replacement)
    if not post_verify_enabled():
        # Если пост-аудит выключен, просто убираем лишнюю “апологию”, если она примешана.
        return cleaned_answer

    # Если пост-аудит включён, проверяем grounding уже для “очищенного” ответа.
    # Иначе можно скрыть ситуацию, когда остальной текст не обоснован CONTEXT.
    ok = await verify_answer_grounded(context_excerpt, cleaned_answer)
    if ok:
        return cleaned_answer
    logger.info("[RAG_POST_VERIFY] ответ заменён стандартной формулировкой")
    return replacement
