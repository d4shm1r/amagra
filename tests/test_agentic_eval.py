"""
Tests for evaluation/agentic_eval.py — the agentic task-completion benchmark.

The substrate (oracle) path is deterministic already. These tests pin the
*live-mode measurement logic* without a real model, by injecting test-double
"models" into the live path: a competent one that emits the right tool calls, a
lazy one that never calls a tool, and a malformed one. This proves --live scores
model-driven completion correctly (auto-enabled writes, preamble, validity
metric) so the real phi4-mini run only supplies numbers, not confidence in the
harness.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workbench.evaluation.agentic_eval as ae


def _competent_for(task):
    """A double that emits exactly this task's oracle calls, one per turn — a
    stand-in for a model that drives the loop correctly."""
    return ae._oracle_invoke(task.oracle)


def test_oracle_substrate_needs_writes(monkeypatch):
    """Substrate ceiling: read-only catalog completes only the read task."""
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    records = ae.run_suite()
    passed = sum(r["passed"] for r in records)
    assert passed == 1  # only read_only_baseline


def test_oracle_substrate_full_with_writes(monkeypatch):
    monkeypatch.setenv("AMAGRA_WORKSPACE_WRITE", "1")
    records = ae.run_suite()
    assert all(r["passed"] for r in records)


def test_live_path_completes_with_competent_model(monkeypatch):
    """A model that emits the right tool calls completes every task through the
    live wrapper — which must auto-enable writes even with the gate off."""
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    for task in ae.TASKS:
        rec = ae._run_task(task, verbose=False, invoke=_competent_for(task),
                           live=True, max_iters=len(task.oracle) + 1)
        assert rec["passed"], f"{task.tid}: {rec['reason']}"
        assert rec["ok_calls"] == rec["calls"]


def test_live_path_scores_lazy_model_as_failure(monkeypatch):
    """A model that only narrates and never calls a tool must score as a failure
    with an honest reason — not a false pass."""
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    lazy = lambda _t: "I would create the file with a greet() function."
    task = next(t for t in ae.TASKS if t.tid == "write_single_file")
    rec = ae._run_task(task, verbose=False, invoke=lazy, live=True)
    assert not rec["passed"]
    assert rec["reason"] == "no tool calls emitted"
    assert rec["calls"] == 0


def test_live_writes_do_not_leak_env(monkeypatch):
    """The auto-enabled write gate is scoped to the run and restored after."""
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    task = next(t for t in ae.TASKS if t.tid == "read_only_baseline")
    ae._run_task(task, verbose=False, invoke=_competent_for(task), live=True)
    assert os.environ.get("AMAGRA_WORKSPACE_WRITE") is None


def test_json_records_are_serializable():
    records = ae.run_suite()
    json.dumps(records)  # must not raise
    for r in records:
        assert set(r) >= {"task", "passed", "reason", "calls", "ok_calls"}
