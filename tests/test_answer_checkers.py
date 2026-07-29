"""Tests for the reflection-stress answer checkers — the grading is load-bearing."""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from workbench.evaluation import answer_checkers as ck


def test_numeric_prefers_answer_line_over_echoed_numbers():
    # Response echoes the question's 5s and 100s but the final answer is 5.
    txt = "5 machines make 5 widgets in 5 min; for 100 machines and 100 widgets... Answer: 5 minutes"
    assert ck.check({"type": "numeric", "expect": 5}, txt) is True
    # Wrong final answer despite echoing a 5 earlier.
    wrong = "5 machines... so it scales linearly. Answer: 100"
    assert ck.check({"type": "numeric", "expect": 5}, wrong) is False


def test_numeric_fallback_without_answer_marker():
    assert ck.check({"type": "numeric", "expect": 47}, "it is half on day 47") is True
    assert ck.check({"type": "numeric", "expect": 47}, "no numbers here") is None


def test_contains_and_any_all():
    assert ck.check({"type": "contains", "expect": "redis"}, "Use Redis for caching") is True
    assert ck.check({"type": "any_contains", "expect": ["?", "%s"]}, "use a %s placeholder") is True
    assert ck.check({"type": "all_contains", "expect": ["a", "b"]}, "only a") is False


def test_rejects_premise_requires_correction_and_optional_fact():
    good = "Actually, Einstein won it for the photoelectric effect, not relativity."
    assert ck.check({"type": "rejects_premise", "must_contain": ["photoelectric"]}, good) is True
    # Corrects but misses the required fact.
    assert ck.check({"type": "rejects_premise", "must_contain": ["photoelectric"]},
                    "Actually that is a common myth.") is False
    # Accepts the false premise.
    assert ck.check({"type": "rejects_premise"}, "He unified space and time, so...") is False


def test_uncertainty_and_clarification():
    assert ck.check({"type": "admits_uncertainty"}, "I don't know that population.") is True
    assert ck.check({"type": "admits_uncertainty"}, "It was exactly 1,234.") is False
    assert ck.check({"type": "seeks_clarification"}, "Which one do you mean?") is True


def test_none_on_empty():
    assert ck.check({"type": "contains", "expect": "x"}, "") is None


def test_is_heuristic():
    assert ck.is_heuristic({"type": "rejects_premise"}) is True
    assert ck.is_heuristic({"type": "numeric", "expect": 1}) is False
    assert ck.is_heuristic({"type": "all_of", "checks": [{"type": "admits_uncertainty"}]}) is True


def test_shipped_stress_dataset_valid():
    p = os.path.join(os.path.dirname(ck.__file__), "data", "reflection_stress.json")
    data = {k: v for k, v in json.load(open(p)).items() if not k.startswith("_")}
    assert len(data) >= 24
    cats = {v["category"] for v in data.values()}
    assert len(cats) == 7
    for v in data.values():
        assert "prompt" in v and "check" in v and "type" in v["check"]


def test_numeric_accepts_spelled_out_answer():
    # Local model answers in words — must still grade.
    assert ck.check({"type": "numeric", "expect": 60}, "Answer: sixty apples remain") is True
    assert ck.check({"type": "numeric", "expect": 47}, "it was half on day forty-seven") is True
    assert ck.check({"type": "numeric", "expect": 47}, "day forty seven") is True
    assert ck.check({"type": "numeric", "expect": 5}, "Answer: five cents") is True
    # A wrong answer that is ONLY spelled out (no digits, not the expected word)
    # is ungradeable → None, not a false pass. Honest under-grading, not wrong.
    assert ck.check({"type": "numeric", "expect": 60}, "Answer: fifty apples") is None
    # But a wrong DIGIT answer is still caught as False.
    assert ck.check({"type": "numeric", "expect": 60}, "Answer: 50 apples") is False
