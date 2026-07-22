"""
Сохранение исходников RAG в PVC (/ragdb) вместо MinIO.

Структура:
  {RAG_PVC_DIR}/{memory|project|agent}/{username}/{yyyy}/{mm}/{dd}/{prefix}{uuid}{ext}

Env (ConfigMap/Deployment astra-chat-backend):
  RAG_USE_PVC=true|false  — переключатель MinIO ↔ PVC
  RAG_PVC_DIR=/ragdb      — mountPath PVC
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from backend.settings.logging import get_logger
from backend.settings.logging.errors import logged_suppress

logger = get_logger(__name__)

RAG_USE_PVC_ENV = "RAG_USE_PVC"
RAG_PVC_DIR_ENV = "RAG_PVC_DIR"
# Маркер bucket в metadata SVC-RAG: файл лежит в PVC, не в MinIO.
RAG_PVC_BUCKET_MARKER = "__pvc_rag__"

RagPvcScope = Literal["memory", "project", "agent"]
_VALID_SCOPES = frozenset({"memory", "project", "agent"})


def use_rag_pvc() -> bool:
    """True — исходники RAG пишем в PVC; False — в MinIO (как раньше)."""
    return (os.getenv(RAG_USE_PVC_ENV) or "false").strip().lower() in ("1", "true", "yes", "on")


def rag_pvc_root(*, required: bool = True) -> Optional[str]:
    """Корень PVC RAG — только из env RAG_PVC_DIR."""
    base = (os.getenv(RAG_PVC_DIR_ENV) or "").strip()
    if not base:
        if required:
            logger.error(
                "%s не задан — укажите путь PVC RAG в ConfigMap/Deployment пода astra-chat-backend "
                "(ожидается mountPath, например /ragdb)",
                RAG_PVC_DIR_ENV,
            )
        return None
    os.makedirs(base, exist_ok=True)
    return base


def _sanitize_user_dir(username: str) -> str:
    raw = (username or "").strip()
    if not raw:
        return "anonymous"
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", raw)
    if not safe:
        logger.warning(
            "RAG PVC: логин %r не содержит допустимых символов для имени каталога — используется anonymous",
            raw,
        )
        return "anonymous"
    return safe


def _date_dir(*, now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return f"{dt.strftime('%Y')}/{dt.strftime('%m')}/{dt.strftime('%d')}"


def _normalize_object_key(object_name: str) -> Optional[str]:
    raw = str(object_name or "").strip().replace("\\", "/")
    parts = [part for part in raw.split("/") if part and part not in (".", "..")]
    if not parts:
        return None
    return "/".join(parts)


def build_rag_pvc_storage_dir(
    scope: RagPvcScope,
    username: str,
    *,
    now: datetime | None = None,
) -> Optional[str]:
    """{RAG_PVC_DIR}/{scope}/{user}/{yyyy}/{mm}/{dd}/"""
    if scope not in _VALID_SCOPES:
        logger.error("RAG PVC: неизвестный scope=%r", scope)
        return None
    base = rag_pvc_root()
    if not base:
        return None
    storage_dir = os.path.join(base, scope, _sanitize_user_dir(username), *_date_dir(now=now).split("/"))
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def rag_pvc_file_path(object_name: str) -> Optional[str]:
    """Безопасный абсолютный путь к файлу в RAG_PVC_DIR (защита от path traversal)."""
    rel_key = _normalize_object_key(object_name)
    if not rel_key:
        return None
    root_dir = rag_pvc_root(required=False)
    if not root_dir:
        return None
    root = os.path.realpath(root_dir)
    full_path = os.path.realpath(os.path.join(root, *rel_key.split("/")))
    if full_path != root and not full_path.startswith(root + os.sep):
        return None
    return full_path if os.path.isfile(full_path) else None


def is_rag_pvc_bucket(bucket: Optional[str]) -> bool:
    return (bucket or "").strip() == RAG_PVC_BUCKET_MARKER


def _is_rag_pvc_file_entry(val: Any) -> bool:
    return isinstance(val, dict) and "name" in val


def _collect_rag_pvc_files(
    scan_root: str,
    *,
    highlight_object: str | None = None,
    path_prefix: str = "",
) -> tuple[list[dict], int]:
    """Собирает файлы под scan_root; name — относительный путь от корня PVC (с path_prefix)."""
    highlight_rel = _normalize_object_key(highlight_object) if highlight_object else None
    files: list[dict] = []
    total_bytes = 0
    for dirpath, _, filenames in os.walk(scan_root):
        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_under_scan = os.path.relpath(full_path, scan_root).replace("\\", "/")
            rel_path = f"{path_prefix}/{rel_under_scan}".strip("/") if path_prefix else rel_under_scan
            size: int | None
            modified: str | None
            try:
                stat = os.stat(full_path)
                size = int(stat.st_size)
                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                total_bytes += size
            except OSError:
                size = None
                modified = None
            files.append(
                {
                    "name": rel_path,
                    "size": size,
                    "modified": modified,
                    "just_added": bool(highlight_rel and rel_path == highlight_rel),
                }
            )
    files.sort(key=lambda item: item["name"])
    return files, total_bytes


def _build_rag_pvc_nested_tree(files: list[dict]) -> dict:
    nested: dict = {}
    for entry in files:
        parts = entry["name"].split("/")
        node = nested
        for part in parts[:-1]:
            child = node.get(part)
            if _is_rag_pvc_file_entry(child):
                node[part] = {"__shadow_file__": child}
                child = node[part]
            elif child is None:
                node[part] = {}
                child = node[part]
            node = child
        node[parts[-1]] = entry
    return nested


def _render_rag_pvc_tree_lines(files: list[dict]) -> list[str]:
    if not files:
        return ["  (empty)"]

    nested = _build_rag_pvc_nested_tree(files)
    lines: list[str] = []

    def render(node: dict, prefix: str) -> None:
        dir_keys = sorted(key for key, val in node.items() if isinstance(val, dict) and not _is_rag_pvc_file_entry(val))
        file_items = sorted(
            ((key, val) for key, val in node.items() if _is_rag_pvc_file_entry(val)),
            key=lambda item: item[0],
        )
        entries = [(key, True) for key in dir_keys] + [(key, False) for key, _ in file_items]
        for idx, (key, is_dir) in enumerate(entries):
            is_last = idx == len(entries) - 1
            branch = "└── " if is_last else "├── "
            if is_dir:
                lines.append(f"{prefix}{branch}{key}/")
                extension = "    " if is_last else "│   "
                render(node[key], prefix + extension)
            else:
                entry = node[key]
                display_key = os.path.basename(entry["name"]) if key == "__shadow_file__" else key
                size_part = f" ({entry['size']} B)" if isinstance(entry.get("size"), int) else ""
                marker = "  ← new" if entry.get("just_added") else ""
                lines.append(f"{prefix}{branch}{display_key}{size_part}{marker}")

    render(nested, "  ")
    return lines


def snapshot_rag_pvc_structure(
    *,
    scope: RagPvcScope | None = None,
    highlight_object: str | None = None,
) -> dict:
    """
    Снимок дерева PVC:
      /ragdb/{memory|project|agent}/{user}/{yyyy}/{mm}/{dd}/...
    Если задан scope — только подкаталог этого вида RAG.
    """
    root_dir = rag_pvc_root(required=False)
    if not root_dir:
        return {
            "rag_pvc_dir": None,
            "rag_pvc_dir_env": RAG_PVC_DIR_ENV,
            "scope": scope,
            "error": f"{RAG_PVC_DIR_ENV} не задан в окружении пода",
            "file_count": 0,
            "total_bytes": 0,
            "tree": f"({RAG_PVC_DIR_ENV} не задан)",
            "files": [],
        }

    if scope:
        if scope not in _VALID_SCOPES:
            return {
                "rag_pvc_dir": root_dir,
                "rag_pvc_dir_env": RAG_PVC_DIR_ENV,
                "scope": scope,
                "error": f"неизвестный scope={scope!r}",
                "file_count": 0,
                "total_bytes": 0,
                "tree": f"(неизвестный scope={scope!r})",
                "files": [],
            }
        scan_root = os.path.join(root_dir, scope)
        path_prefix = scope
        tree_root_label = f"{root_dir}/{scope}/"
        os.makedirs(scan_root, exist_ok=True)
    else:
        scan_root = root_dir
        path_prefix = ""
        tree_root_label = f"{root_dir}/"

    try:
        files, total_bytes = _collect_rag_pvc_files(
            scan_root, highlight_object=highlight_object, path_prefix=path_prefix
        )
    except OSError as exc:
        return {
            "rag_pvc_dir": root_dir,
            "rag_pvc_dir_env": RAG_PVC_DIR_ENV,
            "scope": scope,
            "error": str(exc),
            "file_count": 0,
            "total_bytes": 0,
            "tree": f"{tree_root_label}\n  (ошибка чтения: {exc})",
            "files": [],
        }

    # Для scoped-снимка в дереве показываем пути относительно scope (без дубля «memory/…»).
    render_files = files
    if scope and path_prefix:
        prefix = f"{path_prefix}/"
        render_files = [
            {**entry, "name": entry["name"][len(prefix) :] if entry["name"].startswith(prefix) else entry["name"]}
            for entry in files
        ]
        if highlight_object:
            hl = _normalize_object_key(highlight_object) or ""
            if hl.startswith(prefix):
                hl_under = hl[len(prefix) :]
                for entry in render_files:
                    entry["just_added"] = entry["name"] == hl_under

    tree_lines = [tree_root_label, *_render_rag_pvc_tree_lines(render_files)]
    return {
        "rag_pvc_dir": root_dir,
        "rag_pvc_dir_env": RAG_PVC_DIR_ENV,
        "scope": scope,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "tree": "\n".join(tree_lines),
        "files": files,
        "highlight_object": highlight_object,
    }


def log_rag_pvc_structure(
    *,
    filename: str,
    scope: RagPvcScope,
    highlight_object: str | None = None,
    stage: str = "rag-pvc-storage-structure",
) -> None:
    """INFO-лог древовидной структуры PVC для вида RAG (memory/project/agent)."""
    structure = snapshot_rag_pvc_structure(scope=scope, highlight_object=highlight_object)
    logger.info(
        "[RAG PVC] %s scope=%s filename=%s files=%s bytes=%s\n%s",
        stage,
        scope,
        filename,
        structure.get("file_count", 0),
        structure.get("total_bytes", 0),
        structure.get("tree", ""),
    )


def save_rag_bytes_to_pvc(
    content: bytes,
    filename: str,
    *,
    scope: RagPvcScope,
    username: str,
    prefix: str,
    content_type: str = "application/octet-stream",
) -> Optional[str]:
    """
    Пишет файл в PVC. Возвращает относительный ключ
    ``{scope}/{user}/{yyyy}/{mm}/{dd}/{prefix}{uuid}{ext}`` или None при ошибке.
    CEF FS009/FS010 вызываются здесь.
    """
    from backend.settings.cef_logger.storage_audit import log_rag_pvc_write_failure, log_rag_pvc_write_success

    storage_dir = build_rag_pvc_storage_dir(scope, username)
    base_dir = rag_pvc_root(required=False)
    display = filename or "unknown"
    fsize = len(content or b"")
    if not storage_dir or not base_dir:
        log_rag_pvc_write_failure(
            display,
            f"{RAG_PVC_DIR_ENV} не задан или каталог недоступен",
            scope=scope,
            file_size=fsize,
        )
        log_rag_pvc_structure(filename=display, scope=scope, stage="rag-pvc-storage-structure-save-failed")
        return None
    if not content:
        log_rag_pvc_write_failure(display, "пустой файл", scope=scope, file_size=0)
        log_rag_pvc_structure(filename=display, scope=scope, stage="rag-pvc-storage-structure-rejected-empty")
        return None

    ext = os.path.splitext(display)[1].lower() or ".bin"
    safe_prefix = re.sub(r"[^a-zA-Z0-9._-]", "_", (prefix or "rag_").strip()) or "rag_"
    if not safe_prefix.endswith("_"):
        safe_prefix = f"{safe_prefix}_"
    stored_name = f"{safe_prefix}{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(storage_dir, stored_name)
    try:
        with open(full_path, "wb") as out:
            out.write(content)
        rel_key = os.path.relpath(full_path, base_dir).replace("\\", "/")
        logger.info(
            "RAG PVC: сохранён scope=%s user=%s path=%s ctype=%s size=%s",
            scope,
            _sanitize_user_dir(username),
            full_path,
            content_type or "application/octet-stream",
            fsize,
        )
        log_rag_pvc_write_success(
            display,
            object_key=rel_key,
            scope=scope,
            file_size=fsize,
        )
        log_rag_pvc_structure(
            filename=display,
            scope=scope,
            highlight_object=rel_key,
            stage="rag-pvc-storage-structure",
        )
        return rel_key
    except Exception as exc:
        logger.exception("RAG PVC save error filename=%s scope=%s user=%s", display, scope, username)
        log_rag_pvc_write_failure(display, str(exc), scope=scope, file_size=fsize)
        log_rag_pvc_structure(filename=display, scope=scope, stage="rag-pvc-storage-structure-save-failed")
        return None


def delete_rag_pvc_file(object_name: Optional[str], bucket: Optional[str] = None) -> None:
    """Удаляет файл из PVC, если bucket — маркер PVC (или bucket не указан, но ключ валиден)."""
    if bucket is not None and not is_rag_pvc_bucket(bucket):
        return
    path = rag_pvc_file_path(object_name or "")
    if not path:
        return
    with logged_suppress(logger):
        os.remove(path)
        logger.info("RAG PVC: удалён файл %s", path)
