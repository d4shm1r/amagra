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


# ── _is_instance_mismatch — template-collision (context-bleed) guard ──────────

def test_instance_mismatch_disjoint_numbers():
    # cow/sheep eval: query has its own givens, memory carries a different set
    assert mc._is_instance_mismatch(
        "A farmer has 10 cows. How many cows remain?",
        "The answer is 8 sheep left; 15 sheep minus the 7 that ran away.",
    )

def test_instance_mismatch_shared_number_is_ok():
    # Shares a number → plausibly the same instance → do not drop
    assert not mc._is_instance_mismatch(
        "What is 10% of 50?", "Earlier: 10% of 200 is 20.")

def test_instance_mismatch_non_numeric_query_never_fires():
    assert not mc._is_instance_mismatch(
        "How do I configure nginx?", "To configure nginx on port 8080, edit ...")

def test_instance_mismatch_ignores_glued_identifiers():
    # port8080 / v3 are identifiers, not problem quantities — must not count
    assert not mc._is_instance_mismatch(
        "restart the service on port8080", "the v3 daemon listens on port8080")


# ── get_memory_context — bleed guard end-to-end (fake backend, no Ollama) ─────

class _FakeRecord:
    def __init__(self, content, score, agent="knowledge_learning",
                 mem_type="lesson", _id=1):
        self.content, self.score = content, score
        self.agent, self.mem_type, self.id = agent, mem_type, _id

class _FakeBackend:
    def __init__(self, records):
        self._records = records
    def retrieve(self, query, k=3, agent_name=None, caller="", prefer_agent=None):
        return self._records

def _patch_backend(monkeypatch, records):
    import memory_core.backend as be
    monkeypatch.setattr(be, "get_backend", lambda: _FakeBackend(records))

def test_get_memory_context_drops_bled_instance(monkeypatch):
    # The stale sheep answer scores 0.77 (≥ min_score) but is a different
    # quantitative instance than the cow query → must be filtered out.
    sheep = _FakeRecord(
        "The answer is 8 sheep left; 15 sheep, all but 8 ran away.", score=0.77)
    _patch_backend(monkeypatch, [sheep])
    ctx = mc.get_memory_context(
        "A farmer has 10 cows. How many cows remain?", "knowledge_learning")
    assert ctx == "", f"bled sheep memory should be dropped, got: {ctx!r}"

def test_get_memory_context_keeps_legitimate_recall(monkeypatch):
    # Non-numeric, on-topic memory must still be injected.
    rec = _FakeRecord(
        "nginx reverse proxy: set proxy_pass in the server block.", score=0.80)
    _patch_backend(monkeypatch, [rec])
    ctx = mc.get_memory_context("how do I configure an nginx proxy?", "it_networking")
    assert "nginx reverse proxy" in ctx
