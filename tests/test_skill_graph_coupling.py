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

from infrastructure.skill_graph import (
    select_skills, top_agent, _action_fits, _BIAS_PREFER_AGENT, SkillNode,
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
