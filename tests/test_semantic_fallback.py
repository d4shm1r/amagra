"""
Tests for the semantic routing fallback (orchestration/semantic_fallback.py)
and its flag-gated integration into core_brain.think().

No Ollama required: the embedding provider is monkeypatched with a deterministic
stub so the k-NN maths and the core_brain wiring are exercised hermetically.
"""

import importlib

import pytest

import orchestration.semantic_fallback as sf

# Capture the REAL _build_index before the autouse fixture stubs it.
_ORIG_BUILD = sf._build_index


# ── a deterministic fake embedder ────────────────────────────────────────────
class _FakeProvider:
    """Maps a keyword bag to a fixed 3-d vector so nearest-neighbour is testable."""
    model_id = "fake-embed"

    _BASIS = {
        "loop": [1.0, 0.0, 0.0], "memory": [1.0, 0.0, 0.0],      # python-ish
        "browser": [0.0, 1.0, 0.0], "page": [0.0, 1.0, 0.0],     # web-ish
        "packet": [0.0, 0.0, 1.0], "subnet": [0.0, 0.0, 1.0],    # net-ish
    }

    def embed(self, text: str):
        v = [0.0, 0.0, 0.0]
        for kw, basis in self._BASIS.items():
            if kw in text.lower():
                v = [a + b for a, b in zip(v, basis)]
        if v == [0.0, 0.0, 0.0]:
            v = [0.01, 0.01, 0.01]     # avoid a zero vector
        return v


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """Each test starts from a clean, disabled module with the fake provider."""
    monkeypatch.setattr(sf, "_PROVIDER", _FakeProvider())
    monkeypatch.setattr(sf, "_EX_VECS", None)
    monkeypatch.setattr(sf, "_EX_LABELS", None)
    monkeypatch.setattr(sf, "_DISABLED", False)
    # Small, fixed exemplar set so we don't depend on training data.
    monkeypatch.setattr(sf, "_exemplars", lambda: [
        ("python_dev", "an infinite loop eats all memory"),
        ("web_dev", "the page renders wrong in the browser"),
        ("it_networking", "packet loss across the subnet"),
    ])
    # Force rebuild from the fake exemplars, bypassing any on-disk cache.
    monkeypatch.setattr(sf, "_build_index",
                        lambda rebuild=False: _real_build(monkeypatch))
    yield


def _real_build(monkeypatch):
    pairs = sf._exemplars()
    sf._EX_LABELS = [lab for lab, _ in pairs]
    sf._EX_VECS = [sf._norm(sf._PROVIDER.embed(t)) for _, t in pairs]
    return True


# ── is_enabled / gating ──────────────────────────────────────────────────────
def test_enabled_by_default(monkeypatch):
    # ON by default since 2026-07-07 (threshold-study ship gate passed).
    monkeypatch.delenv("AGENTIC_SEMANTIC_FALLBACK", raising=False)
    assert sf.is_enabled() is True


def test_disabled_by_explicit_flag(monkeypatch):
    monkeypatch.setenv("AGENTIC_SEMANTIC_FALLBACK", "0")
    assert sf.is_enabled() is False


def test_enabled_by_flag(monkeypatch):
    monkeypatch.setenv("AGENTIC_SEMANTIC_FALLBACK", "1")
    assert sf.is_enabled() is True


def test_empty_query_returns_none():
    assert sf.route("") is None
    assert sf.route("   ") is None


# ── k-NN correctness ─────────────────────────────────────────────────────────
def test_route_picks_nearest_label(monkeypatch):
    monkeypatch.setattr(sf, "_K", 1)
    agent, sim = sf.route("my loop leaks memory over time")
    assert agent == "python_dev"
    assert sim > 0.9                       # near-parallel to the python exemplar


def test_route_web_and_net(monkeypatch):
    monkeypatch.setattr(sf, "_K", 1)
    assert sf.route("blank page in the browser")[0] == "web_dev"
    assert sf.route("packet loss on the subnet")[0] == "it_networking"


def test_min_sim_floor_declines(monkeypatch):
    """With an impossibly high floor, even the nearest match is rejected."""
    monkeypatch.setattr(sf, "_K", 1)
    monkeypatch.setattr(sf, "_MIN_SIM", 0.99)
    assert sf.route("something totally unrelated with no basis words") is None


def test_query_embed_failure_is_crash_safe(monkeypatch):
    """Ollama dies AFTER the index is built: the query embed raises → route None."""
    class _Boom:
        model_id = "fake-embed"
        def embed(self, text):
            raise RuntimeError("ollama down")
    # Pre-build the index with the good provider, then swap in the failing one
    # and neutralise the fixture's rebuild so route() uses the built index.
    sf._build_index()
    monkeypatch.setattr(sf, "_build_index", lambda rebuild=False: True)
    monkeypatch.setattr(sf, "_PROVIDER", _Boom())
    assert sf.route("anything") is None


def test_index_build_failure_is_crash_safe(monkeypatch):
    """Ollama down at boot: the REAL _build_index must catch and return None route."""
    # Restore the real build (fixture stubbed it) and make the provider explode.
    monkeypatch.setattr(sf, "_build_index", _ORIG_BUILD)
    monkeypatch.setattr(sf, "_EX_VECS", None)

    class _Boom:
        model_id = "boom"
        def embed(self, text):
            raise RuntimeError("ollama down")
    monkeypatch.setattr(sf, "_provider", lambda: _Boom())
    assert sf.route("anything") is None
    assert sf._DISABLED is True            # don't retry every call this session


# ── core_brain integration (flag-gated) ──────────────────────────────────────
def test_core_brain_rescue_only_when_enabled(monkeypatch):
    cb = importlib.import_module("orchestration.core_brain")

    # A query with no domain that would otherwise fall to the LLM/knowledge path.
    query = "the thing keeps doing the annoying repeated behaviour again"

    # Force the semantic router to a known answer, bypassing embeddings entirely.
    monkeypatch.setattr(sf, "route", lambda q: ("web_dev", 0.61))

    # Flag OFF → rescue must NOT fire (route must not be web_dev via semantic).
    monkeypatch.setenv("AGENTIC_SEMANTIC_FALLBACK", "0")
    d_off = cb.think(query, {})

    # Flag ON → rescue fires → web_dev with light reflection.
    monkeypatch.setenv("AGENTIC_SEMANTIC_FALLBACK", "1")
    d_on = cb.think(query, {})

    assert d_on.agent_strategy[0] == "web_dev"
    assert d_on.reflect_level == "light"
    # The ON decision differs from OFF (proves the flag changed behaviour).
    assert d_on.agent_strategy[0] != d_off.agent_strategy[0] or d_off.agent_strategy[0] == "web_dev"
