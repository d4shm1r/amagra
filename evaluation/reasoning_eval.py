"""
reasoning_eval.py
─────────────────────────────────────────────────────────────────
GSM8K reasoning head-to-head: does inference-time compute lift a small local
model toward a GPT-4-class ceiling?

Three conditions, exact-match graded on the final number (no LLM judge):

  baseline   — phi4-mini, single greedy sample (temp 0)
  voted      — phi4-mini + self-consistency (N samples, majority vote)
  ceiling    — a hosted GPT-4-class model, single sample  [--ceiling]

The headline number is gap-closed:
    (voted_acc - baseline_acc) / (ceiling_acc - baseline_acc)
i.e. how much of the distance to the frontier model the orchestration recovered.

Usage:
  python3 reasoning_eval.py --n 50                     # baseline vs voted
  python3 reasoning_eval.py --n 50 --samples 8         # wider vote
  python3 reasoning_eval.py --n 50 --ceiling           # add frontier column
                                                       # (needs a hosted provider)

Backends:
  local   — ChatOllama, OLLAMA_MODEL (default phi4-mini:latest)
  ceiling — models.llm with LLM_PROVIDER=openai|anthropic + the usual API-key env

Results saved to logs/reasoning_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognition.self_consistency import (
    extract_final_answer,
    self_consistent_answer,
    normalize_number,
)

_ROOT       = Path(__file__).parent.parent
DATA_CACHE  = _ROOT / "logs" / "gsm8k_test.jsonl"
RESULTS_DIR = _ROOT / "logs"
GSM8K_URL   = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    "master/grade_school_math/data/test.jsonl"
)

# ── Dataset ───────────────────────────────────────────────────

def _download_gsm8k() -> None:
    import requests
    print("[data] downloading GSM8K test split …", flush=True)
    r = requests.get(GSM8K_URL, timeout=60)
    r.raise_for_status()
    DATA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DATA_CACHE.write_text(r.text)
    print(f"[data] saved {DATA_CACHE}")


def load_gsm8k(n: int = 50) -> list[dict]:
    if not DATA_CACHE.exists():
        _download_gsm8k()
    rows = [json.loads(l) for l in DATA_CACHE.read_text().splitlines() if l.strip()]
    return rows[:n]


def gold_answer(row: dict) -> str:
    """GSM8K gold answers end with '#### <number>'."""
    return normalize_number(row["answer"].split("####")[-1])


# ── Backends ──────────────────────────────────────────────────

_local_cache: dict = {}

def _local_generate(prompt: str, temperature: float) -> str:
    from langchain_ollama import ChatOllama
    key = round(temperature, 2)
    if key not in _local_cache:
        _local_cache[key] = ChatOllama(
            model=os.environ.get("OLLAMA_MODEL", "phi4-mini:latest"),
            temperature=temperature,
            num_ctx=2048,
            num_thread=6,
            num_predict=512,
        )
    return _local_cache[key].invoke(prompt).content.strip()


_ceiling_llm = None

def _ceiling_generate(prompt: str, _temperature: float = 0.0) -> str:
    global _ceiling_llm
    if _ceiling_llm is None:
        from models.llm import llm  # honours LLM_PROVIDER / API-key env
        _ceiling_llm = llm
    out = _ceiling_llm.invoke(prompt)
    return (getattr(out, "content", None) or str(out)).strip()


# ── Prompt ────────────────────────────────────────────────────

def _make_prompt(question: str) -> str:
    return (
        "Solve the math problem. Think step by step, then give the final answer "
        "on its own line as:\n#### <number>\n\n"
        f"Problem: {question}"
    )


# ── Conditions ────────────────────────────────────────────────

def run_baseline(rows: list[dict]) -> list[dict]:
    out = []
    for i, row in enumerate(rows, 1):
        t0 = time.time()
        text = _local_generate(_make_prompt(row["question"]), 0.0)
        pred = extract_final_answer(text)
        gold = gold_answer(row)
        out.append({
            "i": i, "pred": pred, "gold": gold,
            "correct": pred is not None and pred == gold,
            "elapsed_s": round(time.time() - t0, 2),
        })
        print(f"[baseline {i}/{len(rows)}] pred={pred} gold={gold} "
              f"{'✓' if out[-1]['correct'] else '✗'}", flush=True)
    return out


def run_voted(rows: list[dict], samples: int, temperature: float) -> list[dict]:
    out = []
    for i, row in enumerate(rows, 1):
        t0 = time.time()
        res = self_consistent_answer(
            _make_prompt(row["question"]), _local_generate,
            n=samples, temperature=temperature,
        )
        pred, gold = res["answer"], gold_answer(row)
        out.append({
            "i": i, "pred": pred, "gold": gold,
            "correct": pred is not None and pred == gold,
            "votes": res["votes"], "valid": res["valid"], "n": res["n"],
            "distribution": res["distribution"],
            "elapsed_s": round(time.time() - t0, 2),
        })
        print(f"[voted {i}/{len(rows)}] pred={pred} gold={gold} "
              f"({res['votes']}/{res['valid']} votes) "
              f"{'✓' if out[-1]['correct'] else '✗'}", flush=True)
    return out


def run_ceiling(rows: list[dict]) -> list[dict]:
    out = []
    for i, row in enumerate(rows, 1):
        t0 = time.time()
        text = _ceiling_generate(_make_prompt(row["question"]))
        pred = extract_final_answer(text)
        gold = gold_answer(row)
        out.append({
            "i": i, "pred": pred, "gold": gold,
            "correct": pred is not None and pred == gold,
            "elapsed_s": round(time.time() - t0, 2),
        })
        print(f"[ceiling {i}/{len(rows)}] pred={pred} gold={gold} "
              f"{'✓' if out[-1]['correct'] else '✗'}", flush=True)
    return out


# ── Metrics ───────────────────────────────────────────────────

def _accuracy(results: list[dict]) -> float:
    return round(sum(r["correct"] for r in results) / len(results), 4) if results else 0.0


def summarise(baseline, voted, ceiling) -> dict:
    b = _accuracy(baseline)
    v = _accuracy(voted)
    summary = {
        "n": len(baseline),
        "baseline_acc": b,
        "voted_acc": v,
        "voted_lift": round(v - b, 4),
    }
    if ceiling:
        c = _accuracy(ceiling)
        summary["ceiling_acc"] = c
        head = c - b
        summary["gap_to_ceiling"] = round(head, 4)
        summary["gap_closed"] = round((v - b) / head, 4) if head > 0 else None
    return summary


# ── CLI ───────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="GSM8K reasoning head-to-head (self-consistency lift)")
    ap.add_argument("--n", type=int, default=50, help="number of problems")
    ap.add_argument("--samples", type=int, default=5, help="self-consistency samples (voted)")
    ap.add_argument("--temperature", type=float, default=0.7, help="voted-sample temperature")
    ap.add_argument("--ceiling", action="store_true", help="also run a hosted GPT-4-class model")
    ap.add_argument("--mode", choices=["all", "baseline", "voted"], default="all")
    args = ap.parse_args()

    rows = load_gsm8k(args.n)
    print(f"[eval] {len(rows)} GSM8K problems | samples={args.samples} "
          f"temp={args.temperature} ceiling={args.ceiling}\n")

    baseline = run_baseline(rows) if args.mode in ("all", "baseline") else []
    voted    = run_voted(rows, args.samples, args.temperature) if args.mode in ("all", "voted") else []
    ceiling  = run_ceiling(rows) if (args.ceiling and args.mode == "all") else []

    summary = summarise(baseline, voted, ceiling)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "config": vars(args),
        "summary": summary,
        "baseline": baseline,
        "voted": voted,
        "ceiling": ceiling,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"reasoning_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(payload, indent=2))

    print("\n── summary ─────────────────────────────")
    for k, val in summary.items():
        print(f"  {k:16} {val}")
    print(f"\n[saved] {out_path}")


if __name__ == "__main__":
    main()
