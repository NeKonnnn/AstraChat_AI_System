"""Пресеты моделей генерации изображений (workflow + checkpoint)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.settings import get_settings


def _cfg():
    return get_settings().image_generation


def list_configured_presets() -> List[Dict[str, Any]]:
    cfg = _cfg()
    presets_map = getattr(cfg, "presets", None) or {}
    out: List[Dict[str, Any]] = []
    if isinstance(presets_map, dict):
        for pid, preset in presets_map.items():
            if hasattr(preset, "model_dump"):
                row = preset.model_dump()
            elif isinstance(preset, dict):
                row = dict(preset)
            else:
                continue
            row["id"] = str(row.get("id") or pid)
            if row.get("label"):
                out.append(row)
    return out


def resolve_preset(preset_id: Optional[str]) -> Optional[Dict[str, Any]]:
    cfg = _cfg()
    pid = (preset_id or "").strip()
    if not pid:
        pid = str(getattr(cfg, "default_preset_id", None) or "").strip()
    presets = list_configured_presets()
    if not presets:
        return None
    if pid:
        for p in presets:
            if p.get("id") == pid:
                return p
    return presets[0]


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
    }
