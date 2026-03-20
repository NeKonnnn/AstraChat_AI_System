"""
socket_helpers.py - утилиты, общие для socket_handlers и роутеров
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _is_structure_query(text: str) -> bool:
    """Запрос про оглавление/структуру/главы - добавляем начало документа в RAG"""
    if not text or len(text.strip()) < 3:
        return False
    t = text.lower().strip()
    keywords = (
        "оглавление", "содержание", "главы", "глава", "пункт", "подпункт",
        "структура работы", "структуру работы", "названия глав", "какие главы",
    )
    return any(k in t for k in keywords)


def _terminal_chat_inference_banner(
    *,
    sid: str,
    conversation_id,
    user_preview: str,
    mode_label: str,
    model_path_for_call: str = None,
    extra_line: str = None,
):
    import backend.app_state as _state

    lines = [
        "",
        "=" * 76,
        "  [ЧАТ] Генерация ответа - что использует сервер СЕЙЧАС",
        "=" * 76,
        f"  Режим: {mode_label}",
        f"  Socket: {str(sid)[:20]}…  |  conversation_id: {conversation_id}",
        f"  Текст запроса (начало): {(user_preview or '')[:160]!r}",
    ]
    path = model_path_for_call if model_path_for_call is not None else _state.get_current_model_path()
    lines.append(f"  Модель (путь для вызова LLM): {path!r}")

    if _state.get_model_info:
        try:
            info = _state.get_model_info()
            if info:
                lines.append(f"  get_model_info: {json.dumps(info, ensure_ascii=False, default=str)[:500]}")
        except Exception as ex:
            lines.append(f"  get_model_info: ошибка {ex}")

    if _state.model_settings:
        try:
            st = _state.model_settings.get_all()
            lines.append(f"  Настройки модели: {json.dumps(st, ensure_ascii=False, default=str)}")
        except Exception as ex:
            lines.append(f"  Настройки модели: недоступны ({ex})")
    else:
        lines.append("  Настройки модели: модуль недоступен")

    if _state.context_prompt_manager:
        try:
            gp = _state.context_prompt_manager.get_global_prompt() or ""
            prev = gp[:500] + ("…" if len(gp) > 500 else "")
            lines.append(f"  Глобальный системный промпт ({len(gp)} симв., начало): {prev!r}")
        except Exception as ex:
            lines.append(f"  Глобальный промпт: ошибка {ex}")
    else:
        lines.append("  Глобальный промпт: менеджер недоступен")

    if extra_line:
        lines.append(f"  {extra_line}")

    lines.append(
        "  Примечание: блок get_model_info - глобальное состояние llm-svc (что загружено в память)"
    )
    lines.append(
        "  Реальный ответ строится по полю model в POST /v1/chat/completions (см. лог generate_response выше);"
    )
    lines.append(
        "  при выбранном агенте туда подставляется модель из конструктора (llm-svc://id)"
    )
    lines.append("=" * 76)
    block = "\n".join(lines)
    print(block, flush=True)
    logger.info(block)


async def _resolve_agent_chat_params(agent_id_raw) -> dict:
    """Модель и параметры из карточки агента (конструктор)."""
    empty = {"model_path": None, "max_tokens": None, "temperature": None, "system_prompt": None}
    if agent_id_raw is None:
        return empty
    try:
        aid = int(agent_id_raw)
    except (TypeError, ValueError):
        return empty
    try:
        from backend.database.init_db import get_agent_repository
        repo = get_agent_repository()
        if repo is None:
            return empty
        ag = await repo.get_agent(aid, None)
        if not ag:
            return empty
        cfg = ag.config if isinstance(ag.config, dict) else {}
        mp = str(cfg.get("model") or cfg.get("model_path") or "").strip()
        out = {**empty}
        if mp:
            low = mp.lower()
            if low.startswith("1lm-svc://"):
                mp = "llm-svc://" + mp[10:]
                low = mp.lower()
            if low.startswith("llm-svc://"):
                out["model_path"] = mp
            elif "/" in mp or mp.lower().endswith(".gguf") or (len(mp) > 2 and mp[1] == ":"):
                out["model_path"] = mp
            else:
                out["model_path"] = f"llm-svc://{mp}"
        ms = cfg.get("model_settings")
        if isinstance(ms, dict):
            if ms.get("output_tokens") is not None:
                try:
                    out["max_tokens"] = int(ms["output_tokens"])
                except (TypeError, ValueError):
                    pass
            if ms.get("temperature") is not None:
                try:
                    out["temperature"] = float(ms["temperature"])
                except (TypeError, ValueError):
                    pass
        sp = (ag.system_prompt or "").strip()
        if sp:
            out["system_prompt"] = sp
        logger.info(
            f"[chat] agent_id={aid} → model_path={out['model_path']}, "
            f"max_tokens={out['max_tokens']}, temperature={out['temperature']}"
        )
        return out
    except Exception as ex:
        logger.warning(f"_resolve_agent_chat_params: {ex}")
        return empty
