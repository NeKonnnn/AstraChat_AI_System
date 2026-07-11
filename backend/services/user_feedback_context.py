"""
Сборка блока предпочтений пользователя из лайков/дизлайков сообщений
для инъекции в system prompt / контекст LLM.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Человекочитаемые подписи тегов (синхрон с frontend)
DISLIKE_TAG_LABELS: Dict[str, str] = {
    "did_not_follow_instructions": "Не полностью следовал инструкциям",
    "dislike_style": "Не нравится стиль",
    "inaccurate": "Неточный / фактические ошибки",
    "too_verbose": "Слишком длинный / многословный",
    "too_short": "Слишком короткий / неполный",
    "irrelevant": "Нерелевантный ответ",
    "biased": "Пристрастный",
    "safety_or_legal": "Вопросы безопасности или правовых рисков",
    "other": "Другое",
}


def _tag_label(tag: str) -> str:
    return DISLIKE_TAG_LABELS.get(tag, tag)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
        except Exception:
            pass
    return datetime.min


def _extract_feedback_entries(messages: List[Any]) -> List[Dict[str, Any]]:
    """Достаёт feedback из сообщений и multi-LLM слотов."""
    entries: List[Dict[str, Any]] = []
    for msg in messages or []:
        meta = getattr(msg, "metadata", None)
        if meta is None and isinstance(msg, dict):
            meta = msg.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}

        fb = meta.get("feedback")
        if isinstance(fb, dict) and fb.get("rating") in ("like", "dislike"):
            entries.append(
                {
                    "rating": fb.get("rating"),
                    "tags": list(fb.get("tags") or []),
                    "comment": (fb.get("comment") or "").strip(),
                    "updated_at": fb.get("updated_at") or getattr(msg, "timestamp", None),
                    "content_preview": (getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "") or "")[
                        :180
                    ],
                }
            )

        slots = meta.get("multi_llm_responses") or meta.get("multiLLMResponses") or []
        if isinstance(slots, list):
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                slot_fb = slot.get("feedback")
                if isinstance(slot_fb, dict) and slot_fb.get("rating") in ("like", "dislike"):
                    entries.append(
                        {
                            "rating": slot_fb.get("rating"),
                            "tags": list(slot_fb.get("tags") or []),
                            "comment": (slot_fb.get("comment") or "").strip(),
                            "updated_at": slot_fb.get("updated_at") or getattr(msg, "timestamp", None),
                            "content_preview": (slot.get("content") or "")[:180],
                            "model": slot.get("model"),
                        }
                    )
    return entries


def format_feedback_system_block(entries: List[Dict[str, Any]], *, max_items: int = 8) -> Optional[str]:
    """Формирует текстовый блок для system prompt."""
    if not entries:
        return None

    sorted_entries = sorted(entries, key=lambda e: _parse_ts(e.get("updated_at")), reverse=True)
    likes = [e for e in sorted_entries if e.get("rating") == "like"][: max(1, max_items // 2)]
    dislikes = [e for e in sorted_entries if e.get("rating") == "dislike"][:max_items]

    if not likes and not dislikes:
        return None

    lines: List[str] = [
        "[Обратная связь пользователя по прошлым ответам]",
        "Учитывай эти предпочтения при формировании текущего ответа. "
        "Не упоминай этот блок явно, просто адаптируй стиль и содержание.",
    ]

    if dislikes:
        lines.append("")
        lines.append("Плохие ответы (избегай подобного):")
        for e in dislikes:
            tags = e.get("tags") or []
            tag_text = ", ".join(_tag_label(t) for t in tags) if tags else "без уточнения причины"
            comment = e.get("comment") or ""
            preview = (e.get("content_preview") or "").replace("\n", " ").strip()
            piece = f"- Причины: {tag_text}."
            if comment:
                piece += f" Комментарий пользователя: «{comment}»."
            if preview:
                piece += f" Фрагмент ответа: «{preview[:120]}»."
            lines.append(piece)

    if likes:
        lines.append("")
        lines.append("Хорошие ответы (ориентируйся на подобный стиль и полезность):")
        for e in likes:
            comment = e.get("comment") or ""
            preview = (e.get("content_preview") or "").replace("\n", " ").strip()
            piece = "- Пользователь отметил ответ как хороший."
            if comment:
                piece += f" Комментарий: «{comment}»."
            if preview:
                piece += f" Фрагмент: «{preview[:120]}»."
            lines.append(piece)

    return "\n".join(lines)


def merge_feedback_into_system_prompt(
    system_prompt: Optional[str], feedback_block: Optional[str]
) -> Optional[str]:
    block = (feedback_block or "").strip()
    if not block:
        return system_prompt
    base = (system_prompt or "").strip()
    if base:
        return f"{base}\n\n{block}"
    return block


async def collect_user_feedback_entries(
    user_id: str,
    *,
    conversation_id: Optional[str] = None,
    limit_conversations: int = 15,
    max_entries: int = 12,
) -> List[Dict[str, Any]]:
    """Собирает недавние feedback-записи пользователя из MongoDB."""
    if not user_id:
        return []
    try:
        from backend.app_state import get_conversation_repository

        repo = get_conversation_repository()
        if repo is None:
            return []

        entries: List[Dict[str, Any]] = []

        if conversation_id:
            conv = await repo.get_conversation(conversation_id)
            if conv and getattr(conv, "messages", None):
                entries.extend(_extract_feedback_entries(conv.messages))

        conversations = await repo.get_user_conversations(user_id, limit=limit_conversations, skip=0)
        for conv in conversations:
            if conversation_id and getattr(conv, "conversation_id", None) == conversation_id:
                continue
            entries.extend(_extract_feedback_entries(getattr(conv, "messages", None) or []))

        seen = set()
        unique: List[Dict[str, Any]] = []
        for e in sorted(entries, key=lambda x: _parse_ts(x.get("updated_at")), reverse=True):
            key = (
                e.get("rating"),
                tuple(e.get("tags") or []),
                e.get("comment") or "",
                (e.get("content_preview") or "")[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
            if len(unique) >= max_entries:
                break
        return unique
    except Exception:
        logger.exception("Не удалось собрать feedback пользователя %s", user_id)
        return []


async def build_user_feedback_system_block(
    user_id: Optional[str],
    *,
    conversation_id: Optional[str] = None,
    max_items: int = 8,
) -> Optional[str]:
    if not user_id:
        return None
    entries = await collect_user_feedback_entries(
        user_id, conversation_id=conversation_id, max_entries=max_items + 4
    )
    return format_feedback_system_block(entries, max_items=max_items)
