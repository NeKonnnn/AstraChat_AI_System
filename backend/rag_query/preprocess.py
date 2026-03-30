"""Лёгкая нормализация запроса (ru/en), без агрессивного удаления стоп-слов."""

from __future__ import annotations

import re
import unicodedata


def normalize_query(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text.strip())
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t
