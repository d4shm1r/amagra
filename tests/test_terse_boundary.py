"""
Adversarial terse boundary test.

Stress-tests the terse routing boundary with 12 cases designed to probe
both directions of the failure:
  - Queries that SHOULD go to terse but have domain keywords that could
    pull them to a specialist (false negative: terse missed)
  - Queries that SHOULD stay domain-routed but sound short/factual
    (false positive: terse overclaims)

No LLM calls. Pure QuerySignal routing via normalize(). Runs in <1s.

Run: python3 tests/test_terse_boundary.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT

TERSE_AGENT  = "terse"
ROUTING_THRESHOLD = 0.30

def route(query: str) -> str:
    """Mirror the priority table from core_brain fast path (core_brain.py:329-381)."""
    sig = normalize(query)
    # Rule 1: factual shape always → terse regardless of domain
    if sig.answer_shape == "factual":
        return TERSE_AGENT
    # Rule 2: short generic explanation with NO domain → terse
    # (domain must be "general" — if a domain was detected, fall through)
    if sig.verbosity == "terse" and sig.answer_shape == "explanation" and sig.domain == "general":
        return TERSE_AGENT
    # Rule 3: detected domain → domain agent
    if sig.domain_conf > ROUTING_THRESHOLD:
        return DOMAIN_TO_AGENT[sig.domain]
    return "knowledge_learning"

# ── Test cases ────────────────────────────────────────────────
# (query, expected_agent, note)
CASES = [
    # ── Should go to terse ───────────────────────────────────
    ("What port does HTTPS use?",
     TERSE_AGENT,
     "Classic terse — networking keyword present but answer_shape=factual should win"),

    ("What TCP flags are there?",
     "it_networking",
     "Enumeration — shape=explanation (not factual), domain wins; networking agent explains each flag"),

    ("What does DNS stand for?",
     TERSE_AGENT,
     "Has 'dns' keyword; 'what does X stand for' is factual"),

    ("What is the default port for PostgreSQL?",
     TERSE_AGENT,
     "Short factual — one-number answer expected"),

    ("How many bytes in a megabyte?",
     TERSE_AGENT,
     "Pure factual, no domain keywords"),

    ("What does HTTP status 429 mean?",
     TERSE_AGENT,
     "Has 'http' keyword; 'what does X mean' is factual shape"),

    # ── Should NOT go to terse ───────────────────────────────
    ("What is machine learning?",
     "ai_ml",
     "Sounds factual but 'machine learning' is a concept requiring explanation"),

    ("How does async await work in Python?",
     "python_dev",
     "Short query but requires code explanation — shape should be explanation/code"),

    ("What is the difference between TCP and UDP?",
     "it_networking",
     "9 tokens, comparison shape — verbosity=normal, not terse"),

    ("What port does HTTPS use and why was that port chosen?",
     "it_networking",
     "Starts terse but the 'and why' clause shifts to explanation shape"),

    ("Explain DNS",
     "it_networking",
     "Explicit 'explain' verb overrides terse path; shape=explanation"),

    ("What is Blazor?",
     "dotnet_dev",
     "Has 'blazor' keyword; single-word definition could be verbose — domain should win"),
]


def run():
    passed = failed = 0
    wrong_direction = {"false_negative": [], "false_positive": []}

    for query, expected, note in CASES:
        sig    = normalize(query)
        actual = route(query)
        ok     = actual == expected

        status = "PASS" if ok else "FAIL"
        print(f"  {status}  [{sig.answer_shape:12} | conf={sig.domain_conf:.2f} | verb={sig.verbosity}]  "
              f"{query!r}")
        if not ok:
            print(f"         expected={expected!r}  got={actual!r}")
            print(f"         note: {note}")
            if expected == TERSE_AGENT:
                wrong_direction["false_negative"].append(query)
            else:
                wrong_direction["false_positive"].append(query)
            failed += 1
        else:
            passed += 1

    print()
    print(f"Result: {passed}/{passed+failed} passed")
    if wrong_direction["false_negative"]:
        print(f"  False negatives (terse missed): {len(wrong_direction['false_negative'])}")
        for q in wrong_direction["false_negative"]:
            print(f"    - {q!r}")
    if wrong_direction["false_positive"]:
        print(f"  False positives (terse overclaimed): {len(wrong_direction['false_positive'])}")
        for q in wrong_direction["false_positive"]:
            print(f"    - {q!r}")

    return failed


if __name__ == "__main__":
    sys.exit(run())
