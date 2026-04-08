"""
Поиск и идентификаторы GGUF под /app/models (включая подпапки llm/, llama/ и т.д.).
"""

import os
from typing import Any, Dict, List, Optional

MODELS_ROOT = os.environ.get("LLM_MODELS_ROOT", "/app/models")


def gguf_model_id_for_path(abs_path: str, root: str = MODELS_ROOT) -> str:
    """Стабильный id для API: файлы только в models/llm/<name>.gguf -> id=<name>; иначе относительный путь без .gguf"""
    try:
        ap = os.path.abspath(abs_path)
        rt = os.path.abspath(root)
        rel = os.path.relpath(ap, rt).replace("\\", "/")
    except ValueError:
        rel = os.path.basename(abs_path)
    if rel.lower().endswith(".gguf"):
        rel = rel[:-5]
    parts = rel.split("/")
    if len(parts) == 2 and parts[0] == "llm":
        return parts[1]
    return rel


def resolve_gguf_path(model_id: str, root: str = MODELS_ROOT) -> Optional[str]:
    """Путь к файлу .gguf по id из списка моделей или короткому имени (legacy: только llm/)"""
    mid = (model_id or "").strip().replace("\\", "/")
    if not mid:
        return None
    if mid.lower().endswith(".gguf"):
        mid = mid[:-5]

    cand = os.path.join(root, mid.replace("/", os.sep) + ".gguf")
    if os.path.isfile(cand):
        return cand

    cand_llm = os.path.join(root, "llm", os.path.basename(mid) + ".gguf")
    if os.path.isfile(cand_llm):
        return cand_llm

    stem = os.path.basename(mid)
    hits: List[str] = []
    if not os.path.isdir(root):
        return None
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if not fn.lower().endswith(".gguf"):
                continue
            if os.path.splitext(fn)[0] == stem:
                hits.append(os.path.join(dp, fn))
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]

    def sort_key(p: str) -> tuple:
        n = p.replace("\\", "/")
        return (0 if "/llm/" in n else 1, n)

    hits.sort(key=sort_key)
    return hits[0]


def list_gguf_models(root: str = MODELS_ROOT) -> List[Dict[str, Any]]:
    """Все .gguf под root с полями как в OpenAI-style list models"""
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(root):
        return out
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if not fn.lower().endswith(".gguf"):
                continue
            fp = os.path.join(dp, fn)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            mid = gguf_model_id_for_path(fp, root)
            out.append(
                {
                    "id": mid,
                    "object": "model",
                    "owned_by": "local",
                    "permissions": [],
                    "path": fp,
                    "size": sz,
                    "size_mb": round(sz / (1024 * 1024), 2),
                }
            )
    return out
