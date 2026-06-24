"""
Tests for the memory-recall release gate (evaluation/memory_recall_bench.py +
evaluation/memory_gate.py).

Two things are under test:
  1. The benchmark's three trust invariants hold under the production ranking
     formula (recall, provenance ordering, currency safety) — and the scoring
     primitives that back them behave directionally.
  2. The gate fails *closed*: synthesis is allowed only behind a fresh PASS.

Gate state is isolated per-test via AMAGRA_DATA_DIR so the real logs/ verdict is
never touched.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation import memory_recall_bench as bench
from evaluation import memory_gate


# ── benchmark invariants ──────────────────────────────────────────────────────

def test_synthetic_benchmark_passes():
    report = bench.run_synthetic(n_topics=40)
    assert report["passed"] is True, report["failures"]
    for k, th in bench.THRESHOLDS.items():
        assert report["metrics"][k] >= th, f"{k} below threshold"


def test_synthetic_is_deterministic():
    a = bench.run_synthetic(n_topics=25, seed=3)
    b = bench.run_synthetic(n_topics=25, seed=3)
    assert a["metrics"] == b["metrics"]


def test_score_penalizes_staleness():
    """A high-quality but stale memory must score below an identical fresh one —
    the safety-critical invariant: stale never wins on age-blind quality alone."""
    vec = np.ones(bench._DIM)
    fresh = {"vec": vec, "type": "decision", "quality": 1.0,
             "ts": datetime.now(timezone.utc).isoformat()}
    stale = {"vec": vec, "type": "decision", "quality": 1.0,
             "ts": (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()}
    q = np.ones(bench._DIM)
    assert bench._score(q, fresh) > bench._score(q, stale)


def test_score_rewards_provenance():
    """Explicit (quality 1.0) outranks derived (quality 0.6) at equal similarity."""
    vec = np.ones(bench._DIM)
    explicit = {"vec": vec, "type": "decision", "quality": 1.0,
                "ts": datetime.now(timezone.utc).isoformat()}
    derived  = {"vec": vec, "type": "decision", "quality": 0.6,
                "ts": datetime.now(timezone.utc).isoformat()}
    q = np.ones(bench._DIM)
    assert bench._score(q, explicit) > bench._score(q, derived)


def test_verdict_fails_when_metric_below_threshold():
    bad = bench._verdict("synthetic",
                         {"recall_at_3": 0.5, "provenance_order_rate": 1.0,
                          "currency_safety_rate": 1.0}, 10, [])
    assert bad["passed"] is False
    assert any("recall_at_3" in f for f in bad["failures"])


# ── gate: fails closed ────────────────────────────────────────────────────────

def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_gate_blocked_without_verdict(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DATA_DIR", str(tmp_path))
    assert memory_gate.read_verdict() is None
    assert memory_gate.synthesis_allowed() is False
    assert memory_gate.status()["allowed"] is False


def test_gate_blocked_on_fail_verdict(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DATA_DIR", str(tmp_path))
    memory_gate.write_verdict({"passed": False, "failures": ["recall_at_3=0.50 < 0.90"],
                               "generated_at": _iso(0)})
    assert memory_gate.synthesis_allowed() is False
    assert "FAIL" in memory_gate.status()["reason"]


def test_gate_blocked_on_stale_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DATA_DIR", str(tmp_path))
    memory_gate.write_verdict({"passed": True,
                               "generated_at": _iso(memory_gate.VERDICT_TTL_DAYS + 5)})
    assert memory_gate.synthesis_allowed() is False
    assert "stale" in memory_gate.status()["reason"]


def test_gate_allows_fresh_pass(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DATA_DIR", str(tmp_path))
    memory_gate.write_verdict({"passed": True, "generated_at": _iso(0)})
    assert memory_gate.synthesis_allowed() is True
    assert memory_gate.status()["allowed"] is True


def test_write_verdict_stamps_generated_at(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DATA_DIR", str(tmp_path))
    memory_gate.write_verdict({"passed": True})
    assert memory_gate.read_verdict().get("generated_at")
