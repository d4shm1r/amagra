"""
Tests for the closed-loop executor behaviour in cognition/deep_pipeline.py.

Two capabilities are pinned here, both with fake runners (no model, no I/O):
  observation threading — a step executes with prior steps' outputs in its task
  bounded replan        — a "replan" verdict re-decomposes the remaining work once,
                          and AMAGRA_PIPELINE_REPLAN=0 restores commit-and-continue.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.deep_pipeline as dp
import cognition.step_verifier as sv
from orchestration.planner import PlanStep


class _Msg:
    """A real content-bearing message. langchain_core is MagicMock-stubbed in this
    test env (conftest.py), so AIMessage would swallow the content we assert on."""
    def __init__(self, content):
        self.content = content


def _recording_runner_map(seen_tasks: list):
    """One runner, shared across agents, that records the task it received and
    returns a distinctively-tagged response so threading is observable."""
    def runner(state):
        n = len(seen_tasks) + 1
        seen_tasks.append(state["task"])
        return {"messages": [_Msg(f"RESPONSE_{n}: completed the step")]}

    from agents.registry import AGENT_IDS
    return {a: runner for a in AGENT_IDS}


def _verification(step, recommendation, passed, score):
    return sv.StepVerification(
        step_id=getattr(step, "step_id", "x"),
        passed=passed, raw_score=score, threshold=0.6,
        recommendation=recommendation,
        issues=[] if passed else ["step failed"],
    )


def _always(recommendation, passed=True, score=0.9):
    """A verify_step stand-in that always returns one recommendation."""
    def fake(step, response, retries_remaining=1, log=True):
        return _verification(step, recommendation, passed, score)
    return fake


def _sequence(recommendations):
    """verify_step stand-in that returns a scripted recommendation per call."""
    calls = {"n": 0}

    def fake(step, response, retries_remaining=1, log=True):
        rec = recommendations[calls["n"]] if calls["n"] < len(recommendations) else "continue"
        calls["n"] += 1
        passed = rec == "continue"
        return _verification(step, rec, passed, 0.9 if passed else 0.4)
    return fake


def test_observations_thread_into_later_steps(monkeypatch):
    monkeypatch.setenv("AMAGRA_PIPELINE_REPLAN", "0")   # isolate threading
    monkeypatch.setattr(sv, "verify_step", _always("continue"))

    seen = []
    dp.run_deep_pipeline(
        query="Explain and demonstrate binary search",
        agents=["knowledge_learning"],
        state={},
        agent_runner_map=_recording_runner_map(seen),
        action="explain", complexity="simple",
    )

    assert len(seen) >= 2, "expected a multi-step plan"
    # The first step's task has no prior context; a later one carries the digest.
    assert "Context from completed steps" not in seen[0]
    assert any("Context from completed steps" in t and "RESPONSE_1" in t
               for t in seen[1:]), "prior step output was not threaded forward"


def test_replan_splices_remaining_work(monkeypatch):
    monkeypatch.setenv("AMAGRA_PIPELINE_REPLAN", "1")
    # First step → replan; everything after → continue.
    monkeypatch.setattr(sv, "verify_step", _sequence(["replan"]))

    called = {"n": 0}

    def fake_replan(query, agents, action, complexity, done_count, failure_note, tag):
        called["n"] += 1
        step = PlanStep(step_id=f"{tag}_recovered", description="recovered step",
                        agent="knowledge_learning", uncertainty=0.3)
        sub = {"agent": "knowledge_learning",
               "sub_task": "recovered step", "step_id": step.step_id,
               "uncertainty": 0.3}
        return [step], [sub]

    monkeypatch.setattr(dp, "_replan_remaining", fake_replan)

    seen = []
    result = dp.run_deep_pipeline(
        query="Build a thing", agents=["python_dev", "knowledge_learning"],
        state={}, agent_runner_map=_recording_runner_map(seen),
        action="build", complexity="compound",
    )

    assert called["n"] == 1, "replan should fire exactly once"
    step_ids = [r.get("step_id") for r in
                _pipeline_step_ids(result)]
    assert any(str(sid).endswith("_recovered") for sid in step_ids), \
        "spliced recovery step never ran"


def test_replan_budget_zero_restores_old_behaviour(monkeypatch):
    monkeypatch.setenv("AMAGRA_PIPELINE_REPLAN", "0")
    monkeypatch.setattr(sv, "verify_step", _sequence(["replan"]))

    called = {"n": 0}

    def fake_replan(*a, **k):
        called["n"] += 1
        return [], []

    monkeypatch.setattr(dp, "_replan_remaining", fake_replan)

    seen = []
    dp.run_deep_pipeline(
        query="Build a thing", agents=["python_dev", "knowledge_learning"],
        state={}, agent_runner_map=_recording_runner_map(seen),
        action="build", complexity="compound",
    )
    assert called["n"] == 0, "budget=0 must not replan"


def _pipeline_step_ids(result):
    """Reconstruct the executed step records from the pipeline result."""
    return result.get("pipeline_responses", [])
