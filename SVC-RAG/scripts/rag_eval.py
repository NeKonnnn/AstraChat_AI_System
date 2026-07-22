#!/usr/bin/env python3
"""Offline RAG eval-пайплайн: MRR, Precision@k, Recall@k, Faithfulness, Context Recall.

Считает метрики по размеченному датасету, сверяет с порогами (OK/WARNING/CRITICAL)
и сохраняет отчёт. Retrieval-метрики (MRR/Precision/Recall) считаются всегда;
generation-метрики (Faithfulness, Context Recall) — если в строке датасета есть
`ground_truth_answer` (для Context Recall) и/или `answer` (для Faithfulness) и
задан --llm-url.

Формат датасета (JSONL, по объекту на строку):
  {
    "question": "Какие условия автокредита?",
    "gold_document_ids": [12, 15],                 # опционально
    "gold_chunks": [{"document_id": 12, "chunk_index": 3}],  # опционально (приоритетнее)
    "ground_truth_answer": "Ставка от 4.9% ...",   # опционально (для Context Recall)
    "answer": "..."                                  # опционально (для Faithfulness готового ответа)
  }

Примеры запуска:
  python SVC-RAG/scripts/rag_eval.py --dataset eval.jsonl --store kb \
      --base-url http://localhost:8000 --k 12

  python SVC-RAG/scripts/rag_eval.py --dataset eval.jsonl --store project \
      --project-id my-project --base-url http://localhost:8000 \
      --llm-url http://llm-service:8000 --llm-model default
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from statistics import mean
from typing import Any, Dict, List, NoReturn, Optional, Tuple

import httpx

# Импорт числовых метрик из сервиса (retrieval_eval).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SVC_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _SVC_ROOT not in sys.path:
    sys.path.insert(0, _SVC_ROOT)

from app.services.retrieval_eval import compute_retrieval_metrics, mrr  # noqa: E402

# Пороги из спецификации.
THRESHOLDS = {
    "mrr": (0.75, 0.60),
    "faithfulness": (0.85, 0.70),
    "context_precision": (0.70, 0.50),
    "context_recall": (0.80, 0.60),
}


def _verdict(name: str, value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    target, warn = THRESHOLDS.get(name, (0.0, 0.0))
    if value >= target:
        return "OK"
    if value >= warn:
        return "WARNING"
    return "CRITICAL"


def _die(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(2)


def _search_endpoint(base_url: str, store: str, project_id: Optional[str]) -> str:
    base = base_url.rstrip("/")
    if store == "kb":
        return f"{base}/kb/search"
    if store == "memory":
        return f"{base}/memory-rag/search"
    if store == "project":
        if not project_id:
            _die("--project-id обязателен для store=project")
        return f"{base}/project-rag/projects/{project_id}/search"
    _die(f"Неизвестный store: {store}")


def _search(
    client: httpx.Client,
    url: str,
    row: Dict[str, Any],
    *,
    k: int,
    strategy: str,
) -> List[Tuple[str, float, Optional[int], Optional[int]]]:
    body: Dict[str, Any] = {
        "query": row["question"],
        "k": k,
        "strategy": strategy,
        "debug_trace": True,
    }
    if row.get("gold_document_ids"):
        body["eval_gold_document_ids"] = row["gold_document_ids"]
    if row.get("gold_chunks"):
        body["eval_gold_chunks"] = row["gold_chunks"]
    resp = client.post(url, json=body, timeout=120.0)
    resp.raise_for_status()
    data = resp.json()
    hits = data.get("hits") or []
    return [
        (h.get("content") or "", float(h.get("score") or 0.0), h.get("document_id"), h.get("chunk_index"))
        for h in hits
    ]


def _extract_json(text: str) -> Optional[dict]:
    import re

    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}\s*$", text.strip())
    for candidate in ([m.group(0)] if m else []) + [text.strip()]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _llm_judge(client: httpx.Client, llm_url: str, model: str, system: str, prompt: str) -> Optional[dict]:
    try:
        r = client.post(
            f"{llm_url.rstrip('/')}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 900,
                "stream": False,
            },
            timeout=120.0,
        )
        r.raise_for_status()
        content = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        return _extract_json(content)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] llm judge failed: {e}", file=sys.stderr)
        return None


def _faithfulness(client, llm_url, model, context: str, answer: str) -> Optional[float]:
    if not context or not answer:
        return None
    prompt = (
        "Разбей ОТВЕТ на атомарные утверждения и для каждого укажи, подтверждается ли оно "
        "КОНТЕКСТОМ (перефраз допустим).\n\n"
        f"КОНТЕКСТ:\n{context[:12000]}\n\nОТВЕТ:\n{answer[:8000]}\n\n"
        'Верни ТОЛЬКО JSON: {"claims":[{"text":"...","supported":true/false}]}'
    )
    parsed = _llm_judge(client, llm_url, model, "Ты аудитор фактов. Только JSON.", prompt)
    if not parsed or not isinstance(parsed.get("claims"), list):
        return None
    claims = parsed["claims"]
    if not claims:
        return None
    supported = sum(1 for c in claims if isinstance(c, dict) and c.get("supported"))
    return supported / len(claims)


def _context_recall(client, llm_url, model, context: str, ground_truth: str) -> Optional[float]:
    if not context or not ground_truth:
        return None
    prompt = (
        "Разбей ЭТАЛОННЫЙ ОТВЕТ на атомарные утверждения и для каждого укажи, можно ли его "
        "подтвердить КОНТЕКСТОМ (есть ли в контексте информация для этого утверждения).\n\n"
        f"КОНТЕКСТ:\n{context[:12000]}\n\nЭТАЛОННЫЙ ОТВЕТ:\n{ground_truth[:8000]}\n\n"
        'Верни ТОЛЬКО JSON: {"claims":[{"text":"...","supported":true/false}]}'
    )
    parsed = _llm_judge(client, llm_url, model, "Ты аудитор покрытия. Только JSON.", prompt)
    if not parsed or not isinstance(parsed.get("claims"), list):
        return None
    claims = parsed["claims"]
    if not claims:
        return None
    supported = sum(1 for c in claims if isinstance(c, dict) and c.get("supported"))
    return supported / len(claims)


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline RAG eval")
    ap.add_argument("--dataset", required=True, help="JSONL с вопросами и разметкой")
    ap.add_argument("--store", required=True, choices=["kb", "memory", "project"])
    ap.add_argument("--project-id", default=None)
    ap.add_argument("--base-url", default=os.getenv("SVC_RAG_URL", "http://localhost:8000"))
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--strategy", default="auto")
    ap.add_argument("--llm-url", default=os.getenv("LLM_SERVICE_URL", ""))
    ap.add_argument("--llm-model", default=os.getenv("LLM_MODEL", "default"))
    ap.add_argument("--out", default="rag_eval_report.json")
    args = ap.parse_args()

    rows: List[Dict[str, Any]] = []
    with open(args.dataset, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        _die("Пустой датасет")

    url = _search_endpoint(args.base_url, args.store, args.project_id)
    per_question: List[Dict[str, Any]] = []
    rr_list: List[float] = []
    prec_list: List[float] = []
    rec_list: List[float] = []
    hit_list: List[float] = []
    faith_list: List[float] = []
    ctx_recall_list: List[float] = []

    with httpx.Client() as client:
        for idx, row in enumerate(rows):
            q = row.get("question")
            if not q:
                continue
            hits = _search(client, url, row, k=args.k, strategy=args.strategy)
            rm = compute_retrieval_metrics(
                hits,
                args.k,
                gold_document_ids=row.get("gold_document_ids"),
                gold_chunks=[(c["document_id"], c["chunk_index"]) for c in row.get("gold_chunks", [])] or None,
            )
            entry: Dict[str, Any] = {"question": q, "retrieval": rm}
            if rm.get("reciprocal_rank") is not None:
                rr_list.append(rm["reciprocal_rank"])
            if rm.get("precision_at_k") is not None:
                prec_list.append(rm["precision_at_k"])
            if rm.get("recall_at_k") is not None:
                rec_list.append(rm["recall_at_k"])
            if rm.get("hit_rate_at_k") is not None:
                hit_list.append(rm["hit_rate_at_k"])

            if args.llm_url:
                context_text = "\n\n".join(h[0] for h in hits[: args.k])
                if row.get("answer"):
                    f_score = _faithfulness(client, args.llm_url, args.llm_model, context_text, row["answer"])
                    if f_score is not None:
                        entry["faithfulness"] = f_score
                        faith_list.append(f_score)
                if row.get("ground_truth_answer"):
                    cr = _context_recall(
                        client, args.llm_url, args.llm_model, context_text, row["ground_truth_answer"]
                    )
                    if cr is not None:
                        entry["context_recall"] = cr
                        ctx_recall_list.append(cr)

            per_question.append(entry)
            print(f"[{idx + 1}/{len(rows)}] RR={rm.get('reciprocal_rank')} P@k={rm.get('precision_at_k')}")

    aggregate = {
        "mrr": round(mrr(rr_list), 4) if rr_list else None,
        "precision_at_k": round(mean(prec_list), 4) if prec_list else None,
        "recall_at_k": round(mean(rec_list), 4) if rec_list else None,
        "hit_rate_at_k": round(mean(hit_list), 4) if hit_list else None,
        "faithfulness": round(mean(faith_list), 4) if faith_list else None,
        "context_recall": round(mean(ctx_recall_list), 4) if ctx_recall_list else None,
    }
    verdicts = {
        "mrr": _verdict("mrr", aggregate["mrr"]),
        "faithfulness": _verdict("faithfulness", aggregate["faithfulness"]),
        "context_recall": _verdict("context_recall", aggregate["context_recall"]),
    }
    report = {
        "store": args.store,
        "k": args.k,
        "strategy": args.strategy,
        "n_questions": len(per_question),
        "aggregate": aggregate,
        "verdicts": verdicts,
        "per_question": per_question,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n=== RAG EVAL ===")
    for name, val in aggregate.items():
        v = verdicts.get(name)
        print(f"  {name:18} = {val}" + (f"  [{v}]" if v and v != "N/A" else ""))
    print(f"\nОтчёт сохранён: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
