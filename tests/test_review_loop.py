"""Tests for the review-loop topology (AMAGRA_REVIEW_LOOP).

The revision cycle used to be a hidden `if gate_score < THRESH: regenerate` inside
the agent node. These tests pin the behaviour of lifting it into graph structure:
  * reviewer_node's verdict logic: pass / fail / exhausted + keep-best
  * route_after_review: fail loops back to the drafting agent, else → finalize
  * the compiled cycle is BOUNDED (max_revisions) and keeps the best draft

The cycle test wires the *real* reviewer + router around a stub agent and a stub
terminal, so it exercises the loop-back edge without dragging in finalize's
reflection/learning side effects. grounded_evaluate is monkeypatched — no LLM.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import orchestration.coordinator as coordinator


def _msg(text):
    """Lightweight stand-in for an AIMessage (langchain_core is stubbed here)."""
    return types.SimpleNamespace(content=text, id=None)


# ── reviewer_node verdict logic ──────────────────────────────────────

def _review(monkeypatch, score, *, revise_count=0, best_score=-1.0,
            best_response="", max_revisions=1, response="draft"):
    monkeypatch.setattr(coordinator, "grounded_evaluate",
                        lambda *a, **k: {"score": score})
    state = {
        "task": "q",
        "messages": [_msg(response)],
        "active_agent": "python_dev",
        "reflect_type": "code",
        "revise_count": revise_count,
        "best_score": best_score,
        "best_response": best_response,
        "max_revisions": max_revisions,
    }
    return coordinator.reviewer_node(state)


def test_reviewer_passes_when_score_clears_threshold(monkeypatch):
    out = _review(monkeypatch, 0.90)
    assert out["review_verdict"] == "pass"
    assert out["revise_count"] == 1
    assert out["best_score"] == 0.9


def test_reviewer_fails_when_revisions_remain(monkeypatch):
    out = _review(monkeypatch, 0.30, max_revisions=2)
    assert out["review_verdict"] == "fail"      # tries=1 <= ceiling=2


def test_reviewer_exhausts_instead_of_looping_forever(monkeypatch):
    # Already used our one allowed revision → must stop, not fail again.
    out = _review(monkeypatch, 0.30, revise_count=1, max_revisions=1)
    assert out["review_verdict"] == "exhausted"


def test_reviewer_keeps_best_draft(monkeypatch):
    # A worse current draft (0.4) must not displace a better earlier one (0.5).
    out = _review(monkeypatch, 0.40, revise_count=1, max_revisions=2,
                  best_score=0.5, best_response="earlier")
    assert out["best_score"] == 0.5
    assert out["best_response"] == "earlier"


# ── route_after_review: the loop-back edge ───────────────────────────

def test_route_fail_loops_back_to_active_agent():
    assert coordinator.route_after_review(
        {"review_verdict": "fail", "active_agent": "web_dev"}) == "web_dev"


def test_route_pass_and_exhausted_go_to_finalize():
    assert coordinator.route_after_review({"review_verdict": "pass"}) == "finalize"
    assert coordinator.route_after_review({"review_verdict": "exhausted"}) == "finalize"


# ── The cycle, end to end: bounded + keep-best ───────────────────────
# langgraph is stubbed in this suite, so we drive the real reviewer + router by
# hand exactly as the compiled graph would: draft → review → (fail: loop back to
# the agent and re-draft | else: stop). The hard iteration cap proves the cycle
# terminates rather than spinning on the loop-back edge.

def _run_cycle(scores, monkeypatch, max_revisions, cap=50):
    calls = {"n": 0}
    score_iter = iter(scores)
    monkeypatch.setattr(coordinator, "grounded_evaluate",
                        lambda *a, **k: {"score": next(score_iter)})

    state = {"task": "q", "active_agent": "agent", "reflect_type": "code",
             "max_revisions": max_revisions}

    def draft():                       # the "agent" node
        calls["n"] += 1
        state["messages"] = [_msg(f"draft{calls['n']}")]

    draft()
    for _ in range(cap):
        state.update(coordinator.reviewer_node(state))
        if coordinator.route_after_review(state) == "finalize":
            break
        draft()                        # route_after_review sent us back to the agent
    else:
        raise AssertionError("cycle never reached finalize — loop-back is unbounded")
    return state, calls


def test_cycle_passes_on_first_good_draft(monkeypatch):
    final, calls = _run_cycle([0.90], monkeypatch, max_revisions=2)
    assert calls["n"] == 1                       # no revision needed
    assert final["review_verdict"] == "pass"


def test_cycle_is_bounded_and_keeps_best(monkeypatch):
    # Three failing drafts, best in the middle. ceiling=2 → 3 drafts then exhausted.
    final, calls = _run_cycle([0.30, 0.50, 0.40], monkeypatch, max_revisions=2)
    assert final["review_verdict"] == "exhausted"
    assert calls["n"] == 3                        # bounded: ceiling + 1, not infinite
    assert final["revise_count"] == 3
    assert final["best_score"] == 0.5            # kept the best, not the last (0.4)
    assert final["best_response"] == "draft2"
