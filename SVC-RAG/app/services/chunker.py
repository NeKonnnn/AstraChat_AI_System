"""Разбиение текста на чанки для RAG.

Два уровня нарезки:
1. Структурный: сначала делим по заголовкам, номерам разделов, разрывам страниц,
   чтобы один чанк не охватывал два разных смысловых блока. Таблицы и списки
   по возможности не дробим на середине строки.
2. Размерный: если секция слишком большая — доразбиваем её
   ``RecursiveCharacterTextSplitter`` с приоритетом естественных границ.

API:
- ``split_into_chunks(text)`` — обратно совместимый список строк (использовался прежде).
- ``split_into_chunks_with_meta(text)`` — список (text, metadata), где metadata
  содержит связь чанка с разделом/заголовком (пригодится для атрибуции источников
  и для small-to-big retrieval в будущем, без миграции БД).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# Распознавание структурных границ. Порядок важен: от «крупных» разделителей к «мелким».
_HEADING_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*#{1,6}\s+.+$", re.MULTILINE),           # Markdown-заголовки
    re.compile(r"^\s*(?:Глава|Раздел|Часть)\s+\S.+$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}(?:\.\d{1,3}){0,4}\s+\S.+$", re.MULTILINE),  # 1.2.3 Заголовок
    re.compile(r"^\s*[IVXLC]{1,6}\.\s+\S.+$", re.MULTILINE),  # Римские цифры: II. Title
]

_PAGE_BREAK_PATTERN = re.compile(r"\n?-{2,}\s*Страница.*?-{2,}\s*\n?", re.IGNORECASE)
_TABLE_LINE_PATTERN = re.compile(r"^\s*\|.+\|\s*$")


def _split_by_page_breaks(text: str) -> List[str]:
    parts = _PAGE_BREAK_PATTERN.split(text)
    return [p for p in parts if p and p.strip()]


def _find_heading_positions(text: str) -> List[int]:
    """Позиции начала всех найденных заголовков, отсортированные."""
    positions: set = {0}
    for pat in _HEADING_PATTERNS:
        for m in pat.finditer(text):
            positions.add(m.start())
    return sorted(positions)


def _split_by_headings(text: str) -> List[str]:
    """Делит текст на секции по заголовкам. Пустые/коротенькие заголовки-строки
    склеиваются с последующим контентом, чтобы в секции всегда было тело.
    """
    if not text:
        return []
    positions = _find_heading_positions(text)
    if len(positions) <= 1:
        return [text]

    sections: List[str] = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        sec = text[pos:end].strip()
        if sec:
            sections.append(sec)
    return sections


def _protect_tables(section: str) -> List[str]:
    """Разбивает секцию на «блоки»: обычный текст и цельные таблицы.

    Цельная таблица — последовательность ≥ 2 строк, начинающихся и заканчивающихся "|".
    Таблицы не дробятся по размеру чанка; разбиваются только если сама таблица больше
    двух chunk_size (очень редкий случай).
    """
    lines = section.split("\n")
    blocks: List[str] = []
    buf: List[str] = []
    table_buf: List[str] = []
    in_table = False

    def flush_buf() -> None:
        if buf:
            blocks.append("\n".join(buf).strip())
            buf.clear()

    def flush_table() -> None:
        if table_buf:
            blocks.append("\n".join(table_buf).strip())
            table_buf.clear()

    for ln in lines:
        if _TABLE_LINE_PATTERN.match(ln):
            if not in_table:
                flush_buf()
                in_table = True
            table_buf.append(ln)
        else:
            if in_table:
                # Строка-разделитель/пустая в середине таблицы тоже считаем её частью,
                # если предыдущая и следующая строки — таблица. Здесь простая эвристика:
                # «пустая/разделитель ---» — добавляем в таблицу, иначе закрываем.
                if ln.strip() == "" or re.match(r"^\s*[-:|]+\s*$", ln):
                    table_buf.append(ln)
                    continue
                flush_table()
                in_table = False
            buf.append(ln)
    flush_table()
    flush_buf()
    return [b for b in blocks if b]


def _make_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=[
            "\n\n\n",
            "\n\n",
            "\n",
            ". ",
            "! ",
            "? ",
            "; ",
            ": ",
            ", ",
            " ",
            "",
        ],
    )


def split_into_chunks_with_meta(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Возвращает [(chunk_text, metadata)] со связью с разделом.

    metadata содержит:
      - ``section_index``   — порядковый номер секции (разделённой по заголовку/странице);
      - ``section_heading`` — первая строка секции (обычно заголовок);
      - ``chunk_of_section``— индекс этого чанка внутри своей секции;
      - ``is_table``        — True, если чанк — целая таблица.
    """
    if not text or not text.strip():
        return []

    cfg = get_settings().rag
    chunk_size = max(200, int(getattr(cfg, "chunk_size", 1000)))
    chunk_overlap = max(0, int(getattr(cfg, "chunk_overlap", 200)))
    splitter = _make_splitter(chunk_size, chunk_overlap)

    # 1. Крупная структура: страницы → заголовки.
    pages = _split_by_page_breaks(text.strip())
    sections: List[str] = []
    for page in pages:
        sections.extend(_split_by_headings(page))
    if not sections:
        sections = [text.strip()]

    out: List[Tuple[str, Dict[str, Any]]] = []
    for s_idx, section in enumerate(sections):
        head_line = section.split("\n", 1)[0].strip()[:200]
        blocks = _protect_tables(section)

        chunk_of_sec = 0
        for block in blocks:
            is_table = block.startswith("|") and "\n|" in block
            # Очень большие таблицы всё-таки делим, но реже — удваиваем chunk_size.
            effective_limit = chunk_size * 2 if is_table else chunk_size
            if len(block) <= effective_limit:
                out.append(
                    (
                        block,
                        {
                            "section_index": s_idx,
                            "section_heading": head_line,
                            "chunk_of_section": chunk_of_sec,
                            "is_table": is_table,
                        },
                    )
                )
                chunk_of_sec += 1
                continue
            for sub in splitter.split_text(block):
                sub_clean = sub.strip()
                if not sub_clean:
                    continue
                out.append(
                    (
                        sub_clean,
                        {
                            "section_index": s_idx,
                            "section_heading": head_line,
                            "chunk_of_section": chunk_of_sec,
                            "is_table": is_table,
                        },
                    )
                )
                chunk_of_sec += 1

    # Фильтр совсем мелких/пустых фрагментов, чтобы они не засоряли индекс.
    min_useful = max(20, int(getattr(cfg, "min_chunk_length", 40)) // 2)
    out = [(t, m) for t, m in out if len(t) >= min_useful]
    return out


def split_into_chunks(text: str) -> List[str]:
    """Обратно совместимый API — только тексты чанков (без metadata).

    Внутри используется новый структурный чанкер: заголовки, страницы, таблицы
    распознаются и не дробятся посередине. Если текст простой — поведение близко
    к прежнему ``RecursiveCharacterTextSplitter``.
    """
    return [t for t, _m in split_into_chunks_with_meta(text)]
