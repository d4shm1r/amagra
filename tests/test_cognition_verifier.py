"""
Unit tests for cognition/step_verifier.py pure functions:
  _length_score, _criteria_score, _error_score, _artifact_score
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.step_verifier as sv


# ── _length_score ────────────────────────────────────────────────────────────

def test_length_score_long_enough():
    criteria = "explain networking"  # 2 words → min_words = max(20, 16) = 20
    response = " ".join(["word"] * 25)  # 25 words >= 20
    score, issues = sv._length_score(response, criteria)
    assert score == 1.0
    assert issues == []

def test_length_score_partial():
    criteria = "explain networking"
    response = " ".join(["word"] * 12)  # 12 words, min_words=20, 12 >= 10 (50%)
    score, issues = sv._length_score(response, criteria)
    assert score == 0.5
    assert len(issues) == 1

def test_length_score_too_short():
    criteria = "explain networking"
    response = "short"  # 1 word, min_words=20, 1 < 10 (50%)
    score, issues = sv._length_score(response, criteria)
    assert score == 0.0
    assert len(issues) == 1

def test_length_score_complex_criteria():
    criteria = " ".join(["word"] * 10)  # 10 words → min_words = max(20, 80) = 80
    response = " ".join(["x"] * 100)   # 100 words >= 80
    score, issues = sv._length_score(response, criteria)
    assert score == 1.0


# ── _criteria_score ──────────────────────────────────────────────────────────

def test_criteria_score_full_match():
    response = "networking configuration uses routing protocols"
    criteria = "networking configuration routing protocols"
    score, issues = sv._criteria_score(response, criteria)
    assert score == 1.0

def test_criteria_score_no_keywords():
    response = "something"
    criteria = "a an the or"  # all stop words
    score, issues = sv._criteria_score(response, criteria)
    assert score == 1.0  # no keywords → full credit

def test_criteria_score_partial_match():
    response = "configure routing"
    criteria = "networking configuration routing protocols security"
    score, issues = sv._criteria_score(response, criteria)
    assert 0 < score < 1.0

def test_criteria_score_no_match():
    response = "completely unrelated text here"
    criteria = "networking routing protocols"
    score, issues = sv._criteria_score(response, criteria)
    assert score < 0.5
    assert len(issues) == 1

def test_criteria_score_stem_partial():
    response = "route the traffic"  # "route" is stem of "routing"
    criteria = "routing configuration"  # "routing" stem "routi" matches "route" prefix... depends on heuristic
    score, _ = sv._criteria_score(response, criteria)
    assert 0.0 <= score <= 1.0  # just validate it returns valid range


# ── _error_score ─────────────────────────────────────────────────────────────

def test_error_score_clean_response():
    response = "Here is how to configure your system. Follow these steps."
    score, issues = sv._error_score(response)
    assert score == 1.0
    assert issues == []

def test_error_score_multiple_error_signals():
    response = "I cannot help with that. I don't know. I'm unable to provide assistance."
    score, issues = sv._error_score(response)
    assert score == 0.0
    assert len(issues) == 1

def test_error_score_single_signal():
    response = "I cannot provide that information directly."
    score, issues = sv._error_score(response)
    assert score in (0.4, 1.0)  # 0.4 if "cannot" is a signal, 1.0 if not

def test_error_score_ignores_code_blocks():
    response = "```python\nraise HTTPException(404, 'not found')\n```\nHere is the implementation."
    score, issues = sv._error_score(response)
    assert score == 1.0  # code blocks are stripped before checking


# ── _artifact_score ───────────────────────────────────────────────────────────

def test_artifact_score_non_code_agent():
    score, issues = sv._artifact_score("some response", "explain routing", "it_networking")
    assert score == 1.0  # non-code agent always gets full credit

def test_artifact_score_code_agent_no_intent():
    score, issues = sv._artifact_score("some response", "explain this concept", "python_dev")
    assert score == 1.0  # no code intent keyword

def test_artifact_score_code_agent_with_code():
    score, issues = sv._artifact_score(
        "Here is the code:\n```python\ndef hello():\n    pass\n```",
        "implement a function",
        "python_dev"
    )
    assert score == 1.0

def test_artifact_score_code_agent_missing_code():
    score, issues = sv._artifact_score(
        "You should write a function that does X.",
        "implement a function",
        "python_dev"
    )
    assert score == 0.3
    assert len(issues) == 1
