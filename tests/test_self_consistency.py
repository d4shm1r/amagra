"""
Unit tests for the self-consistency reasoning lever.

The model call is injected, so we exercise answer extraction and majority
voting deterministically with a fake generator — no Ollama, no network.
"""
from cognition.self_consistency import (
    escalation_decision,
    extract_final_answer,
    is_numeric_reasoning,
    wants_scalar_answer,
    majority_vote,
    normalize_number,
    self_consistent_answer,
    vote_confidence,
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


# ── vote_confidence ───────────────────────────────────────────

def test_vote_confidence_is_agreement_ratio():
    assert vote_confidence({"votes": 3, "valid": 5}) == 0.6
    assert vote_confidence({"votes": 5, "valid": 5}) == 1.0
    assert vote_confidence({"votes": 1, "valid": 4}) == 0.25


def test_vote_confidence_zero_when_nothing_parsed():
    assert vote_confidence({"votes": 0, "valid": 0}) == 0.0


# ── escalation_decision (the empirically-tuned gate) ──────────
# Threshold matches the GSM8K / phi4-mini N=100 cut: ≥3/5 trust, ≤2/5 escalate.

def test_escalation_trusts_a_confident_vote():
    d = escalation_decision({"votes": 4, "valid": 5})
    assert d["escalate"] is False
    assert d["confidence"] == 0.8


def test_escalation_trusts_the_exact_boundary():
    # 3/5 = 0.60 sits on the default threshold and must count as trust, not escalate.
    d = escalation_decision({"votes": 3, "valid": 5})
    assert d["escalate"] is False


def test_escalation_flags_a_split_vote():
    d = escalation_decision({"votes": 2, "valid": 5})
    assert d["escalate"] is True
    assert d["confidence"] == 0.4


def test_escalation_flags_total_disagreement():
    d = escalation_decision({"votes": 0, "valid": 0})
    assert d["escalate"] is True
    assert d["confidence"] == 0.0


def test_escalation_threshold_is_tunable():
    res = {"votes": 4, "valid": 5}  # agreement 0.8
    assert escalation_decision(res, trust_agreement=0.9)["escalate"] is True
    assert escalation_decision(res, trust_agreement=0.7)["escalate"] is False


def test_escalation_decision_end_to_end_from_samples():
    # A split run (2/2/1) should surface as low-confidence → escalate.
    scripted = iter(["#### 10", "#### 20", "#### 10", "#### 20", "#### 30"])
    res = self_consistent_answer("q", lambda p, t: next(scripted), n=5)
    d = escalation_decision(res)
    assert res["votes"] == 2 and res["valid"] == 5
    assert d["escalate"] is True


# ── is_numeric_reasoning (the coordinator's applicability gate) ─

def test_numeric_reasoning_fires_on_word_problems():
    assert is_numeric_reasoning(
        "Natalia sold 48 clips in April and half as many in May. How many total?"
    )
    assert is_numeric_reasoning("What is 12 times 8?")


def test_numeric_reasoning_skips_ordinary_prose():
    assert not is_numeric_reasoning("What year did World War 2 end?")   # number, no cue
    assert not is_numeric_reasoning("Explain how TCP handshakes work")  # no numbers
    assert not is_numeric_reasoning("what port does ssh use")           # no numbers
    assert not is_numeric_reasoning("")


def test_numeric_reasoning_needs_a_number_and_a_cue():
    assert not is_numeric_reasoning("The answer is 42")   # number but no cue word
    assert is_numeric_reasoning("Add 5 and 7 together")   # number + 'add'


# ── wants_scalar_answer (the #185 gate: scalar-only self-consistency) ─

def test_scalar_gate_fires_on_word_problems():
    # Arithmetic word problems still qualify (the measured +0.19 lever).
    assert wants_scalar_answer("What is 12 times 8?")
    assert wants_scalar_answer(
        "A shop sold 12 apples and had 30 left. How many in total?"
    )


def test_scalar_gate_fires_on_scalar_compute_shape():
    # Scalar compute-shaped queries (#184) qualify only with the shape hint,
    # since they carry no word-problem cue word.
    assert wants_scalar_answer("Compute 17 factorial exactly", shape="compute")
    assert wants_scalar_answer("Compute the 15th Fibonacci number", shape="compute")
    assert wants_scalar_answer("Evaluate the sum 1+2+3+...+100", shape="compute")
    # Without the compute shape, a bare compute verb + number is not enough.
    assert not wants_scalar_answer("Compute 17 factorial exactly")


def test_scalar_gate_excludes_enumerations_and_proofs():
    # Vector / derivation answers: scalar voting can't validate them → #186.
    for q in [
        "Compute the first 12 terms of the sequence a1=1, a2=2",
        "Enumerate the first 10 prime numbers",
        "List the first 8 powers of 2 exactly",
        "Give the exact decimal expansion of 1/7 to 12 places",
        "Prove that the sum of the first n odd numbers equals n squared",
    ]:
        assert not wants_scalar_answer(q, shape="compute"), q


def test_scalar_gate_needs_a_number_and_rejects_empty():
    assert not wants_scalar_answer("Compute the answer", shape="compute")  # no number
    assert not wants_scalar_answer("", shape="compute")


def test_coordinator_composition_picks_winning_sample_text():
    # Mirrors the coordinator's inline block: sample texts → vote → winning text
    # → escalation decision. Guards the composition without importing the graph.
    samples = [
        "step by step ... #### 72",
        "hmm ... #### 71",
        "reasoning ... #### 72",
        "work ... #### 72",
        "oops ... #### 24",
    ]
    answers = [extract_final_answer(s) for s in samples]
    vote = majority_vote(answers)
    winner_text = next(s for s, a in zip(samples, answers) if a == vote["answer"])
    assert vote["answer"] == "72"
    assert winner_text == "step by step ... #### 72"   # first sample with the winner
    assert escalation_decision(vote)["escalate"] is False  # 3/5 agreement → trust
