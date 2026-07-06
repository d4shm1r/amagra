"""
v1.5 Hybrid Inference — run-tracer cost telemetry (no LLM, no network).

record_cost() accumulates inference cost on a run; finish() persists it;
get_run() reads it back; cost_summary() aggregates over recent runs.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tracer(tmp_path, monkeypatch):
    """Fresh run_tracer bound to an isolated runs DB under tmp_path."""
    import importlib
    monkeypatch.setenv("AMAGRA_DB", str(tmp_path / "amagra.db"))
    import cognition.run_tracer as run_tracer
    importlib.reload(run_tracer)
    return run_tracer


def test_record_cost_accumulates_and_persists(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    run_id = rt.start("a compound query")
    rt.record_cost(run_id, cost_usd=0.012, tokens_in=100, tokens_out=200,
                   provider="anthropic/claude-sonnet-4-6", escalated=True)
    # A second generation in the same run accumulates.
    rt.record_cost(run_id, cost_usd=0.008, tokens_in=50, tokens_out=50,
                   provider="anthropic/claude-sonnet-4-6", escalated=True)
    rt.finish(run_id, agent="python_dev", duration_ms=42)

    trace = rt.get_run(run_id)
    assert abs(trace["cost_usd"] - 0.020) < 1e-9
    assert trace["tokens_in"] == 150
    assert trace["tokens_out"] == 250
    assert trace["escalated"] is True
    assert trace["gen_provider"] == "anthropic/claude-sonnet-4-6"


def test_local_run_has_zero_cost(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    run_id = rt.start("simple local query")
    rt.finish(run_id, agent="terse", duration_ms=10)
    trace = rt.get_run(run_id)
    assert trace["cost_usd"] == 0.0
    assert trace["escalated"] is False


def test_cost_summary_aggregates(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    # one escalated run, one local run
    r1 = rt.start("hard")
    rt.record_cost(r1, cost_usd=0.05, tokens_in=10, tokens_out=20, escalated=True)
    rt.finish(r1, agent="ai_ml")
    r2 = rt.start("easy")
    rt.finish(r2, agent="terse")

    summary = rt.cost_summary()
    assert summary["runs"] == 2
    assert abs(summary["total_cost_usd"] - 0.05) < 1e-9
    assert summary["escalated_runs"] == 1
    assert summary["escalation_rate"] == 0.5
    assert summary["tokens_out"] == 20


def test_cost_summary_empty_is_zero(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    summary = rt.cost_summary()
    assert summary["runs"] == 0
    assert summary["total_cost_usd"] == 0.0
    assert summary["escalation_rate"] == 0.0


# ── Self-consistency vote telemetry (step 2 — measure-first) ──

def test_record_vote_persists(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    run_id = rt.start("A box has 8 rows of 9 apples. How many total?")
    rt.record_vote(run_id, confidence=0.6, votes=3, valid=5, escalated=False)
    rt.finish(run_id, agent="knowledge_learning", duration_ms=30)

    trace = rt.get_run(run_id)
    assert trace["vote_confidence"] == 0.6
    assert trace["vote_votes"] == 3
    assert trace["vote_valid"] == 5
    assert trace["vote_escalated"] is False


def test_vote_columns_null_when_self_consistency_off(tmp_path, monkeypatch):
    # A run where record_vote was never called (SC off / non-numeric) leaves the
    # vote columns NULL, so calibration queries can filter to real votes.
    rt = _tracer(tmp_path, monkeypatch)
    run_id = rt.start("explain tcp")
    rt.finish(run_id, agent="terse", duration_ms=5)

    trace = rt.get_run(run_id)
    assert trace["vote_confidence"] is None
    assert trace["vote_escalated"] is None


def test_low_agreement_vote_records_escalation(tmp_path, monkeypatch):
    rt = _tracer(tmp_path, monkeypatch)
    run_id = rt.start("split arithmetic")
    rt.record_vote(run_id, confidence=0.4, votes=2, valid=5, escalated=True)
    rt.finish(run_id, agent="knowledge_learning")

    trace = rt.get_run(run_id)
    assert trace["vote_confidence"] == 0.4
    assert trace["vote_escalated"] is True
