"""
experience.py — the counterfactual → strategy_memory feed (closes O2's missing edge).

The decision-economics loop has three built pieces that were never connected:

    counterfactual (what else could have worked?)   ← cognition/counterfactual.py
            ↓  (this module: the missing edge)
    strategy_memory (task_class → strategy stats)    ← decision/strategy_memory.py
            ↓
    strategy_selector (EV rank; abstains w/o alts)   ← decision/strategy_selector.py

`strategy_memory.ingest_run_log()` already backfills the *chosen* strategy for each
run. But natural traffic picks exactly one strategy per task class, so the selector
has no alternatives to rank and abstains everywhere (OPEN_PROBLEMS O2). The only way
to generate alternative-strategy evidence without waiting for organic A/B traffic is
to *replay* historical decisions through a different agent and record the outcome —
which `cognition.counterfactual.compare_agents` already computes but throws away.

This module:
  * `record_counterfactual()` — persist BOTH arms of a counterfactual comparison as
    StrategyRecords, so the losing/alternative strategy accrues evidence too.
  * `explore()` — drive the highest-regret historical decisions through a real
    counterfactual run and feed both arms in, populating alternatives per class.

Honesty guards inherited from the components it wires:
  * Success is the counterfactual quality *proxy* (≥ SUCCESS_QUALITY), never a graded
    pass — every row it writes is proxy-graded, and the selector's Beta-shrinkage
    already discounts thin evidence.
  * Idempotent: each (decision, agent) pair writes one deduped row (run_id key), so
    re-running exploration never double-counts.

CLI:
  python3 -m decision.experience --explore 15         # replay 15 top candidates (real LLM)
  python3 -m decision.experience --explore 15 --dry   # candidate plan only, no LLM calls
  python3 -m decision.experience --coverage           # classes with ≥2 strategies (selectable)
"""

from __future__ import annotations

import argparse
import hashlib

from decision.strategy_memory import (
    StrategyMemory, StrategyRecord, canonical_strategy, task_class_of, SUCCESS_QUALITY,
)


def _cf_run_id(decision_id: int | None, agent: str, tag: str) -> str:
    """Stable dedup key for a counterfactual-derived row. Same (decision, agent, arm)
    always maps to the same id, so re-exploration is a no-op."""
    base = f"cf:{decision_id if decision_id is not None else 'adhoc'}:{agent}:{tag}"
    if decision_id is not None:
        return base
    # ad-hoc comparisons have no decision id → hash the arm identity so distinct
    # queries don't collide while identical replays still dedup.
    return "cf:" + hashlib.sha1(base.encode()).hexdigest()[:16]


def record_counterfactual(cf: dict, *, task_class: str,
                          memory: StrategyMemory | None = None) -> int:
    """Persist both arms of a `compare_agents()` result into strategy memory.

    Comparison runs skip reflection (counterfactual forces reflect_level="none"),
    so the recorded strategy is the bare agent path — exactly the alternative the
    selector needs to rank against the reflected production strategy.

    Returns the number of NEW rows written (0 on a dry/failed run or a full re-dedup).
    """
    if not cf or not cf.get("is_real_run"):
        return 0  # dry_run / error carries no outcome to learn from
    mem = memory or StrategyMemory()
    decision_id = cf.get("decision_id")
    written = 0
    arms = (
        ("original", cf.get("original_agent"), cf.get("original_quality_proxy"),
         cf.get("original_duration_s")),
        ("alt", cf.get("alt_agent"), cf.get("alt_quality_proxy"),
         cf.get("alt_duration_s")),
    )
    for tag, agent, quality, dur_s in arms:
        if not agent:
            continue
        success = (quality >= SUCCESS_QUALITY) if isinstance(quality, (int, float)) else None
        rec = StrategyRecord(
            task_class=task_class,
            strategy=canonical_strategy(agent, reflect_level="none"),
            success=success,
            latency_ms=int((dur_s or 0.0) * 1000),
            run_id=_cf_run_id(decision_id, agent, tag),
        )
        if mem.record(rec):
            written += 1
    return written


