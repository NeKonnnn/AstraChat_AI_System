"""Управление workflow JSON для ComfyUI: список, сохранение, анализ node_map."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.services.comfyui_image_generation import ComfyImageGenError

_WORKFLOW_DIR_REL = "config/comfy_workflows"
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}$")


def _workflow_base_dir() -> Path:
    routes_dir = Path(__file__).resolve().parent.parent / "routes"
    backend_dir = routes_dir.parent
    if (backend_dir / "config").is_dir():
        return backend_dir
    return backend_dir.parent


def workflows_directory() -> Path:
    return (_workflow_base_dir() / _WORKFLOW_DIR_REL).resolve()


def _validate_workflow_name(name: str) -> str:
    base = (name or "").strip()
    if not base:
        raise ComfyImageGenError("Имя workflow не задано")
    if not base.endswith(".json"):
        base = f"{base}.json"
    stem = base[:-5]
    if not _SAFE_NAME_RE.match(stem):
        raise ComfyImageGenError(
            "Имя файла workflow: латиница, цифры, точка, дефис, подчёркивание (без пробелов)"
        )
    return base


def list_workflow_files() -> List[Dict[str, Any]]:
    root = workflows_directory()
    if not root.is_dir():
        return []
    items: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            stat = path.stat()
            rel = f"{_WORKFLOW_DIR_REL}/{path.name}"
            items.append(
                {
                    "filename": path.name,
                    "workflow_path": rel.replace("\\", "/"),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
        except OSError:
            continue
    return items


def read_workflow_file(filename: str) -> Dict[str, Any]:
    name = _validate_workflow_name(filename)
    path = workflows_directory() / name
    if not path.exists():
        raise ComfyImageGenError(f"Workflow не найден: {name}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ComfyImageGenError(f"Невалидный JSON: {e}") from e
    if not isinstance(data, dict):
        raise ComfyImageGenError("Workflow должен быть JSON-объектом (API-формат ComfyUI)")
    return data


def save_workflow_file(filename: str, workflow: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(workflow, dict) or not workflow:
        raise ComfyImageGenError("Workflow пустой или не объект")
    name = _validate_workflow_name(filename)
    root = workflows_directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, ensure_ascii=False, indent=2)
        f.write("\n")
    rel = f"{_WORKFLOW_DIR_REL}/{name}".replace("\\", "/")
    return {"filename": name, "workflow_path": rel}


def _node_map_entry(node_id: str, field: str) -> Dict[str, str]:
    return {"node": str(node_id), "input": field}


def analyze_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Эвристики для node_map: prompt, negative_prompt, width/height, steps, seed, cfg, denoise,
  checkpoint, reference_image.
    """
    text_nodes: List[Tuple[str, str, int]] = []
    samplers: List[str] = []
    latents: List[str] = []
    checkpoints: List[str] = []
    load_images: List[str] = []

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = str(node.get("class_type") or "")
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}

        if ct == "CLIPTextEncode":
            text = str(inputs.get("text") or "")
            text_nodes.append((str(node_id), text, len(text)))
        elif ct in ("KSampler", "KSamplerAdvanced"):
            samplers.append(str(node_id))
        elif ct in ("EmptyLatentImage", "EmptySD3LatentImage"):
            latents.append(str(node_id))
        elif ct == "CheckpointLoaderSimple":
            checkpoints.append(str(node_id))
        elif ct == "LoadImage":
            load_images.append(str(node_id))

    suggested: Dict[str, Dict[str, str]] = {}
    nodes_info: List[Dict[str, Any]] = []

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = str(node.get("class_type") or "")
        inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        nodes_info.append(
            {
                "id": str(node_id),
                "class_type": ct,
                "inputs": list(inputs.keys()),
            }
        )

    if text_nodes:
        sorted_text = sorted(text_nodes, key=lambda x: x[2], reverse=True)
        prompt_id, prompt_text, _ = sorted_text[0]
        suggested["prompt"] = _node_map_entry(prompt_id, "text")
        negatives = [t for t in text_nodes if t[0] != prompt_id]
        if negatives:
            neg_id = min(negatives, key=lambda x: x[2])[0]
            suggested["negative_prompt"] = _node_map_entry(neg_id, "text")
        elif len(sorted_text) > 1:
            suggested["negative_prompt"] = _node_map_entry(sorted_text[1][0], "text")

    if latents:
        lid = latents[0]
        suggested["width"] = _node_map_entry(lid, "width")
        suggested["height"] = _node_map_entry(lid, "height")

    if samplers:
        sid = samplers[0]
        suggested["steps"] = _node_map_entry(sid, "steps")
        suggested["seed"] = _node_map_entry(sid, "seed")
        suggested["cfg"] = _node_map_entry(sid, "cfg")
        suggested["denoise"] = _node_map_entry(sid, "denoise")

    if checkpoints:
        suggested["checkpoint"] = _node_map_entry(checkpoints[0], "ckpt_name")

    if load_images:
        suggested["reference_image"] = _node_map_entry(load_images[0], "image")

    return {
        "suggested_node_map": suggested,
        "nodes": nodes_info,
        "stats": {
            "clip_text_encode": len(text_nodes),
            "ksampler": len(samplers),
            "latent": len(latents),
            "checkpoint": len(checkpoints),
            "load_image": len(load_images),
        },
    }
