"""
Tests for the A ← R coupling in infrastructure/skill_graph.py — skill
selection conditioned on reasoning state (action + chosen agents).

These assert the mechanism (additive bias, never a filter, backward
compatible) rather than specific registry contents, so they survive
skill-registry edits.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import infrastructure.skill_graph as sg
from infrastructure.skill_graph import (
    select_skills, top_agent, entropy_report,
    _action_fits, _BIAS_PREFER_AGENT, SkillNode,
)

# A query that reliably matches at least one skill in the registry.
_Q = "explain gradient descent and backpropagation"


def _scores(skills):
    return {s.name: s.score for s in skills}


def test_no_kwargs_is_unchanged():
    """Omitting the coupling kwargs reproduces the original behaviour."""
    skills = select_skills(_Q, n=99)
    assert skills, "query should match at least one skill"
    # Scores are pure normalised keyword overlap, all ≤ 1.0, no bias applied.
    assert all(0.0 < s.score <= 1.0 for s in skills)


def test_prefer_agents_adds_exact_bias():
    """A matched skill on a preferred agent gains exactly the prefer bias."""
    base = _scores(select_skills(_Q, n=99))
    target_agent = next(iter(select_skills(_Q, n=1))).agent
    biased = select_skills(_Q, n=99, prefer_agents=[target_agent])

    for s in biased:
        if s.agent == target_agent:
            expected = round(min(base[s.name] + _BIAS_PREFER_AGENT, 1.0), 4)
            assert s.score == expected
        else:
            assert s.score == base[s.name]


def test_prefer_is_a_bias_not_a_filter():
    """Non-preferred matched skills are re-ranked, never removed."""
    base_names = {s.name for s in select_skills(_Q, n=99)}
    biased_names = {s.name for s in
                    select_skills(_Q, n=99, prefer_agents=["devops"])}
    # 'devops' almost certainly matches none of this query's skills, yet every
    # originally-matched skill must still be present — bias, not filter.
    assert base_names == biased_names


def test_action_fit_nudges_matching_complexity():
    """An action that suits a skill's complexity adds the action bias."""
    base = _scores(select_skills(_Q, n=99))
    # 'explain' favours theory-complexity skills (see _ACTION_AFFINITY).
    biased = select_skills(_Q, n=99, action="explain")
    moved = [name for name, sc in _scores(biased).items() if sc > base[name]]
    assert moved, "explain should lift at least one theory/mixed skill"


def test_action_fits_helper():
    mixed = SkillNode("x", "c", "a", "d", ["k"], complexity="mixed")
    theory = SkillNode("y", "c", "a", "d", ["k"], complexity="theory")
    eng = SkillNode("z", "c", "a", "d", ["k"], complexity="engineering")
    assert _action_fits("build", mixed)          # mixed fits any action
    assert _action_fits("build", eng)            # build favours engineering
    assert not _action_fits("build", theory)     # build does not favour theory
    assert _action_fits("explain", theory)       # explain favours theory
    assert not _action_fits("lookup", eng)       # lookup carries no affinity


def test_top_agent_forwards_kwargs():
    """top_agent honours the coupling kwargs without error."""
    agent = top_agent(_Q, action="explain", prefer_agents=["ai_ml"])
    assert isinstance(agent, str) and agent


# ── Entropy diagnostic (the gate for tuning the coupling gains) ──────────────

@pytest.fixture(autouse=True)
def _fresh_selection_log():
    """Each test observes only its own selections."""
    sg._SELECTION_LOG.clear()
    yield
    sg._SELECTION_LOG.clear()


def test_entropy_report_empty():
    r = entropy_report()
    assert r["n"] == 0
    assert r["entropy_bits"] is None
    assert r["falling"] is False


def test_entropy_zero_when_selection_collapses():
    """The same query over and over → one top skill → zero bits."""
    for _ in range(20):
        select_skills(_Q, n=3)
    r = entropy_report()
    assert r["n"] == 20
    assert r["distinct"] == 1
    assert r["entropy_bits"] == 0.0
    # Both halves are identical, so diversity isn't *falling* — it's flat.
    assert r["falling"] is False


def test_entropy_positive_across_diverse_queries():
    queries = [
        "explain gradient descent and backpropagation",
        "docker compose deployment pipeline ci/cd",
        "debug this python fastapi async exception",
        "write a react component with hooks and css",
        "sql query to aggregate pandas dataframe stats",
    ]
    for q in queries * 4:
        select_skills(q, n=3)
    r = entropy_report()
    assert r["n"] == 20
    assert r["distinct"] >= 2
    assert r["entropy_bits"] > 0.0
    assert 0.0 < r["entropy_norm"] <= 1.0


def test_entropy_detects_diversity_collapse():
    """Diverse older half → collapsed newer half must read as falling."""
    diverse = [
        "explain gradient descent and backpropagation",
        "docker compose deployment pipeline ci/cd",
        "debug this python fastapi async exception",
        "write a react component with hooks and css",
    ]
    for q in diverse * 3:                 # older half: high diversity
        select_skills(q, n=3)
    for _ in range(12):                   # newer half: one skill only
        select_skills(_Q, n=3)
    r = entropy_report(window=24)
    assert r["older_bits"] > r["newer_bits"]
    assert r["delta_bits"] < -0.5
    assert r["falling"] is True
    assert "falling" in r["note"]


def test_entropy_tracks_coupled_share():
    for _ in range(5):
        select_skills(_Q, n=3)                       # uncoupled
    for _ in range(5):
        select_skills(_Q, n=3, action="explain")     # coupled
    r = entropy_report()
    assert r["coupled_share"] == 0.5


def test_entropy_window_bounds_sample():
    for _ in range(30):
        select_skills(_Q, n=3)
    r = entropy_report(window=10)
    assert r["n"] == 10
