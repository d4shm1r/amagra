"""
Unit tests for the build-intent over-classification guard (issue #7).

The LLM classifier sometimes returns action="build" for plain imperative
prose ("repeat the months of the year backward"). core_brain.CODE_NOUN is
the guard: build is only a real coding task when a code noun is present.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.core_brain import CODE_NOUN


# Plain imperatives that should NOT be treated as coding tasks
NON_CODE = [
    "Repeat the months of the year backward as listed",
    "List the planets from the sun outward",
    "Summarize the French revolution in three sentences",
    "Translate good morning into Spanish",
]

# Genuine coding requests that SHOULD keep action="build"
CODE = [
    "Write a script to parse a CSV file",
    "Create a function that reverses a string",
    "Build a FastAPI endpoint for login",
    "Generate a regex that matches emails",
    "Make a CLI program that lists files",
]


def test_non_code_imperatives_have_no_code_noun():
    for q in NON_CODE:
        assert CODE_NOUN.search(q) is None, f"false positive: {q!r}"


def test_code_requests_have_code_noun():
    for q in CODE:
        assert CODE_NOUN.search(q) is not None, f"missed code noun: {q!r}"


def test_valid_agents_matches_registry_no_drift():
    """core_brain.VALID_AGENTS gates the LLM classifier prompt, the LLM result
    filter, and both the learned-router and decision-econ overrides. If it drifts
    below the registry, those paths silently can't reach the missing agents (this
    exact bug hid web_dev/devops/data_analyst/writer). Mirror the coordinator's
    boot assertion so the drift can't come back."""
    from orchestration.core_brain import VALID_AGENTS
    from agents.registry import AGENT_IDS
    assert set(VALID_AGENTS) == AGENT_IDS, (
        f"core_brain VALID_AGENTS drifted from registry: "
        f"missing={sorted(AGENT_IDS - set(VALID_AGENTS))} "
        f"extra={sorted(set(VALID_AGENTS) - AGENT_IDS)}"
    )
