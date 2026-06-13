"""
Unit tests for cognition/coherence.py pure functions:
  _c_routing, _c_calib, _c_quality, print_coherence, print_dynamics,
  print_reflection_test, reflection_gain_analysis (empty DB).
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.coherence as ch


def _dec(conflict=False, reflect=False, regret=0.0):
    return {"conflict": conflict, "reflect": reflect, "regret": regret}


# ── _c_routing ────────────────────────────────────────────────────────────────

def test_c_routing_empty():
    c, rate = ch._c_routing([])
    assert c == 0.5
    assert rate == 0.5

def test_c_routing_no_conflicts():
    decisions = [_dec(conflict=False)] * 10
    c, rate = ch._c_routing(decisions)
    assert c == 1.0
    assert rate == 0.0

def test_c_routing_all_conflicts():
    decisions = [_dec(conflict=True)] * 10
    c, rate = ch._c_routing(decisions)
    assert c == 0.0
    assert rate == 1.0

def test_c_routing_mixed():
    decisions = [_dec(conflict=True)] * 3 + [_dec(conflict=False)] * 7
    c, rate = ch._c_routing(decisions)
    assert abs(rate - 0.3) < 0.001
    assert abs(c - 0.7) < 0.001


# ── _c_calib ──────────────────────────────────────────────────────────────────

def test_c_calib_empty():
    assert ch._c_calib({}) == 1.0

def test_c_calib_perfect():
    assert ch._c_calib({"agent1": 0.0, "agent2": 0.0}) == 1.0

def test_c_calib_full_error():
    assert ch._c_calib({"agent1": 1.0}) == 0.0

def test_c_calib_half():
    val = ch._c_calib({"a": 0.5})
    assert abs(val - 0.5) < 0.001


# ── _c_quality ────────────────────────────────────────────────────────────────

def test_c_quality_empty():
    assert ch._c_quality([]) == 0.75

def test_c_quality_no_conflicts():
    decisions = [_dec(conflict=False)] * 10
    q = ch._c_quality(decisions)
    assert q == ch._PROXY_NO_CONFLICT

def test_c_quality_all_conflicts():
    decisions = [_dec(conflict=True)] * 10
    q = ch._c_quality(decisions)
    assert q == ch._PROXY_CONFLICT

def test_c_quality_mixed():
    decisions = [_dec(conflict=True), _dec(conflict=False)]
    q = ch._c_quality(decisions)
    expected = (ch._PROXY_CONFLICT + ch._PROXY_NO_CONFLICT) / 2
    assert abs(q - expected) < 0.001


# ── reflection_gain_analysis ──────────────────────────────────────────────────

def test_reflection_gain_analysis_structure():
    result = ch.reflection_gain_analysis()
    assert "n" in result
    assert "mean" in result
    assert "positive_frac" in result

def test_reflection_gain_analysis_no_data():
    result = ch.reflection_gain_analysis()
    if result["n"] == 0:
        assert result["mean"] == 0.0


# ── print_coherence ───────────────────────────────────────────────────────────

def _make_state(**kwargs):
    defaults = dict(
        C=0.82, c_routing=0.85, c_calib=0.78, c_quality=0.80,
        conflict_rate=0.15, reflection_rate=0.25, mean_regret=0.05,
        G_r_mean=0.03, G_r_std=0.01, G_r_positive=0.75, G_r_n=12,
        mem_avg_quality=0.77, mem_n=150, n_decisions=100,
    )
    defaults.update(kwargs)
    return ch.CoherenceState(**defaults)


def test_print_coherence(capsys):
    state = _make_state()
    ch.print_coherence(state)
    captured = capsys.readouterr()
    assert "0.8200" in captured.out
    assert "COHERENT" in captured.out

def test_print_coherence_degraded(capsys):
    state = _make_state(C=0.50, c_routing=0.55, c_calib=0.45, c_quality=0.50,
                        conflict_rate=0.45, G_r_n=5, mem_n=30, n_decisions=20)
    ch.print_coherence(state)
    captured = capsys.readouterr()
    assert "DEGRADED" in captured.out


# ── print_dynamics ────────────────────────────────────────────────────────────

def test_print_dynamics(capsys):
    series = [
        {"window_idx": 1, "C": 0.75, "c_routing": 0.80, "c_calib": 0.70, "c_quality": 0.75,
         "conflict_rate": 0.20, "reflect_rate": 0.15},
        {"window_idx": 2, "C": 0.78, "c_routing": 0.82, "c_calib": 0.72, "c_quality": 0.78,
         "conflict_rate": 0.18, "reflect_rate": 0.18},
    ]
    ch.print_dynamics(series)
    captured = capsys.readouterr()
    assert "0.7500" in captured.out

def test_print_dynamics_empty(capsys):
    ch.print_dynamics([])
    captured = capsys.readouterr()
    assert "Coherence Dynamics" in captured.out


# ── print_reflection_test ─────────────────────────────────────────────────────

def test_print_reflection_test_no_data(capsys):
    ch.print_reflection_test({"n": 0, "mean": 0.0, "std": 0.0, "positive_frac": 0.0})
    captured = capsys.readouterr()
    assert "No reflection data" in captured.out

def test_print_reflection_test_positive(capsys):
    gains = {"n": 10, "mean": 0.05, "std": 0.02, "positive_frac": 0.7, "min": -0.01, "max": 0.12}
    ch.print_reflection_test(gains)
    captured = capsys.readouterr()
    assert "SUPPORTED" in captured.out

def test_print_reflection_test_negative(capsys):
    gains = {"n": 5, "mean": -0.03, "std": 0.04, "positive_frac": 0.4, "min": -0.08, "max": 0.02}
    ch.print_reflection_test(gains)
    captured = capsys.readouterr()
    assert "NOT SUPPORTED" in captured.out
