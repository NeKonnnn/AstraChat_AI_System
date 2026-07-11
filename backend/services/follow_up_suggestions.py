"""Генерация динамических follow-up подсказок на основе контекста диалога."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from backend.settings.logging import get_logger

logger = get_logger(__name__)

FOLLOW_UP_SYSTEM_PROMPT = """Ты генерируешь follow-up подсказки для чата.
На основе диалога предложи ровно 3 коротких следующих шага пользователя.
Верни ТОЛЬКО валидный JSON-массив без markdown и пояснений:
[{"title":"...","subtitle":"...","content":"..."}]
- title: 1-4 слова, тема кнопки
- subtitle: опционально, до 6 слов уточнения (можно пустую строку)
- content: готовое сообщение пользователя на русском языке (1-2 предложения)
Подсказки должны быть релевантны последнему ответу ассистента и логично продолжать диалог."""

_MAX_HISTORY_MESSAGES = 12
_MAX_MESSAGE_CHARS = 2000
_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")


def _truncate(text: str, limit: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _build_dialogue_prompt(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in messages[-_MAX_HISTORY_MESSAGES:]:
        role = item.get("role", "user")
        label = "Пользователь" if role == "user" else "Ассистент"
        content = _truncate(item.get("content", ""), _MAX_MESSAGE_CHARS)
        if not content:
            continue
        lines.append(f"{label}: {content}")
    return "\n\n".join(lines)


def _parse_suggestions(raw: str) -> list[dict[str, str]]:
    text = (raw or "").strip()
    if not text:
        return []

    candidates = [text]
    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        candidates.insert(0, obj_match.group(0))
    match = _JSON_ARRAY_RE.search(text)
    if match:
        candidates.insert(0, match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            follow_ups = parsed.get("follow_ups")
            if isinstance(follow_ups, list):
                result: list[dict[str, str]] = []
                for idx, item in enumerate(follow_ups[:5]):
                    question = str(item).strip()
                    if not question:
                        continue
                    result.append(
                        {
                            "id": f"follow-up-{idx}",
                            "title": question,
                            "subtitle": "",
                            "content": question,
                        }
                    )
                if result:
                    return result[:5]

        if not isinstance(parsed, list):
            continue

        result = []
        for idx, item in enumerate(parsed[:5]):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            content = str(item.get("content", "")).strip()
            if not title or not content:
                continue
            subtitle = str(item.get("subtitle", "")).strip() or None
            result.append(
                {
                    "id": f"follow-up-{idx}",
                    "title": title,
                    "subtitle": subtitle or "",
                    "content": content,
                }
            )
        if result:
            return result[:3]
    return []


def _generate_sync(
    *,
    ask_agent: Any,
    messages: list[dict[str, str]],
    model_path: str | None,
) -> list[dict[str, str]]:
    dialogue = _build_dialogue_prompt(messages)
    if not dialogue:
        return []

    prompt = (
        "Проанализируй диалог ниже и сгенерируй 3 follow-up подсказки для пользователя.\n\n"
        f"{dialogue}"
    )

    response = ask_agent(
        prompt,
        history=None,
        max_tokens=512,
        streaming=False,
        model_path=model_path,
        system_prompt=FOLLOW_UP_SYSTEM_PROMPT,
        temperature=0.6,
        enable_thinking=False,
    )
    if not response:
        return []
    return _parse_suggestions(str(response))


async def generate_follow_up_suggestions(
    *,
    ask_agent: Any,
    messages: list[dict[str, str]],
    model_path: str | None,
) -> list[dict[str, str]]:
    if not ask_agent:
        return []
    try:
        return await asyncio.to_thread(
            _generate_sync,
            ask_agent=ask_agent,
            messages=messages,
            model_path=model_path,
        )
    except Exception:
        logger.exception("follow-up suggestions generation failed")
        return []
