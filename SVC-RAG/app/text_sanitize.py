"""Подготовка строк для PostgreSQL (encoding UTF-8)."""


def strip_null_bytes(text: str) -> str:
    """U+0000 в TEXT/VARCHAR даёт CharacterNotInRepertoireError у asyncpg/PostgreSQL."""
    if not text:
        return text
    return text.replace("\x00", "")