def explore(limit: int = 10, *, dry_run: bool = False,
            memory: StrategyMemory | None = None) -> dict:
    """Replay the highest-regret / conflicted historical decisions through their
    alternative agent and feed both arms into strategy memory.

    This is the exploration policy O2 calls for: it manufactures the alternative
    evidence the selector needs, targeting exactly the decisions where an
    alternative most plausibly wins (high regret, brain/router conflict).

    dry_run=True lists the candidates and the strategies that *would* be recorded
    without invoking any LLM — safe to run anywhere.

    Returns a summary dict {candidates, ran, rows_written, per_candidate:[...]}.
    """
    from cognition.counterfactual import top_counterfactual_candidates, simulate_alternative

    mem = memory or StrategyMemory()
    candidates = top_counterfactual_candidates(limit)
    summary = {"candidates": len(candidates), "ran": 0, "rows_written": 0,
               "per_candidate": []}

    for c in candidates:
        alt = c.get("suggested_alt")
        if not alt or alt == c.get("original_agent"):
            continue  # no distinct alternative to explore
        entry = {"decision_id": c["decision_id"], "original": c["original_agent"],
                 "alt": alt, "regret": c.get("regret")}
        if dry_run:
            entry["would_record"] = [
                canonical_strategy(c["original_agent"], "none"),
                canonical_strategy(alt, "none"),
            ]
            summary["per_candidate"].append(entry)
            continue

        cf = simulate_alternative(c["decision_id"], alt, dry_run=False)
        # simulate_alternative doesn't know the task class → derive it from the run.
        tc = _task_class_for_decision(c["decision_id"])
        written = record_counterfactual(cf, task_class=tc, memory=mem)
        entry.update({"task_class": tc, "verdict": cf.get("verdict"),
                      "delta_quality": cf.get("delta_quality"), "rows_written": written})
        summary["ran"] += 1
        summary["rows_written"] += written
        summary["per_candidate"].append(entry)

    return summary


def _task_class_for_decision(decision_id: int) -> str:
    """Recover the signal domain/shape for a decision so the recorded strategy lands
    in the same task class the router will later query. Falls back to general/*."""
    import sqlite3
    from infrastructure.db import path as _dbpath
    try:
        con = sqlite3.connect(_dbpath("decisions"))
        row = con.execute(
            "SELECT signal_domain, signal_shape FROM brain_decisions WHERE id=?",
            (decision_id,),
        ).fetchone()
        con.close()
        if row:
            return task_class_of(row[0], row[1])
    except Exception:
        pass
    return task_class_of(None, None)


def selectable_classes(memory: StrategyMemory | None = None,
                       min_alternatives: int = 2) -> list[tuple[str, int]]:
    """Task classes that now have ≥min_alternatives distinct strategies — the ones
    where the selector can actually choose instead of abstain. This is the metric
    that says whether exploration has bought us anything yet."""
    mem = memory or StrategyMemory()
    out = []
    for tc in mem.task_classes():
        n = len(mem.stats_for(tc))
        if n >= min_alternatives:
            out.append((tc, n))
    return out


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Counterfactual → strategy-memory feed")
    ap.add_argument("--explore", type=int, metavar="N", default=None,
                    help="replay N top-regret decisions through their alternative")
    ap.add_argument("--dry", action="store_true", help="plan only, no LLM calls")
    ap.add_argument("--coverage", action="store_true",
                    help="list task classes with ≥2 selectable strategies")
    args = ap.parse_args()

    if args.explore is not None:
        s = explore(args.explore, dry_run=args.dry)
        mode = "DRY (no LLM)" if args.dry else "LIVE"
        print(f"\n  Exploration [{mode}] — {s['candidates']} candidates, "
              f"ran {s['ran']}, wrote {s['rows_written']} rows")
        print("  " + "─" * 68)
        for e in s["per_candidate"]:
            if args.dry:
                print(f"  #{e['decision_id']:>3}  {e['original']:<18} vs {e['alt']:<18} "
                      f"regret={e.get('regret')}  would_record={e['would_record']}")
            else:
                print(f"  #{e['decision_id']:>3}  {e['task_class']:<20} "
                      f"{e['original']}→{e['alt']}  verdict={e.get('verdict')}  "
                      f"Δq={e.get('delta_quality')}  +{e.get('rows_written')} rows")

    if args.coverage or args.explore is None:
        sc = selectable_classes()
        print(f"\n  Selectable classes (≥2 strategies): {len(sc)}")
        for tc, n in sc:
            print(f"    {tc:<24} {n} strategies")
        if not sc:
            print("    none yet — run --explore to populate alternatives")


if __name__ == "__main__":
    main()
