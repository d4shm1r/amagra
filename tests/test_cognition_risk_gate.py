"""
Unit tests for cognition/risk_gate.py — compute_risk pure function.
Uses log=False to avoid DB writes.
"""

import os, sys
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
    # Low confidence, high regret, ambiguous, complex action
    s = rg.compute_risk(
        action="build",
        confidence=0.30,
        regret=0.8,
        complexity="compound",
        planner_uncertainty=0.9,
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
