"""Дедупликация и постобработка списков хитов RAG."""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple


def _normalize_for_overlap(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _word_jaccard(a: str, b: str) -> float:
    wa = set(re.findall(r"[\w\u0400-\u04FF]+", a, re.UNICODE))
    wb = set(re.findall(r"[\w\u0400-\u04FF]+", b, re.UNICODE))
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union else 0.0


def dedupe_rag_hits(
    hits: List[Tuple[str, float, Optional[int], Optional[int]]],
    *,
    jaccard_threshold: float = 0.88,
    max_hits: Optional[int] = None,
) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
    """
    Убирает дубликаты по (document_id, chunk_index) и почти совпадающий текст (Jaccard по словам).
    Порядок входа сохраняется: оставляем первый (обычно лучший по score).
    """
    if not hits:
        return []
    seen_keys: Set[Tuple[Optional[int], Optional[int]]] = set()
    kept_norms: List[str] = []
    out: List[Tuple[str, float, Optional[int], Optional[int]]] = []
    for content, score, doc_id, chunk_idx in hits:
        key = (doc_id, chunk_idx)
        if key in seen_keys and key != (None, None):
            continue
        if key != (None, None):
            seen_keys.add(key)
        norm = _normalize_for_overlap(content or "")
        if norm and len(norm) > 40:
            if any(_word_jaccard(norm, prev) >= jaccard_threshold for prev in kept_norms):
                continue
            kept_norms.append(norm)
        out.append((content, score, doc_id, chunk_idx))
        if max_hits is not None and len(out) >= max_hits:
            break
    return out
