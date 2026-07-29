"""Tests for the held-out selector-vs-baseline evaluator (O2 DoD #4).

Proves the off-policy logic on synthetic records — no DB, no LLM, no traffic:
  * temporal_split holds out the LATEST records per class
  * a class where the EV-better strategy also wins on holdout → status=scored, Δ>0
  * a class the selector abstains on → status=abstained (defers to baseline)
  * a class whose holdout lacks one of the picks → status=insufficient (never guessed)
  * an empty dataset → INSUFFICIENT verdict, no crash
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workbench.evaluation.decision_econ_holdout import (
    Record, temporal_split, evaluate,
)


def _rec(tc, strat, success, lat, ts):
    return Record(task_class=tc, strategy=strat, success=success, latency_ms=lat, ts=ts)


def test_temporal_split_holds_out_latest():
    recs = [_rec("a/b", "x", True, 1000, ts=float(i)) for i in range(10)]
    train, holdout = temporal_split(recs, holdout_frac=0.3)
    assert len(train) == 7 and len(holdout) == 3
    assert max(r.ts for r in train) < min(r.ts for r in holdout)   # train is the past


def test_scored_class_selector_beats_baseline():
    # python/code: natural traffic defaulted to a slow reflect-heavy strategy (the
    # BASELINE = most-attempted), but a faster strategy has higher EV. The selector
    # should DIVERGE to the fast one, and on the held-out era it also wins on success.
    recs = []
    tc = "python/code"
    # train era (ts 0-11, 12 recs): baseline (web_dev+reflect:full) attempted most but
    # weak+slow; python_dev fewer attempts but perfect+fast.
    for i in range(8):
        recs.append(_rec(tc, "web_dev+reflect:full", i < 3, 60000, ts=float(i)))   # 8 attempts, ~37% success
    for i in range(4):
        recs.append(_rec(tc, "python_dev", True, 5000, ts=float(i)))               # 4 attempts, 100% success
    # holdout era (ts 100-105, 6 recs): pattern persists, both picks present
    for i in range(3):
        recs.append(_rec(tc, "web_dev+reflect:full", i < 1, 60000, ts=100.0 + i))  # 33% success
    for i in range(3):
        recs.append(_rec(tc, "python_dev", True, 5000, ts=103.0 + i))              # 100% success

    rep = evaluate(recs, holdout_frac=1.0 / 3, min_attempts=3)
    scored = {o.task_class: o for o in rep.scored}
    assert tc in scored, f"expected {tc} scored, got {[(o.task_class, o.status) for o in rep.outcomes]}"
    o = scored[tc]
    assert o.baseline_pick == "web_dev+reflect:full"              # traffic's default
    assert o.selector_pick == "python_dev"                        # selector diverges
    assert o.success_delta is not None and o.success_delta > 0    # and wins on holdout
    assert o.selector_latency < o.baseline_latency               # cheaper too
    assert "BEATS" in rep.verdict()


def test_abstains_when_no_clear_winner():
    # two near-identical strategies → selector abstains (margin), status=abstained
    recs = []
    tc = "web/code"
    for i in range(8):
        recs.append(_rec(tc, "web_dev", True, 5000, ts=float(i)))
        recs.append(_rec(tc, "python_dev", True, 5100, ts=float(i)))
    rep = evaluate(recs, holdout_frac=0.3, min_attempts=3, margin=0.05)
    statuses = {o.task_class: o.status for o in rep.outcomes}
    assert statuses.get(tc) == "abstained"


def test_insufficient_when_holdout_missing_a_pick():
    # selector picks strategy A (strong in train) but the holdout only contains
    # strategy B → cannot observe A's outcome → insufficient, not a guess.
    recs = []
    tc = "ai_ml/explanation"
    for i in range(6):
        recs.append(_rec(tc, "ai_ml", True, 4000, ts=float(i)))            # strong in train
    for i in range(6):
        recs.append(_rec(tc, "knowledge_learning", False, 3000, ts=float(i)))
    # holdout only has knowledge_learning (not the selector's ai_ml pick)
    for i in range(4):
        recs.append(_rec(tc, "knowledge_learning", False, 3000, ts=100.0 + i))
    rep = evaluate(recs, holdout_frac=0.3, min_attempts=3)
    statuses = {o.task_class: o.status for o in rep.outcomes}
    assert statuses.get(tc) == "insufficient"
    assert not rep.scored                                              # nothing scored
    assert "INSUFFICIENT" in rep.verdict()


def test_empty_dataset_is_insufficient_not_crash():
    rep = evaluate([], holdout_frac=0.3)
    assert rep.outcomes == []
    assert "INSUFFICIENT" in rep.verdict()
    assert rep.mean_success_delta() is None
