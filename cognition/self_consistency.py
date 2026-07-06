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
