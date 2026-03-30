"""Извлечение простых фильтров по дате/имени из текста запроса (эвристики ru/en)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


def extract_filters_from_query(text: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает dict для JSON filters в SVC-RAG или None.
    ISO datetime сериализуется httpx в JSON как строка — SVC-RAG Pydantic примет datetime.
    """
    if not text or len(text) > 4000:
        return None
    low = text.lower()
    now = datetime.utcnow()
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    if "прошл" in low and "год" in low:
        date_from = datetime(now.year - 1, 1, 1)
        date_to = datetime(now.year - 1, 12, 31, 23, 59, 59)
    elif "этот год" in low or "текущий год" in low:
        date_from = datetime(now.year, 1, 1)
        date_to = now
    elif "вчера" in low:
        d = (now - timedelta(days=1)).date()
        date_from = datetime.combine(d, datetime.min.time())
        date_to = datetime.combine(d, datetime.max.time())

    years = [int(y) for y in re.findall(r"\b(20[0-2]\d)\b", text)]
    if years and date_from is None:
        y = max(years)
        date_from = datetime(y, 1, 1)
        date_to = datetime(y, 12, 31, 23, 59, 59)

    filename_contains: Optional[str] = None
    m = re.search(
        r"(?:файл|file|документ|document)\s+['\"]?([^'\"]+\.(?:pdf|docx?|xlsx?|txt))['\"]?",
        text,
        re.I,
    )
    if m:
        filename_contains = m.group(1).strip()

    if date_from is None and date_to is None and not filename_contains:
        return None
    out: Dict[str, Any] = {}
    if date_from is not None:
        out["date_from"] = date_from.isoformat()
    if date_to is not None:
        out["date_to"] = date_to.isoformat()
    if filename_contains:
        out["filename_contains"] = filename_contains
    return out
