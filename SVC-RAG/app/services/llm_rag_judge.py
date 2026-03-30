"""LLM-as-a-Judge: бинарная релевантность каждого чанка к запросу (OpenAI-совместимый chat)."""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MAX_PASSAGE_CHARS = 480


def _extract_json_object(text: str) -> Optional[Dict]:
    if not text:
        return None
    t = text.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", t)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


async def judge_chunk_relevance(query: str, passages: List[str]) -> tuple[List[bool], Optional[str]]:
    """
    Возвращает список флагов релевантности длины len(passages) и опциональное сообщение об ошибке.
    При сбое парсинга — все False.
    """
    if not passages:
        return [], None
    cfg = get_settings()
    if not getattr(cfg.rag, "eval_llm_judge_allowed", False):
        return [False] * len(passages), "LLM-judge отключён (RAG_EVAL_LLM_JUDGE_ALLOWED=false)"

    llm_cfg = cfg.llm_service
    lines: List[str] = []
    for i, p in enumerate(passages):
        snippet = (p or "").replace("\n", " ").strip()[:_MAX_PASSAGE_CHARS]
        lines.append(f"[{i}] {snippet}")
    user_prompt = (
        "Ты судья релевантности для RAG. По запросу пользователя отметь, помогает ли каждый фрагмент "
        "ответить на запрос (содержит по смыслу нужную информацию, не обязательно полный ответ).\n\n"
        f"Запрос:\n{query.strip()}\n\nФрагменты:\n"
        + "\n".join(lines)
        + "\n\nВерни ТОЛЬКО JSON вида {\"relevant\": [true/false, ...]} — массив ровно из "
        f"{len(passages)} булевых значений в порядке индексов 0..{len(passages) - 1}."
    )

    try:
        async with httpx.AsyncClient(timeout=llm_cfg.timeout) as client:
            r = await client.post(
                f"{llm_cfg.base_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": llm_cfg.default_model,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.0,
                    "max_tokens": 512,
                    "stream": False,
                },
            )
            r.raise_for_status()
            data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        parsed = _extract_json_object(content)
        if not parsed or "relevant" not in parsed:
            logger.warning("[SVC-RAG] LLM-judge: не удалось разобрать JSON из ответа модели")
            return [False] * len(passages), "parse_error"
        rel = parsed["relevant"]
        if not isinstance(rel, list):
            return [False] * len(passages), "relevant_not_list"
        out: List[bool] = []
        for i in range(len(passages)):
            if i < len(rel):
                out.append(bool(rel[i]))
            else:
                out.append(False)
        return out, None
    except Exception as e:
        logger.warning("[SVC-RAG] LLM-judge: запрос к LLM не удался: %s", e)
        return [False] * len(passages), str(e)
