"""
Tests for memory_core/context.py:
  _set_fork_excluded_ids, _clear_fork_excluded_ids,
  get_memory_context (empty query → returns ""),
  save_to_memory (empty content → silent no-op).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_core.context as mc


# ── _set_fork_excluded_ids ────────────────────────────────────────────────────

def test_set_fork_excluded_ids():
    mc._set_fork_excluded_ids([1, 2, 3])
    from memory_core.context import _fork_local
    assert _fork_local.excluded_ids == {1, 2, 3}

def test_set_fork_excluded_ids_none():
    mc._set_fork_excluded_ids(None)
    from memory_core.context import _fork_local
    assert _fork_local.excluded_ids == set()

def test_clear_fork_excluded_ids():
    mc._set_fork_excluded_ids([99])
    mc._clear_fork_excluded_ids()
    from memory_core.context import _fork_local
    assert _fork_local.excluded_ids == set()


# ── get_memory_context — empty query guard ────────────────────────────────────

def test_get_memory_context_empty_query():
    result = mc.get_memory_context("", "python_dev")
    assert result == ""

def test_get_memory_context_whitespace_query():
    result = mc.get_memory_context("   ", "it_networking")
    assert result == ""

def test_get_memory_context_nonempty_returns_str():
    # With Ollama offline, backend retrieval returns empty or fails silently
    result = mc.get_memory_context("how to configure nginx", "it_networking")
    assert isinstance(result, str)


# ── save_to_memory — empty content guard ─────────────────────────────────────

def test_save_to_memory_empty_content():
    # Must not raise, even if backend unavailable
    mc.save_to_memory("python_dev", "code", "")

def test_save_to_memory_whitespace_only():
    mc.save_to_memory("it_networking", "chat", "   ")

def test_save_to_memory_nonempty_does_not_crash():
    # Backend may fail, but it must fail silently
    mc.save_to_memory("python_dev", "code", "print('hello')", metadata={"task": "test"})
