"""
Ablation eval — pure QuerySignal routing, no LLM calls.

Measures routing accuracy using only:
  normalize(query) → QuerySignal → DOMAIN_TO_AGENT lookup

No coordinator, no brain, no LLM. Runs in < 2 seconds.

Used to produce the "signal-only" row in the paper's ablation table:

  | Mode                    | Accuracy |
  |-------------------------|----------|
  | Action-first (baseline) | 70%      |  ← from eval_2 log
  | QuerySignal only        | 98%      |  ← this script (100 prompts, 2026-06-09)
  | Signal + brain + LLM    | 97%      |  ← from eval_3 log

For multi-strategy comparison (keyword-only, hybrid, logistic vs signal_only)
see agent_arena.py — runs all strategies in < 2s, persists to logs/arena.db.

Run:
    PYTHONPATH=. \\
      python3 ablation_eval.py
"""

import sys
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT
from workbench.auto_train import PROMPTS

# Terse prompts route differently — expected agent is "terse", domain detection
# alone can't produce "terse" (no domain keyword → "general" → knowledge_learning).
# We need special-case handling: verbosity==terse → terse agent.
def signal_route(query: str) -> str:
    """
    Pure signal-based routing — mirrors core_brain fast path, no LLM.

    This is the PURE KEYWORD BASELINE: no semantic fallback, no flag dependence,
    deterministic. Other tools (semantic_threshold_study.py) rely on it being the
    untouched baseline, so the hybrid composition lives in hybrid_route(), NOT here.

    Routing priority:
      1. factual shape → terse (short concrete answer, any verbosity)
      2. confident domain (domain_conf > 0.3) → domain agent
         Must come BEFORE verbosity check: "Configure nginx SSL" (3 words)
         has domain=networking, conf=0.55 and must NOT route to terse.
      3. terse verbosity (≤6 tokens, no domain) → terse
      4. fallback → knowledge_learning
    """
    if not query.strip():
        return "knowledge_learning"
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"
    if sig.domain_conf > 0.3:
        return DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
    if sig.verbosity == "terse":
        return "terse"
    return "knowledge_learning"


def hybrid_route(query: str) -> str:
    """
    Production-faithful route: the keyword baseline, plus the semantic rescue on
    the `knowledge_learning` fallthrough — mirroring core_brain's shipped hook.

    The rescue fires ONLY when signal_route yields knowledge_learning AND the
    fallback is enabled (AGENTIC_SEMANTIC_FALLBACK=1). Flag off → byte-identical
    to signal_route, so the honest keyword baseline is always recoverable.
    Crash-safe: any fallback failure keeps the knowledge_learning fallthrough.
    """
    base = signal_route(query)
    if base != "knowledge_learning":
        return base
    try:
        from orchestration import semantic_fallback as sf
        if sf.is_enabled():
            r = sf.route(query)
            if r is not None and r[0] != "knowledge_learning":
                return r[0]
    except Exception:
        pass
    return "knowledge_learning"


def run_ablation():
    print("=" * 60)
    print("  Ablation: QuerySignal-only routing (no LLM)")
    print(f"  Prompts: {len(PROMPTS)}")
    print("=" * 60)

    domain_stats: dict = {}
    correct = 0

    for pid, expected, domain, prompt in PROMPTS:
        got = signal_route(prompt)
        ok  = (got == expected)
        if ok:
            correct += 1

        ds = domain_stats.setdefault(domain, {"correct": 0, "total": 0})
        ds["total"]   += 1
        if ok:
            ds["correct"] += 1

        mark = "✓" if ok else "✗"
        if not ok:
            sig = normalize(prompt)
            print(f"  {mark} [{pid}] expected={expected} got={got} "
                  f"domain={sig.domain}({sig.domain_conf:.2f}) shape={sig.answer_shape} verb={sig.verbosity}")

    n = len(PROMPTS)
    pct = 100 * correct / n
    print(f"\n  Result: {correct}/{n} ({pct:.1f}%)")
    print()
    print("  By domain (PROMPTS key → agent):")
    # PROMPTS domain keys are short forms; map to labels for display
    domain_label = {
        "networking": "it_networking",    "python":  "python_dev",
        "dotnet":     "dotnet_dev",        "ai_ml":   "ai_ml",
        "knowledge":  "knowledge_learning","terse":   "terse",
        "web":        "web_dev",           "devops":  "devops",
        "data":       "data_analyst",      "writing": "writer",
    }
    for short, label in domain_label.items():
        ds = domain_stats.get(short, {"correct": 0, "total": 0})
        c, t = ds["correct"], ds["total"]
        if t == 0:
            continue
        bar = "█" * c + "░" * (t - c)
        print(f"    {label:25s}: {c:2d}/{t:2d}  {bar}")

    print()
    print("  Ablation table row (for paper §5):")
    print(f"    QuerySignal only (no LLM fallback): {correct}/{n} = {pct:.1f}%")
    return correct, n


if __name__ == "__main__":
    run_ablation()
