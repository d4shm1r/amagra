"""
Unit tests for cognition/context_snapshot.py pure functions:
  _short_hash, _token_estimate, _get_system_prompt,
  begin, record_routing, record_memories, finalize, recent, diff.
"""

import os
import sys
import uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.context_snapshot as cs


# ── _short_hash ───────────────────────────────────────────────────────────────

def test_short_hash_length():
    h = cs._short_hash("hello world")
    assert len(h) == 12

def test_short_hash_custom_length():
    h = cs._short_hash("hello", n=8)
    assert len(h) == 8

def test_short_hash_deterministic():
    h1 = cs._short_hash("test")
    h2 = cs._short_hash("test")
    assert h1 == h2

def test_short_hash_different_inputs():
    assert cs._short_hash("a") != cs._short_hash("b")


# ── _token_estimate ───────────────────────────────────────────────────────────

def test_token_estimate_empty():
    assert cs._token_estimate("") == 1  # max(1, 0)

def test_token_estimate_single_word():
    assert cs._token_estimate("hello") == 1

def test_token_estimate_multiple_words():
    assert cs._token_estimate("hello world foo") == 3

def test_token_estimate_with_punctuation():
    result = cs._token_estimate("hello, world!")
    assert result >= 1


# ── _get_system_prompt ────────────────────────────────────────────────────────

def test_get_system_prompt_unknown_agent():
    result = cs._get_system_prompt("unknown_agent_xyz")
    assert result == ""

def test_get_system_prompt_known_agent():
    # Returns string (may be empty if agent module fails to load under stub)
    result = cs._get_system_prompt("python_dev")
    assert isinstance(result, str)

def test_get_system_prompt_all_known():
    for agent in ["python_dev", "it_networking", "ai_ml", "knowledge_learning", "terse"]:
        result = cs._get_system_prompt(agent)
        assert isinstance(result, str)


# ── begin + record_* (DB-backed) ─────────────────────────────────────────────

def test_begin_no_crash():
    ctx_id = f"test-ctx-{uuid.uuid4().hex[:8]}"
    cs.begin(ctx_id, "test query")

def test_record_routing_no_crash():
    ctx_id = f"test-routing-{uuid.uuid4().hex[:8]}"
    cs.begin(ctx_id, "test query")
    cs.record_routing("python_dev", 0.85, "respond", "simple", "keyword match")

def test_record_memories_no_crash():
    ctx_id = f"test-mem-{uuid.uuid4().hex[:8]}"
    cs.begin(ctx_id, "test query")
    cs.record_memories([])  # empty list is safe

def test_record_reflection_no_crash():
    ctx_id = f"test-reflect-{uuid.uuid4().hex[:8]}"
    cs.begin(ctx_id, "test query")
    cs.record_reflection(0.6, 0.8)


# ── recent ────────────────────────────────────────────────────────────────────

def test_recent_returns_list():
    result = cs.recent(n=5)
    assert isinstance(result, list)

def test_recent_bounded():
    result = cs.recent(n=3)
    assert len(result) <= 3


# ── diff ──────────────────────────────────────────────────────────────────────

def test_diff_nonexistent_ids():
    result = cs.diff(999991, 999992)
    assert isinstance(result, dict)
    # Either error message or empty/partial diff — must not raise


# ── get_by_id / get_by_context_id ────────────────────────────────────────────

def test_get_by_id_nonexistent():
    result = cs.get_by_id(999999)
    assert result is None

def test_get_by_context_id_nonexistent():
    result = cs.get_by_context_id("nonexistent-ctx-xyz")
    assert result is None
