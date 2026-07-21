"""
Tests for evaluation/decision_quality.py — the Amagra Decision Quality Benchmark.

The scorer is the contract here, so these tests pin it directly on hand-built
DecisionRecords rather than the full arena run. The load-bearing invariants:

  * the PENDING tier is never scored or faked — unobserved dimensions must not
    inflate (or deflate) the composite;
  * per-example calibration only fails the dangerous confident-and-wrong case;
  * efficiency ignores sub-millisecond noise and only fails on a material saving.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workbench.evaluation.decision_quality as dq
from workbench.evaluation.decision_quality import DecisionRecord, Verdict, score


def _base(**kw) -> DecisionRecord:
    defaults = dict(
        prompt_id="t1", domain="python", prompt="q",
        expected_agent="python_dev", chosen_agent="python_dev",
        confidence=0.8,
        chosen_latency_ms=0.4, cheapest_correct_latency_ms=0.4,
    )
    defaults.update(kw)
    return DecisionRecord(**defaults)


def test_routing_pass_and_fail():
    assert _base().grade()["routing_correct"] is Verdict.PASS
    assert _base(chosen_agent="ai_ml").grade()["routing_correct"] is Verdict.FAIL


def test_calibration_only_penalises_confident_and_wrong():
    g = lambda **k: _base(**k).grade()["confidence_calibrated"]
    # confident + correct → PASS
    assert g(confidence=0.9) is Verdict.PASS
    # confident + wrong → FAIL (overconfident, the dangerous case)
    assert g(confidence=0.9, chosen_agent="ai_ml") is Verdict.FAIL
    # unsure + wrong → PASS (appropriately uncertain, honest signalling)
    assert g(confidence=0.3, chosen_agent="ai_ml") is Verdict.PASS
    # unsure + correct → PASS
    assert g(confidence=0.3) is Verdict.PASS


def test_calibration_pending_without_confidence():
    assert _base(confidence=None).grade()["confidence_calibrated"] is Verdict.PENDING


def test_efficiency_ignores_sub_millisecond_noise():
    # 0.4ms chosen vs 0.3ms alternative — real but immaterial → PASS.
    assert _base(chosen_latency_ms=0.4,
                 cheapest_correct_latency_ms=0.3).grade()["efficient"] is Verdict.PASS


def test_efficiency_fails_on_material_saving():
    # A correct route at 0.4ms when the chosen one cost 18000ms (LLM tier) → FAIL.
    assert _base(chosen_latency_ms=18000.0,
                 cheapest_correct_latency_ms=0.4).grade()["efficient"] is Verdict.FAIL


def test_efficiency_moot_when_route_wrong():
    rec = _base(chosen_agent="ai_ml",
                chosen_latency_ms=18000.0, cheapest_correct_latency_ms=0.4)
    assert rec.grade()["efficient"] is Verdict.PASS


def test_pending_tier_is_never_graded_by_default():
    grades = _base().grade()
    for dim in ("reflection_necessary", "memory_useful",
                "correct_tool", "correct_final_answer"):
        assert grades[dim] is Verdict.PENDING, dim


def test_pending_tier_grades_once_populated():
    rec = _base(reflection_used=True, reflection_helped=True,
                memory_used=False,
                tool_chosen="none", tool_expected="none",
                answer_correct=True)
    grades = rec.grade()
    assert grades["reflection_necessary"] is Verdict.PASS
    assert grades["memory_useful"] is Verdict.PASS
    assert grades["correct_tool"] is Verdict.PASS
    assert grades["correct_final_answer"] is Verdict.PASS
    # reflection that ran but did not help is wasted cost → FAIL
    assert _base(reflection_used=True, reflection_helped=False,
                 ).grade()["reflection_necessary"] is Verdict.FAIL


def test_composite_averages_only_graded_dimensions():
    # One clean record: 3 graded dims all pass, 4 pending. Composite must be
    # 1.0 (3/3), NOT 3/7 — pending must not dilute the score.
    sc = score([_base()])
    assert sc.composite == 1.0
    assert sc.per_dim["routing_correct"]["graded"] == 1
    assert sc.per_dim["correct_tool"]["graded"] == 0


def test_clean_rate_and_worst_list():
    good = _base(prompt_id="ok")
    bad = _base(prompt_id="bad", chosen_agent="ai_ml", confidence=0.9)  # fails routing+calib
    sc = score([good, bad])
    assert sc.clean_rate == 0.5
    assert sc.worst[0]["pid"] == "bad"
    assert set(sc.worst[0]["failed"]) == {"routing_correct", "confidence_calibrated"}


def test_ece_reflects_underconfidence():
    # conf ~0.4 but everything routed correctly → large calibration gap.
    recs = [_base(prompt_id=f"p{i}", confidence=0.4) for i in range(10)]
    sc = score(recs)
    assert sc.ece is not None and sc.ece > 0.2
    assert sc.mean_conf is not None and abs(sc.mean_conf - 0.4) < 1e-6


def test_records_from_arena_smoke():
    from workbench.auto_train import PROMPTS
    recs = dq.records_from_arena(list(PROMPTS)[:5], "signal_only")
    assert len(recs) == 5
    assert all(r.confidence is not None for r in recs)
    assert all(r.cheapest_correct_latency_ms is not None for r in recs)


# ── pending-tier wiring: adapter + join ───────────────────────────

def test_observation_from_rich_meta():
    obs = dq.observation_from_meta({
        "agent": "python_dev", "confidence": 0.8,
        "reflect_level": "full", "reflect_delta": 0.12,
        "memory_id": 42, "response_quality": 0.71,
        "output": "use uvicorn to serve it",
    })
    assert obs["chosen_agent"] == "python_dev"
    assert obs["reflection_used"] is True
    assert obs["reflection_helped"] is True     # delta > 0
    assert obs["memory_used"] is True
    assert obs["response_quality"] == 0.71


def test_observation_from_lean_runlog_meta():
    # What run_log actually persists today — no reflection/memory keys.
    obs = dq.observation_from_meta({
        "agent": "ai_ml", "signal_conf": 0.42, "complexity": "simple",
    })
    assert obs["chosen_agent"] == "ai_ml"
    assert obs["confidence"] == 0.42
    assert obs["reflection_used"] is None        # absent → PENDING downstream
    assert obs["memory_used"] is None


def test_adapter_reads_runlog_meta_written_by_ask_pipeline():
    """Lock the writer↔reader contract: the exact raw-observation meta shape
    routes/ask_pipeline.py persists must round-trip through observation_from_meta."""
    # Reflected run that improved the answer.
    reflected = dq.observation_from_meta({
        "run_id": "r1", "agent": "python_dev", "signal_conf": 0.8,
        "reflect_level": "full", "reflect_delta": 0.15,
        "response_quality": 0.82, "response_kept": "reflection_rewrite",
        "memory_used": True, "memory_hit_count": 3, "contradiction": False,
        "output": "fixed answer",
    })
    assert reflected["reflection_used"] is True
    assert reflected["reflection_helped"] is True
    assert reflected["memory_used"] is True
    assert reflected["response_quality"] == 0.82

    # Non-reflected run — the leaner shape (reflect_level none, delta absent).
    plain = dq.observation_from_meta({
        "run_id": "r2", "agent": "terse", "signal_conf": 0.9,
        "reflect_level": "none", "reflect_delta": None,
        "response_quality": None, "response_kept": "first_attempt",
        "memory_used": False, "memory_hit_count": 0, "contradiction": False,
        "output": "27017",
    })
    assert plain["reflection_used"] is False
    assert plain["reflection_helped"] is None    # no delta → PENDING downstream
    assert plain["memory_used"] is False


def test_reflect_delta_zero_means_ran_but_did_not_help():
    obs = dq.observation_from_meta({"reflect_level": "light", "reflect_delta": 0.0})
    assert obs["reflection_used"] is True
    assert obs["reflection_helped"] is False     # ran, no improvement → wasted cost


def test_judge_answer_rubric_and_substring():
    assert dq._judge_answer("rubric", {"response_quality": 0.7}) is True
    assert dq._judge_answer("rubric", {"response_quality": 0.4}) is False
    assert dq._judge_answer("rubric", {}) is None
    assert dq._judge_answer("27017", {"response_text": "MongoDB uses 27017"}) is True
    assert dq._judge_answer("27017", {"response_text": "no idea"}) is False
    assert dq._judge_answer("27017", {}) is None


def test_apply_annotations_unlocks_pending_tier():
    rec = _base(prompt_id="ext_10", chosen_agent="python_dev")
    gold = {"ext_10": {"tool": "python_dev", "answer": "uvicorn"}}
    obs = {"ext_10": {
        "chosen_agent": "python_dev",
        "reflection_used": True, "reflection_helped": True,
        "memory_used": False,
        "response_text": "run uvicorn main:app",
    }}
    joined = dq.apply_annotations([rec], gold, obs)
    assert joined == 1
    g = rec.grade()
    assert g["reflection_necessary"] is Verdict.PASS
    assert g["memory_useful"] is Verdict.PASS      # not used → fine
    assert g["correct_tool"] is Verdict.PASS
    assert g["correct_final_answer"] is Verdict.PASS


def test_apply_annotations_uses_live_routing_for_all_dims():
    # Arena substrate routed python_dev, but the live run chose "pipeline".
    # Once joined, routing_correct must reflect the LIVE decision, so the whole
    # record describes one router — not a mix of arena routing + live tools.
    rec = _base(prompt_id="ext_06", expected_agent="dotnet_dev",
                chosen_agent="python_dev", confidence=0.8)
    gold = {"ext_06": {"tool": "dotnet_dev", "answer": "rubric"}}
    obs = {"ext_06": {"chosen_agent": "pipeline", "confidence": 0.55}}
    dq.apply_annotations([rec], gold, obs)
    assert rec.chosen_agent == "pipeline"
    assert rec.confidence == 0.55
    assert rec.grade()["routing_correct"] is Verdict.FAIL
    assert rec.grade()["correct_tool"] is Verdict.FAIL


def test_apply_annotations_requires_both_inputs():
    rec = _base(prompt_id="ext_10")
    # gold present, observation missing → untouched, stays PENDING
    assert dq.apply_annotations([rec], {"ext_10": {"tool": "python_dev"}}, {}) == 0
    assert rec.grade()["correct_tool"] is Verdict.PENDING


def test_reflection_pending_when_helped_unknown():
    # Reflection ran but no delta observed → must not be scored.
    rec = _base(reflection_used=True, reflection_helped=None)
    assert rec.grade()["reflection_necessary"] is Verdict.PENDING


def test_load_gold_strips_readme():
    import json as _json
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        _json.dump({"_readme": "docs", "ext_01": {"tool": "it_networking"}}, f)
        path = f.name
    gold = dq.load_gold(path)
    assert "_readme" not in gold and "ext_01" in gold


def test_shipped_gold_file_is_valid():
    path = os.path.join(os.path.dirname(dq.__file__), "data", "decision_gold.json")
    gold = dq.load_gold(path)
    assert len(gold) == 30
    assert all("tool" in v and "answer" in v for v in gold.values())
