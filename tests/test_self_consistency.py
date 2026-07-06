"""
Unit tests for the self-consistency reasoning lever.

The model call is injected, so we exercise answer extraction and majority
voting deterministically with a fake generator — no Ollama, no network.
"""
from cognition.self_consistency import (
    extract_final_answer,
    majority_vote,
    normalize_number,
    self_consistent_answer,
)


# ── normalize_number ──────────────────────────────────────────

def test_normalize_strips_commas_and_trailing_zero():
    assert normalize_number("1,000") == "1000"
    assert normalize_number("1000.0") == "1000"
    assert normalize_number("42") == "42"
    assert normalize_number("3.5") == "3.5"


# ── extract_final_answer ──────────────────────────────────────

def test_extract_prefers_hash_marker():
    assert extract_final_answer("blah blah 17 more text\n#### 42") == "42"


def test_extract_answer_cue():
    assert extract_final_answer("Working... therefore the answer is $1,250.") == "1250"


def test_extract_falls_back_to_last_number():
    assert extract_final_answer("First 3 apples, then 4 more, so 7 apples.") == "7"


def test_extract_none_when_no_number():
    assert extract_final_answer("no digits here") is None
    assert extract_final_answer("") is None
    assert extract_final_answer(None) is None


# ── majority_vote ─────────────────────────────────────────────

def test_majority_vote_picks_mode():
    v = majority_vote(["42", "42", "7", "42"])
    assert v["answer"] == "42"
    assert v["votes"] == 3
    assert v["valid"] == 4


def test_majority_vote_ignores_none():
    v = majority_vote([None, "5", None, "5"])
    assert v["answer"] == "5"
    assert v["votes"] == 2
    assert v["valid"] == 2


def test_majority_vote_tie_breaks_to_first_seen():
    # 9 appears first; tie 2–2 must resolve to 9, deterministically.
    v = majority_vote(["9", "4", "9", "4"])
    assert v["answer"] == "9"


def test_majority_vote_all_none():
    v = majority_vote([None, None])
    assert v["answer"] is None
    assert v["valid"] == 0


# ── self_consistent_answer (integration with a fake generator) ─

def test_self_consistency_recovers_from_a_bad_sample():
    # 4 of 5 samples get it right; one is wrong. Majority vote should recover 42.
    scripted = iter([
        "reasoning ... #### 42",
        "oops #### 41",
        "reasoning ... #### 42",
        "reasoning ... #### 42",
        "reasoning ... #### 42",
    ])

    def fake_generate(_prompt, _temp):
        return next(scripted)

    res = self_consistent_answer("q", fake_generate, n=5, temperature=0.7)
    assert res["answer"] == "42"
    assert res["votes"] == 4
    assert res["valid"] == 5
    assert res["n"] == 5
    assert len(res["samples"]) == 5
    assert res["distribution"] == {"42": 4, "41": 1}


def test_self_consistency_single_sample():
    res = self_consistent_answer("q", lambda p, t: "the answer is 8", n=1)
    assert res["answer"] == "8"
    assert res["n"] == 1
