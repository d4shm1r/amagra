"""
Unit tests for cognition/trace_builder.py pure functions:
  _quality_proxy, dataset_stats, load_cached_traces, _features_from_trace.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.trace_builder as tb


# ── _quality_proxy ────────────────────────────────────────────────────────────

def test_quality_proxy_no_feedback_no_reflect():
    q = tb._quality_proxy(regret=0.0, conflict=False, reflect=False, feedback_rating=None)
    assert 0.0 <= q <= 1.0
    assert q == 0.72  # base without reflect

def test_quality_proxy_with_reflect():
    q = tb._quality_proxy(regret=0.0, conflict=False, reflect=True, feedback_rating=None)
    assert q == 0.82  # reflect base

def test_quality_proxy_positive_feedback():
    q = tb._quality_proxy(regret=0.0, conflict=False, reflect=True, feedback_rating=1)
    assert q > 0.82  # positive feedback adds bonus

def test_quality_proxy_negative_feedback():
    q = tb._quality_proxy(regret=0.0, conflict=False, reflect=True, feedback_rating=-1)
    assert q < 0.82  # negative feedback deducts

def test_quality_proxy_high_regret():
    q_low  = tb._quality_proxy(regret=0.0, conflict=False, reflect=False, feedback_rating=None)
    q_high = tb._quality_proxy(regret=1.0, conflict=False, reflect=False, feedback_rating=None)
    assert q_high < q_low

def test_quality_proxy_conflict_penalty():
    q_no  = tb._quality_proxy(regret=0.0, conflict=False, reflect=False, feedback_rating=None)
    q_yes = tb._quality_proxy(regret=0.0, conflict=True,  reflect=False, feedback_rating=None)
    assert q_yes < q_no

def test_quality_proxy_bounded():
    q = tb._quality_proxy(regret=99.0, conflict=True, reflect=False, feedback_rating=-1)
    assert q >= 0.0
    q = tb._quality_proxy(regret=0.0, conflict=False, reflect=True, feedback_rating=1)
    assert q <= 1.0

def test_quality_proxy_rounded():
    q = tb._quality_proxy(regret=0.1, conflict=False, reflect=True, feedback_rating=None)
    assert round(q, 3) == q


# ── dataset_stats ─────────────────────────────────────────────────────────────

def test_dataset_stats_empty():
    result = tb.dataset_stats([])
    assert isinstance(result, dict)
    assert result.get("total", 0) == 0

def _make_trace(domain="python", agent="python_dev", action="respond"):
    return {
        "id": "t1",
        "query": "test query",
        "signal": {"domain": domain, "conf": 0.8, "shape": "code", "verbosity": "normal"},
        "routing": {"final_agent": agent, "action": action},
        "memory": {"count": 5},
        "outcome": {"quality_proxy": 0.85, "regret": 0.05},
        "labels": {
            "is_eval": False,
            "has_response": True,
            "has_memory": True,
            "has_feedback": False,
            "has_reflection": True,
            "has_conflict": False,
            "join_method": "fk",
            "join_confidence": 1.0,
        }
    }


def test_dataset_stats_with_traces():
    traces = [_make_trace("python", "python_dev"), _make_trace("networking", "it_networking")]
    result = tb.dataset_stats(traces)
    assert isinstance(result, dict)
    assert result.get("total", 0) == 2

def test_dataset_stats_structure():
    traces = [_make_trace()]
    result = tb.dataset_stats(traces)
    assert "total" in result
    assert "agent_distribution" in result
    assert "coverage" in result


# ── load_cached_traces ────────────────────────────────────────────────────────

def test_load_cached_traces_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(tb, "_OUT_JSONL", str(tmp_path / "nonexistent.jsonl"))
    result = tb.load_cached_traces()
    assert isinstance(result, list)

def test_load_cached_traces_returns_list():
    result = tb.load_cached_traces()
    assert isinstance(result, list)
