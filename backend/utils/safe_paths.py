"""
Валидация путей к файлам (CWE-73) и санитизация значений для журналов (CWE-117).
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Union

_UNSAFE_PATH_PARTS = frozenset({".", ".."})
_LOG_UNSAFE_CHARS = re.compile(r"[\r\n\x00]")


def default_app_root() -> Path:
    if Path("/app").is_dir():
        return Path("/app")
    return Path(__file__).resolve().parent.parent.parent


def sanitize_log_value(value: object) -> str:
    """Убирает переводы строк и NUL из значений, попадающих в журнал (CWE-117)."""
    return _LOG_UNSAFE_CHARS.sub(" ", str(value))


def resolve_path_under_base(
    raw_path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    *,
    create_parent: bool = False,
) -> Optional[Path]:
    """
    Разрешает путь относительно base_dir и отклоняет выход за его пределы.
    Компоненты "." и ".." в исходном пути запрещены.
    """
    text = str(raw_path).strip()
    if not text:
        return None

    base = Path(base_dir).resolve() if base_dir is not None else default_app_root().resolve()
    candidate = Path(text).expanduser()

    if any(part in _UNSAFE_PATH_PARTS for part in candidate.parts):
        return None

    try:
        resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (base / candidate).resolve(strict=False)
    except (OSError, RuntimeError):
        return None

    try:
        resolved.relative_to(base)
    except ValueError:
        return None

    if create_parent:
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

    return resolved


def _resolve_dir_from_env(env_name: str, default: Path, base: Path) -> Path:
    env_value = os.getenv(env_name)
    if env_value:
        resolved = resolve_path_under_base(env_value, base, create_parent=True)
        if resolved is not None:
            return resolved
    default.mkdir(parents=True, exist_ok=True)
    return default


def is_writable_path(path: Path) -> bool:
    """Проверяет, можно ли создать/записать файл по указанному пути."""
    directory = path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        if not directory.is_dir():
            return False
    return os.access(directory, os.W_OK)


def default_logs_dir() -> Path:
    base = default_app_root()
    return _resolve_dir_from_env("BACKEND_LOG_DIR", base / "logs", base)


def default_context_prompts_dir() -> Path:
    base = default_app_root()
    preferred = Path("/app/memory") if Path("/app").is_dir() else base / "memory"
    return _resolve_dir_from_env("CONTEXT_PROMPTS_DIR", preferred, base)


def resolve_log_file_path(raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None
    logs_dir = default_logs_dir()
    resolved = resolve_path_under_base(raw_path, logs_dir.parent, create_parent=True)
    if resolved is None:
        return None
    try:
        resolved.relative_to(logs_dir.parent)
    except ValueError:
        return None
    if not is_writable_path(resolved):
        return None
    return resolved


def resolve_context_prompts_file_path(raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None
    bases = (
        default_context_prompts_dir().parent,
        Path(tempfile.gettempdir()) / "astrachat",
    )
    for base in bases:
        resolved = resolve_path_under_base(raw_path, base, create_parent=True)
        if resolved is not None:
            return resolved
    return None


def resolve_config_file_path(raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None
    resolved = resolve_path_under_base(raw_path, default_app_root())
    if resolved is None or not resolved.is_file():
        return None
    if resolved.suffix.lower() not in {".yml", ".yaml"}:
        return None
    return resolved
