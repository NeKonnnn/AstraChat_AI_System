"""Пресеты моделей генерации изображений (workflow + checkpoint + node_map)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app_state import load_app_settings, save_app_settings
from backend.settings import get_settings

_USER_PRESETS_KEY = "image_generation_custom_presets"
_USER_DEFAULT_KEY = "image_generation_default_preset_id"


def _cfg():
    return get_settings().image_generation


def _preset_row(pid: str, preset: Any) -> Dict[str, Any]:
    if hasattr(preset, "model_dump"):
        row = preset.model_dump()
    elif isinstance(preset, dict):
        row = dict(preset)
    else:
        return {}
    row["id"] = str(row.get("id") or pid)
    return row


def _user_presets_from_settings() -> List[Dict[str, Any]]:
    data = load_app_settings()
    raw = data.get(_USER_PRESETS_KEY)
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not pid or not label:
            continue
        row = dict(item)
        row["id"] = pid
        row["custom"] = True
        out.append(row)
    return out


def list_configured_presets(*, include_custom: bool = True) -> List[Dict[str, Any]]:
    cfg = _cfg()
    presets_map = getattr(cfg, "presets", None) or {}
    out: List[Dict[str, Any]] = []
    if isinstance(presets_map, dict):
        for pid, preset in presets_map.items():
            row = _preset_row(str(pid), preset)
            if row.get("label"):
                row["custom"] = False
                out.append(row)
    if include_custom:
        out.extend(_user_presets_from_settings())
    return out


def resolve_preset(preset_id: Optional[str]) -> Optional[Dict[str, Any]]:
    cfg = _cfg()
    pid = (preset_id or "").strip()
    if not pid:
        saved = str(load_app_settings().get(_USER_DEFAULT_KEY) or "").strip()
        pid = saved or str(getattr(cfg, "default_preset_id", None) or "").strip()
    presets = list_configured_presets()
    if not presets:
        return None
    if pid:
        for p in presets:
            if p.get("id") == pid:
                return p
    return presets[0]


def resolve_preset_node_map(preset: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = _cfg()
    if preset and isinstance(preset.get("node_map"), dict) and preset["node_map"]:
        return preset["node_map"]
    return getattr(cfg, "node_map", None) or {}


def apply_preset_to_generation_params(
    preset: Optional[Dict[str, Any]],
    *,
    width: Optional[int],
    height: Optional[int],
    steps: Optional[int],
) -> Dict[str, Any]:
    cfg = _cfg()
    p = preset or {}
    return {
        "workflow_path": (p.get("workflow_path") or cfg.workflow_path or "").strip(),
        "checkpoint_name": (p.get("checkpoint_name") or cfg.checkpoint_name or "").strip(),
        "width": width if width is not None else int(p.get("default_width") or cfg.default_width or 512),
        "height": height if height is not None else int(p.get("default_height") or cfg.default_height or 512),
        "steps": steps if steps is not None else int(p.get("default_steps") or cfg.default_steps or 20),
        "preset_id": str(p.get("id") or ""),
        "preset_label": str(p.get("label") or ""),
        "node_map": resolve_preset_node_map(p),
    }


def save_user_presets(presets: List[Dict[str, Any]], default_preset_id: str = "") -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for item in presets:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        label = str(item.get("label") or "").strip()
        if not pid or not label:
            continue
        row = {
            "id": pid,
            "label": label,
            "description": str(item.get("description") or ""),
            "workflow_path": str(item.get("workflow_path") or ""),
            "checkpoint_name": str(item.get("checkpoint_name") or ""),
            "default_width": int(item.get("default_width") or 1024),
            "default_height": int(item.get("default_height") or 1024),
            "default_steps": int(item.get("default_steps") or 4),
        }
        nm = item.get("node_map")
        if isinstance(nm, dict) and nm:
            row["node_map"] = nm
        cleaned.append(row)
    updates: Dict[str, Any] = {_USER_PRESETS_KEY: cleaned}
    if default_preset_id:
        updates[_USER_DEFAULT_KEY] = default_preset_id.strip()
    save_app_settings(updates)
    return cleaned


def get_user_default_preset_id() -> str:
    saved = str(load_app_settings().get(_USER_DEFAULT_KEY) or "").strip()
    if saved:
        return saved
    return str(getattr(_cfg(), "default_preset_id", None) or "").strip()
