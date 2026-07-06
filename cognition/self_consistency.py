"""
Self-consistency — the cheapest real reasoning lift for a small local model.

Sample the same prompt N times at a non-zero temperature, extract the final
answer from each sample, and return the majority vote. On arithmetic / logic
reasoning a single greedy sample is brittle; agreement across independent
samples is a strong signal, so majority voting recovers many problems the model
*can* solve but doesn't on the first try. This is inference-time compute: we
trade N× tokens for accuracy, no weight changes.

The model call is injected as `generate_fn(prompt, temperature) -> str` so the
voting logic is pure and unit-testable without a backend. `evaluation/
reasoning_eval.py` wires in the real ChatOllama / hosted-provider callables.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Callable, Optional

# A number token: optional sign, digits with optional thousands-commas, optional
# decimal part. We deliberately ignore '%' and units — GSM8K answers are plain
# numbers.
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def normalize_number(raw: str) -> str:
    """Canonicalise a numeric string so '1,000', '1000.0' and '1000' compare equal."""
    s = raw.replace(",", "").strip()
    try:
        f = float(s)
    except ValueError:
        return raw.strip()
    # Integers render without a trailing '.0'; keep real decimals as-is.
    return str(int(f)) if f == int(f) else str(f)


def extract_final_answer(text: str) -> Optional[str]:
    """
    Pull the final numeric answer from a model completion.

    Preference order:
      1. An explicit GSM8K-style '#### <number>' marker (what the gold data uses).
      2. The number following an 'answer is/=' cue, if present.
      3. Otherwise the LAST number in the text — models state the result last.

    Returns a normalised string, or None if the text has no number at all.
    """
    if text is None:
        return None

    marker = re.search(r"####\s*(-?\d[\d,]*(?:\.\d+)?)", text)
    if marker:
        return normalize_number(marker.group(1))

    cue = re.search(
        r"(?:answer|result|total)\s*(?:is|:|=)\s*\$?\s*(-?\d[\d,]*(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if cue:
        return normalize_number(cue.group(1))

    nums = _NUM_RE.findall(text)
    return normalize_number(nums[-1]) if nums else None


def majority_vote(answers: list[Optional[str]]) -> dict:
    """
    Majority vote over extracted answers, ignoring None (unparseable) samples.

    Ties break toward the answer that appeared FIRST, so the result is
    deterministic for a fixed sample order. Returns the winning answer, its vote
    count, the number of valid votes, and the full distribution.
    """
    order: list[str] = []
    seen: set[str] = set()
    valid: list[str] = []
    for a in answers:
        if a is None:
            continue
        valid.append(a)
        if a not in seen:
            seen.add(a)
            order.append(a)

    if not valid:
        return {"answer": None, "votes": 0, "valid": 0, "distribution": {}}

    counts = Counter(valid)
    # max() is stable over `order`, so the earliest-seen answer wins a tie.
    winner = max(order, key=lambda a: counts[a])
    return {
        "answer": winner,
        "votes": counts[winner],
        "valid": len(valid),
        "distribution": dict(counts),
    }


def self_consistent_answer(
    prompt: str,
    generate_fn: Callable[[str, float], str],
    n: int = 5,
    temperature: float = 0.7,
) -> dict:
    """
    Sample `prompt` n times via generate_fn(prompt, temperature), extract each
    final answer, and majority-vote.

    Returns the voted answer plus enough detail to audit the run:
      { answer, votes, valid, n, distribution, samples: [{text, answer}, ...] }

    A confident run has votes ≈ n; a votes barely above n/2 (or many None
    extractions) flags a problem the model is guessing at — useful signal for a
    downstream escalation gate.
    """
    samples = []
    extracted: list[Optional[str]] = []
    for _ in range(max(1, n)):
        text = generate_fn(prompt, temperature)
        ans = extract_final_answer(text)
        samples.append({"text": text, "answer": ans})
        extracted.append(ans)

    vote = majority_vote(extracted)
    return {**vote, "n": max(1, n), "samples": samples}


# ── Escalation gate ───────────────────────────────────────────
# The winning-agreement ratio (winner votes / valid votes) is a strong
# confidence signal, measured on GSM8K / phi4-mini (N=100, see the
# self-consistency result memory / logs/reasoning_*.json):
#
#   agreement ≥ 0.6  (≥3/5 votes)  → 97–100% correct  → trust the local answer
#   agreement ≤ 0.4  (≤2/5 votes)  → ~42% correct      → escalate
#
# Escalating just the low-agreement tail targets ~90% of all errors at ~30% of
# the volume — the cheap, high-yield cut. The 0.5–0.6 band is the ambiguous
# middle; where exactly to draw the line depends on escalation cost, so the
# threshold is a tunable argument.
TRUST_AGREEMENT = 0.6


def vote_confidence(result: dict) -> float:
    """
    Winning-agreement ratio in [0, 1]: winner votes / valid votes.

    Takes a `self_consistent_answer` / `majority_vote` result dict. Returns 0.0
    when nothing parsed (`valid == 0`) — total disagreement, always escalate.
    """
    valid = result.get("valid", 0)
    return result.get("votes", 0) / valid if valid else 0.0


def escalation_decision(result: dict, trust_agreement: float = TRUST_AGREEMENT) -> dict:
    """
    Turn a self-consistency result into an escalation decision.

    Mirrors the router's `decide_with_confidence` shape (a value plus a
    confidence) so it can feed the same hybrid escalation gate: a low-agreement
    vote is exactly the case to route to a bigger model or draw more samples.

    Returns { confidence, escalate, reason }. `escalate` is True when the winner
    carries less than `trust_agreement` of the valid votes.
    """
    conf = vote_confidence(result)
    # +epsilon so an exact boundary (e.g. 3/5 = 0.6 at the default) counts as trust.
    escalate = conf + 1e-9 < trust_agreement
    votes, valid = result.get("votes", 0), result.get("valid", 0)
    reason = (
        f"vote agreement {conf:.2f} < {trust_agreement:.2f} "
        f"({votes}/{valid}) — escalate"
        if escalate
        else f"vote agreement {conf:.2f} ≥ {trust_agreement:.2f} "
        f"({votes}/{valid}) — trust local"
    )
    return {"confidence": round(conf, 4), "escalate": escalate, "reason": reason}


# ── Applicability gate ────────────────────────────────────────
# Cue words for quantitative word problems — where voting on a numeric final
# answer helps. `extract_final_answer` is numeric, so self-consistency only
# applies to arithmetic-shaped queries.
_QUANTITY_CUE = re.compile(
    r"\b(how many|how much|total|sum|average|mean|each|per|times|twice|half|"
    r"double|percent|remaining|left|altogether|combined|costs?|price|profit|"
    r"difference|more than|less than|fewer|add|subtract|multiply|divides?|"
    r"divided|product)\b|%",
    re.IGNORECASE,
)


def is_numeric_reasoning(query: str) -> bool:
    """
    Heuristic gate: does this query look like an arithmetic word problem, where
    majority-voting over a numeric answer helps?

    Deliberately conservative — it requires at least one number AND a
    quantitative cue word, so ordinary prose ("what year did X happen") never
    triggers the expensive N-sample path. (Word problems often spell a quantity
    out — "half as many" — so a two-number floor misses real cases; the cue-word
    requirement carries the precision.) The router has no "math" answer_shape,
    so this is the local gate the coordinator uses to decide when to spend the
    extra samples.
    """
    if not query:
        return False
    numbers = re.findall(r"\d[\d,]*(?:\.\d+)?", query)
    return len(numbers) >= 1 and bool(_QUANTITY_CUE.search(query))
