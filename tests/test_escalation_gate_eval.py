"""
Hermetic tests for the self-consistency escalation-gate analysis
(evaluation/escalation_gate_eval.py). Pure arithmetic over synthetic vote
records — no model, no logs, no network. The gate reuses the SHIPPED
`cognition.self_consistency.escalation_decision` (agreement < 0.6 → escalate).
"""
import math

import pytest

from evaluation.escalation_gate_eval import escalates, analyze_gate


def _rec(correct, votes, valid):
    return {"correct": correct, "votes": votes, "valid": valid}


# ── escalates: mirrors the shipped agreement gate ─────────────────────────────
def test_escalates_below_threshold():
    assert escalates(_rec(True, 2, 5), 0.6) is True    # 0.40 < 0.60


def test_trusts_at_boundary():
    # 3/5 = 0.60 exactly → trust (production uses a +epsilon boundary)
    assert escalates(_rec(True, 3, 5), 0.6) is False


def test_escalates_on_zero_valid():
    assert escalates(_rec(False, 0, 0), 0.6) is True   # nothing parsed → escalate


# ── analyze_gate ──────────────────────────────────────────────────────────────
def test_bucket_split_and_accuracy():
    voted = [
        _rec(True,  5, 5),   # 1.0 → trust, correct
        _rec(True,  3, 5),   # 0.6 → trust, correct
        _rec(False, 2, 5),   # 0.4 → escalate, wrong
        _rec(True,  2, 5),   # 0.4 → escalate, correct
    ]
    r = analyze_gate(voted, trust_agreement=0.6)
    assert r["n"] == 4
    assert r["trust"]["n"] == 2 and r["trust"]["acc"] == 1.0
    assert r["escalate"]["n"] == 2 and r["escalate"]["acc"] == 0.5
    assert r["voted_acc"] == 0.75


def test_error_capture_concentration():
    # every error sits in the low-agreement bucket → capture = 1.0
    voted = [_rec(True, 5, 5), _rec(False, 2, 5), _rec(False, 1, 5), _rec(False, 2, 5)]
    r = analyze_gate(voted, trust_agreement=0.6)
    assert r["error_capture"] == 1.0


def test_gated_accuracy_simulation_is_linear():
    # trust: 1 correct (frac .5, acc 1.0); escalate: 1 wrong (frac .5, acc 0.0)
    voted = [_rec(True, 5, 5), _rec(False, 2, 5)]
    r = analyze_gate(voted, trust_agreement=0.6, ceiling_grid=(0.0, 1.0))
    g = {row["ceiling_acc"]: row for row in r["gated"]}
    assert math.isclose(g[0.0]["gated_acc"], 0.5)      # 0.5*1.0 + 0.5*0.0
    assert math.isclose(g[1.0]["gated_acc"], 1.0)      # 0.5*1.0 + 0.5*1.0
    assert math.isclose(g[1.0]["lift_over_voted"], 0.5)
    assert g[1.0]["escalation_rate"] == 0.5


def test_break_even_equals_escalate_acc():
    voted = [_rec(True, 5, 5), _rec(True, 2, 5), _rec(False, 1, 5)]
    r = analyze_gate(voted, trust_agreement=0.6)
    assert r["break_even_ceiling"] == r["escalate"]["acc"]


def test_empty_raises():
    with pytest.raises(ValueError):
        analyze_gate([])
