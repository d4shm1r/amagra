"""
Unit tests for cognition/risk_gate.py — compute_risk pure function.
Uses log=False to avoid DB writes.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.risk_gate as rg


# ── compute_risk output structure ─────────────────────────────────────────────

def test_compute_risk_returns_signal():
    s = rg.compute_risk(log=False)
    assert hasattr(s, "total_risk")
    assert hasattr(s, "reflect_level")
    assert hasattr(s, "reflect_type")

def test_compute_risk_bounded():
    s = rg.compute_risk(log=False)
    assert 0.0 <= s.total_risk <= 1.0

def test_compute_risk_reflect_level_valid():
    s = rg.compute_risk(log=False)
    assert s.reflect_level in ("none", "light", "full")


# ── reflect level thresholds ─────────────────────────────────────────────────

def test_compute_risk_low_returns_none():
    # High confidence, zero regret, simple action = low risk
    s = rg.compute_risk(
        action="respond",
        confidence=0.99,
        regret=0.0,
        complexity="simple",
        planner_uncertainty=0.0,
        log=False,
    )
    assert s.reflect_level in ("none", "light")  # should be very low

def test_compute_risk_high_returns_full():
    # Low confidence, high regret, complex action.
    # NB: this deliberately supplies no planner_uncertainty. It used to pass
    # 0.9 — the one signal production can never supply — which is precisely why
    # the unreachable-`full` bug survived a green suite until 2026-07-16.
    s = rg.compute_risk(
        action="build",
        confidence=0.30,
        regret=0.8,
        complexity="compound",
        log=False,
    )
    assert s.reflect_level == "full"

def test_compute_risk_unknown_action():
    s = rg.compute_risk(action="unknown", log=False)
    assert s.total_risk >= 0.0

def test_compute_risk_all_actions():
    for action in ["respond", "build", "debug", "review", "plan", "explain", "unknown"]:
        s = rg.compute_risk(action=action, log=False)
        assert 0.0 <= s.total_risk <= 1.0


# ── component risks ───────────────────────────────────────────────────────────

def test_action_risk_in_signal():
    s = rg.compute_risk(log=False)
    assert hasattr(s, "action_risk")
    assert 0.0 <= s.action_risk <= 1.0

def test_routing_uncertainty_in_signal():
    s = rg.compute_risk(confidence=0.5, regret=0.1, log=False)
    assert hasattr(s, "routing_uncertainty")
    assert 0.0 <= s.routing_uncertainty <= 1.0

def test_complexity_compound_higher_than_simple():
    s_simple   = rg.compute_risk(complexity="simple",   log=False)
    s_compound = rg.compute_risk(complexity="compound", log=False)
    assert s_compound.complexity_risk > s_simple.complexity_risk

def test_confidence_inverse_relationship():
    s_high = rg.compute_risk(confidence=0.95, regret=0.0, log=False)
    s_low  = rg.compute_risk(confidence=0.30, regret=0.0, log=False)
    assert s_low.total_risk > s_high.total_risk


# ── reflect_type ──────────────────────────────────────────────────────────────

def test_reflect_type_for_python_dev():
    s = rg.compute_risk(primary_agent="python_dev", log=False)
    assert isinstance(s.reflect_type, str)
    assert len(s.reflect_type) > 0

def test_reflect_type_for_unknown_agent():
    s = rg.compute_risk(primary_agent="nonexistent_agent_xyz", log=False)
    assert s.reflect_type == "general"  # fallback


# ── reflect_depth — the continuous dial (#110) ────────────────────────────────

def test_reflect_depth_zero_outside_full():
    # none and light do no correction, so they have no depth to grade.
    for level, kw in [
        ("none",  dict(action="lookup", confidence=0.99, complexity="simple")),
        ("light", dict(action="research", confidence=0.72, complexity="simple")),
    ]:
        s = rg.compute_risk(log=False, **kw)
        if s.reflect_level == level:
            assert s.reflect_depth == 0.0, f"{level} should have depth 0"

def test_reflect_depth_bounded():
    for conf in (0.30, 0.50, 0.70, 0.90, 0.99):
        for action in ("debug", "build", "lookup", "explain"):
            s = rg.compute_risk(action=action, confidence=conf, log=False)
            assert 0.0 <= s.reflect_depth <= 1.0

def test_reflect_depth_monotone_in_risk():
    # Within full, more risk must never mean less correction depth.
    seen = sorted(
        (s.total_risk, s.reflect_depth)
        for s in (
            rg.compute_risk(action=a, confidence=c, regret=r,
                            complexity=x, log=False)
            for a in ("debug", "build", "research")
            for c in (0.3, 0.6, 0.9)
            for r in (0.0, 0.4)
            for x in ("simple", "compound")
        )
        if s.reflect_level == "full"
    )
    for (r1, d1), (r2, d2) in zip(seen, seen[1:]):
        assert d2 >= d1, f"depth fell from {d1} to {d2} as risk rose {r1}→{r2}"

def test_reflect_depth_full_band_endpoints():
    assert rg._risk_to_depth(rg._THRESH_LIGHT, "full") == 0.0   # full begins
    assert rg._risk_to_depth(1.0, "full") == 1.0                # max risk
    assert rg._risk_to_depth(1.0, "light") == 0.0               # kind, not degree

def test_reflect_depth_does_not_change_reflect_level():
    # The dial is additive: it must not perturb the existing three-bucket gate.
    for conf in (0.3, 0.6, 0.9):
        s = rg.compute_risk(action="debug", confidence=conf, log=False)
        expected = ("full" if s.total_risk >= rg._THRESH_LIGHT
                    else "light" if s.total_risk >= rg._THRESH_NONE
                    else "none")
        assert s.reflect_level == expected

def test_full_tier_is_reachable_from_observable_signals():
    # Regression for the 2026-07-16 finding: planner_uncertainty was 25% of the
    # score and structurally always 0.0, pinning the ceiling at exactly
    # _THRESH_LIGHT so `full` never fired (0 of 160 logged runs; max 0.4362).
    # The gate must stay reachable using ONLY signals a caller can supply.
    ceiling = (
        rg._W_ACTION * max(rg._ACTION_RISK.values())
        + rg._W_ROUTING * 1.0
        + rg._W_COMPLEXITY * 0.30
    )
    assert ceiling > rg._THRESH_LIGHT, (
        f"full tier unreachable again: ceiling {ceiling:.4f} <= threshold "
        f"{rg._THRESH_LIGHT}. A weighted signal has gone dead."
    )
    worst = rg.compute_risk(action="debug", confidence=0.0, regret=0.0,
                            complexity="compound", log=False)
    assert worst.reflect_level == "full", "worst realistic case must reach full"

def test_weights_sum_to_one_and_exclude_planner():
    total = rg._W_ACTION + rg._W_ROUTING + rg._W_COMPLEXITY
    assert abs(total - 1.0) < 0.001, f"weights sum to {total}, not 1.0"
    assert not hasattr(rg, "_W_PLANNER"), (
        "_W_PLANNER is back — it cannot be scored unless the gate moved "
        "downstream of plan_query; if it did, re-tune the thresholds too."
    )

def test_planner_uncertainty_recorded_but_not_scored():
    # It is unobservable at gate time, so it must not move the score. If this
    # fails, either the gate moved downstream (fine — update this test) or the
    # dead weight crept back in (not fine).
    a = rg.compute_risk(action="debug", confidence=0.5, complexity="compound",
                        planner_uncertainty=0.0, log=False)
    b = rg.compute_risk(action="debug", confidence=0.5, complexity="compound",
                        planner_uncertainty=1.0, log=False)
    assert a.total_risk == b.total_risk
    assert a.reflect_level == b.reflect_level
    assert b.planner_uncertainty == 1.0     # still recorded as evidence

def test_reflect_depth_band_is_bottom_heavy():
    # The dial's live range: even the worst case the gate can score tops out
    # well below t=1, so a depth->threshold consumer must be calibrated against
    # the logged distribution rather than assuming t spans [0,1].
    worst = rg.compute_risk(action="debug", confidence=0.0, regret=0.0,
                            complexity="compound", log=False)
    assert worst.reflect_level == "full"
    assert worst.reflect_depth < 0.5, (
        f"realistic worst case now reaches depth {worst.reflect_depth}; "
        "the dial band assumption in _risk_to_depth needs revisiting"
    )
