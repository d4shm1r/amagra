"""
answer_checkers.py — pluggable answer graders for the reflection stress set.

Substring matching is fine for "MongoDB port = 27017" but useless for the cases
where reflection actually has a chance to help: multi-step arithmetic, false
premises the model must reject, questions it should refuse. Each stress item
carries a `check` spec graded here. `check(spec, text)` returns:

  True   answer satisfies the spec
  False  answer violates it
  None   ungradeable (empty text) — kept out of correctness rates, not counted wrong

Confidence note: `numeric`, `contains`, `any_contains`, `all_contains` are
rigorous. `rejects_premise` and `admits_uncertainty` are HEURISTIC (marker-based)
and the report flags them as such — they can be fooled, so treat them as weaker
signal than the exact checks.
"""

from __future__ import annotations

import re

# Markers that signal the model corrected a false premise.
_REJECT_MARKERS = (
    "actually", "in fact", "not true", "isn't true", "is false", "false premise",
    "incorrect", "misconception", "not correct", "mistaken", "contrary to",
    "there is no", "there's no", "did not", "does not", "no such", "however,",
    "that's not", "not accurate", "common myth",
)

# Markers that signal the model asked for missing information instead of guessing.
_CLARIFY_MARKERS = (
    "could you clarify", "can you clarify", "please clarify", "please specify",
    "which one", "do you mean", "more information", "more details", "more context",
    "which of", "need to know", "ambiguous", "unclear which", "not specified",
    "did you mean", "what do you mean", "can you provide",
)

# Markers that signal an honest admission of uncertainty / refusal to fabricate.
_UNCERTAINTY_MARKERS = (
    "i don't know", "i do not know", "not sure", "cannot determine",
    "can't determine", "unable to", "no reliable", "don't have", "do not have",
    "not aware", "no way to know", "impossible to know", "i'm not certain",
    "insufficient information", "cannot verify", "can't verify", "no public",
    "not possible to", "i cannot provide", "unclear",
)


def _numbers(text: str) -> list[float]:
    """All numbers in the text, commas stripped. '18', '1,024', '3.5' → floats."""
    out = []
    for m in re.findall(r"-?\d[\d,]*\.?\d*", text or ""):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def check(spec: dict, text: str) -> bool | None:
    if not text or not text.strip():
        return None
    t = text.lower()
    kind = spec.get("type")

    if kind == "numeric":
        expect = float(spec["expect"])
        tol = float(spec.get("tol", 1e-6))
        # Prefer the number after the last "answer" marker — the response usually
        # echoes the question's numbers, so scanning everything is fooled. The
        # stress prompts request an "Answer: N" line to make this reliable.
        tail = re.split(r"answer\s*[:=]", text, flags=re.IGNORECASE)
        nums = _numbers(tail[-1]) if len(tail) > 1 else _numbers(text)
        if not nums:
            return None
        # After an explicit answer marker, judge the FIRST number stated there;
        # otherwise fall back to "any number matches" over the whole response.
        if len(tail) > 1:
            return abs(nums[0] - expect) <= tol
        return any(abs(n - expect) <= tol for n in nums)

    if kind == "contains":
        return spec["expect"].lower() in t

    if kind == "any_contains":
        return any(e.lower() in t for e in spec["expect"])

    if kind == "all_contains":
        return all(e.lower() in t for e in spec["expect"])

    if kind == "rejects_premise":
        # Must correct the premise; optionally must also mention the right fact.
        corrected = any(m in t for m in _REJECT_MARKERS)
        need = spec.get("must_contain")
        if need:
            corrected = corrected and any(e.lower() in t for e in need)
        return corrected

    if kind == "admits_uncertainty":
        return any(m in t for m in _UNCERTAINTY_MARKERS)

    if kind == "seeks_clarification":
        return any(m in t for m in _CLARIFY_MARKERS)

    if kind == "all_of":
        results = [check(s, text) for s in spec["checks"]]
        if any(r is None for r in results):
            return None
        return all(results)

    raise ValueError(f"unknown check type: {kind!r}")


# Which check types are rigorous vs heuristic — the report uses this to caveat.
HEURISTIC_TYPES = frozenset({"rejects_premise", "admits_uncertainty", "seeks_clarification"})


def is_heuristic(spec: dict) -> bool:
    if spec.get("type") in HEURISTIC_TYPES:
        return True
    if spec.get("type") == "all_of":
        return any(is_heuristic(s) for s in spec["checks"])
    return False
