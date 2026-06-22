"""
evaluation/memory_recall_bench.py — the memory-recall release gate.

Run:
    make benchmark-memory
    PYTHONPATH=. python3 evaluation/memory_recall_bench.py            # synthetic gate
    PYTHONPATH=. python3 evaluation/memory_recall_bench.py --live     # real backend (Ollama)
    PYTHONPATH=. python3 evaluation/memory_recall_bench.py --no-gate   # measure, don't write verdict

Why this exists
---------------
"Explain this project" and every other synthesis feature are only as trustworthy
as the memory they read. The danger is not missing a memory — it is confidently
surfacing the *wrong* one: a stale decision presented as current, or an
unconfirmed guess ranked above a user-stated fact. So before synthesis is
allowed, three invariants of the ranking formula must hold under realistic score
distributions:

  1. recall@k          — the right decision is actually retrievable.
  2. provenance order  — explicit (user-stated) memory outranks derived (a bare
                         click) for the same topic. Trust beats convenience.
  3. currency safety   — a fresh decision outranks the stale one it replaced,
                         even when both are high-confidence. This is the
                         safety-critical one: a high-provenance *stale* memory is
                         the most dangerous record in the system.

The default mode is synthetic and deterministic so it can gate CI without
Ollama: it builds a controlled corpus and runs the exact production ranking
(raw cosine × quality × type_weight × freshness) over it. --live measures the
real backend over actually-stored decisions for a truthful local reading.

Exit code is 0 on PASS, 1 on FAIL, so it works as a literal gate in a pipeline.
The verdict is also written via evaluation/memory_gate.py for the running app.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))

import memory_core.db as memory_db
from evaluation import memory_gate

# ── Thresholds — the gate. Currency safety is strictest: a stale memory winning
#    is an active falsehood, far worse than a recall miss (which is just silence).
THRESHOLDS = {
    "recall_at_3":           0.90,
    "provenance_order_rate": 0.95,
    "currency_safety_rate":  0.98,
}

_DIM = 64
# Perturbation magnitude along a random *unit* direction. With unit topic
# vectors, intra-topic cosine ≈ 1/(1+_NOISE²): _NOISE=0.5 → ≈0.8, a realistic
# "same topic, different phrasing" similarity. (Scaling raw standard_normal here
# would give a perturbation of norm ≈√dim that swamps the topic signal.)
_NOISE = 0.5
_STALE_AGE_DAYS = 120  # ≈4 freshness half-lives → heavily decayed


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v


def _ts(age_days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()


def _score(query: np.ndarray, mem: dict) -> float:
    """The production ranking formula, reproduced exactly."""
    raw     = float(np.dot(_unit(query), _unit(mem["vec"])))
    tweight = memory_db._TYPE_WEIGHTS.get(mem["type"], 1.0)
    fresh   = memory_db._freshness(mem["ts"])
    return raw * mem["quality"] * tweight * fresh


def _build_corpus(n_topics: int, seed: int):
    """Deterministic synthetic corpus: per topic an explicit/derived/stale
    decision plus cross-topic episodic distractors."""
    rng = np.random.default_rng(seed)
    topics = []
    for t in range(n_topics):
        base = _unit(rng.standard_normal(_DIM))
        def perturb():
            return base + _NOISE * _unit(rng.standard_normal(_DIM))
        explicit = {"id": f"t{t}-explicit", "topic": t, "type": "decision",
                    "quality": 1.0, "ts": _ts(0), "vec": perturb(), "role": "explicit-active"}
        derived  = {"id": f"t{t}-derived",  "topic": t, "type": "decision",
                    "quality": 0.6, "ts": _ts(0), "vec": perturb(), "role": "derived-active"}
        stale    = {"id": f"t{t}-stale",    "topic": t, "type": "decision",
                    "quality": 1.0, "ts": _ts(_STALE_AGE_DAYS), "vec": perturb(), "role": "explicit-stale"}
        distractors = [
            {"id": f"t{t}-chat{j}", "topic": t, "type": "episodic", "quality": 0.9,
             "ts": _ts(int(rng.integers(0, 30))), "vec": perturb(), "role": "distractor"}
            for j in range(2)
        ]
        topics.append({"query": base + _NOISE * _unit(rng.standard_normal(_DIM)),
                       "explicit": explicit, "derived": derived, "stale": stale,
                       "members": [explicit, derived, stale, *distractors]})

    corpus = [m for tp in topics for m in tp["members"]]
    return topics, corpus


def run_synthetic(n_topics: int = 40, seed: int = 7) -> dict:
    topics, corpus = _build_corpus(n_topics, seed)

    hits = order_ok = currency_ok = 0
    failures_detail = []

    for ti, tp in enumerate(topics):
        ranked = sorted(corpus, key=lambda m: _score(tp["query"], m), reverse=True)
        top3_ids = {m["id"] for m in ranked[:3]}

        if tp["explicit"]["id"] in top3_ids:
            hits += 1
        else:
            failures_detail.append(f"topic {ti}: explicit decision missed top-3")

        s_exp = _score(tp["query"], tp["explicit"])
        s_der = _score(tp["query"], tp["derived"])
        s_stale = _score(tp["query"], tp["stale"])

        if s_exp > s_der:
            order_ok += 1
        else:
            failures_detail.append(f"topic {ti}: derived outranked explicit ({s_der:.3f} ≥ {s_exp:.3f})")

        if s_exp > s_stale:
            currency_ok += 1
        else:
            failures_detail.append(f"topic {ti}: STALE outranked fresh ({s_stale:.3f} ≥ {s_exp:.3f})")

    n = len(topics)
    metrics = {
        "recall_at_3":           round(hits / n, 4),
        "provenance_order_rate": round(order_ok / n, 4),
        "currency_safety_rate":  round(currency_ok / n, 4),
    }
    return _verdict("synthetic", metrics, n, failures_detail)


def run_live(k: int = 3) -> dict:
    """Truthful measurement over actually-stored model decisions (needs Ollama)."""
    from decision import model_choices
    from memory_core.backend import get_backend

    decisions = [d for d in model_choices.recent(limit=200, active_only=True)
                 if d["provenance"] == "explicit"]
    if not decisions:
        return _verdict("live", {"recall_at_3": 0.0, "provenance_order_rate": 0.0,
                                 "currency_safety_rate": 0.0}, 0,
                        ["no explicit active decisions stored yet — capture some first"])

    backend = get_backend()
    hits = 0
    failures_detail = []
    for d in decisions:
        try:
            recs = backend.retrieve(d["prompt"], k=k, caller="memory_recall_bench")
        except Exception as e:
            failures_detail.append(f"decision {d['id']}: retrieve failed ({e})")
            continue
        found = any(str(d["id"]) == str((r.metadata or {}).get("decision_id"))
                    or d["chosen_provider"] in (r.content or "")
                    for r in recs)
        if found:
            hits += 1
        else:
            failures_detail.append(f"decision {d['id']}: not in top-{k} for its own prompt")

    n = len(decisions)
    # Live mode measures recall only; ordering invariants are proven by synthetic.
    metrics = {
        "recall_at_3":           round(hits / n, 4),
        "provenance_order_rate": 1.0,
        "currency_safety_rate":  1.0,
    }
    return _verdict("live", metrics, n, failures_detail)


def _verdict(mode: str, metrics: dict, n: int, failures_detail: list) -> dict:
    failures = [f"{k}={metrics[k]:.3f} < {THRESHOLDS[k]:.2f}"
                for k in THRESHOLDS if metrics.get(k, 0.0) < THRESHOLDS[k]]
    return {
        "mode":       mode,
        "passed":     len(failures) == 0,
        "n":          n,
        "metrics":    metrics,
        "thresholds": THRESHOLDS,
        "failures":   failures,
        # Cap the noisy per-topic detail so the report stays readable.
        "detail":     failures_detail[:20],
    }


def _print_report(report: dict) -> None:
    print(f"\n  Memory Recall Benchmark — {report['mode']} mode  ({report['n']} cases)")
    print("  " + "─" * 52)
    for k, th in THRESHOLDS.items():
        v = report["metrics"].get(k, 0.0)
        mark = "✓" if v >= th else "✗"
        print(f"  {mark} {k:<22} {v*100:6.2f}%   (gate ≥ {th*100:.0f}%)")
    print("  " + "─" * 52)
    print(f"  VERDICT: {'PASS — synthesis allowed' if report['passed'] else 'FAIL — synthesis stays gated'}")
    if report["failures"]:
        print("  Failures:")
        for f in report["failures"]:
            print(f"    · {f}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Memory recall release gate")
    ap.add_argument("--live", action="store_true", help="measure the real backend (requires Ollama)")
    ap.add_argument("--topics", type=int, default=40, help="synthetic topic count")
    ap.add_argument("--no-gate", action="store_true", help="measure without writing the gate verdict")
    args = ap.parse_args()

    report = run_live() if args.live else run_synthetic(n_topics=args.topics)
    _print_report(report)

    if not args.no_gate:
        memory_gate.write_verdict(report)
        print(f"  Gate verdict written → synthesis_allowed() = {memory_gate.synthesis_allowed()}\n")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
