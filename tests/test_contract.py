"""
Neutral-contract tests — core/contract.py is the wire between core and agents.

Two things matter here: the data structures are frozen (an extension can't mutate
a Context it was handed), and trim_history() reproduces the old langchain
trim_messages semantics on plain Msg tuples — preserve the system turn, hard-cut
the rest, inject the truncation notice as an ASSISTANT turn (never a user turn).
"""
import dataclasses

import pytest

from core.contract import Context, Result, RoutingMeta, Msg, trim_history


# ── immutability of the wire types ─────────────────────────────
@pytest.mark.parametrize("obj,attr", [
    (Context(task="t"), "task"),
    (Msg("user", "hi"), "content"),
    (RoutingMeta(agent="a"), "confidence"),
    (Result(output="o"), "output"),
])
def test_wire_types_are_frozen(obj, attr):
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, attr, "mutated")


def test_context_defaults_are_lean():
    c = Context(task="t")
    assert c.history == () and dict(c.memory) == {} and c.run_id == ""


# ── trim_history: empty / under-limit pass through ─────────────
def test_empty_history_returns_empty():
    assert trim_history(()) == ()


def test_under_limit_history_is_unchanged():
    h = (Msg("user", "a"), Msg("assistant", "b"))
    assert trim_history(h, max_messages=10) == h


def test_exactly_at_limit_is_not_trimmed():
    h = tuple(Msg("user", str(i)) for i in range(5))
    assert trim_history(h, max_messages=5) == h


# ── trim_history: the cut ──────────────────────────────────────
def test_over_limit_keeps_last_n_and_injects_assistant_notice():
    h = tuple(Msg("user", str(i)) for i in range(10))
    out = trim_history(h, max_messages=3)
    # notice + the last 3
    assert len(out) == 4
    assert out[0].role == "assistant" and "10 → 3" in out[0].content
    assert [m.content for m in out[1:]] == ["7", "8", "9"]


def test_truncation_notice_is_never_a_user_turn():
    # A user-role notice would invite the model to "answer" the bookkeeping line.
    h = tuple(Msg("user", str(i)) for i in range(30))
    out = trim_history(h, max_messages=5)
    notice = next(m for m in out if "Context trimmed" in m.content)
    assert notice.role == "assistant"


def test_leading_system_message_is_preserved_across_the_cut():
    h = (Msg("system", "you are a bot"),) + tuple(Msg("user", str(i)) for i in range(10))
    out = trim_history(h, max_messages=3)
    assert out[0] == Msg("system", "you are a bot")
    assert out[1].role == "assistant" and "Context trimmed" in out[1].content
    assert [m.content for m in out[2:]] == ["7", "8", "9"]


def test_system_message_preserved_when_under_limit():
    h = (Msg("system", "sys"), Msg("user", "hi"))
    assert trim_history(h, max_messages=10) == h
