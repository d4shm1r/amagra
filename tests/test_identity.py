"""
Tests for models/identity.py — the Identity contract.

These are the invariant family from docs/design/IDENTITY.md §4, as regression gates:

  1. Capability replacement must not modify identity.
  2. Runtime restart preserves identity.
  3. Identity mutations are attributable (learned vs intrinsic subtree).
  4. Absence degrades content, never shape.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.identity as identity


# ── Shape & determinism ───────────────────────────────────────────────────────

def test_snapshot_shape_always_present():
    snap = identity.snapshot()
    assert set(snap) == {"intrinsic", "learned", "meta"}
    assert set(snap["intrinsic"]) == {"profile", "goals", "permissions"}
    assert set(snap["learned"]) == {"decision_weights", "calibration", "memory"}
    assert snap["meta"]["schema_version"] == identity.IDENTITY_SCHEMA_VERSION


def test_shape_survives_missing_subsystems(monkeypatch):
    # Invariant 4: on a fresh install every source is empty but the identity
    # structure is intact.
    for src in ("_intrinsic_profile", "_intrinsic_goals",
                "_intrinsic_permissions", "_learned_weights",
                "_learned_calibration", "_learned_memory"):
        monkeypatch.setattr(identity, src, lambda: {})
    snap = identity.snapshot()
    assert set(snap["intrinsic"]) == {"profile", "goals", "permissions"}
    assert set(snap["learned"]) == {"decision_weights", "calibration", "memory"}


def test_fingerprint_ignores_volatile_meta():
    a = identity.snapshot()
    b = dict(a, meta={"schema_version": 999, "ts": 0.0})
    assert identity.fingerprint(a) == identity.fingerprint(b)


def test_fingerprint_deterministic_without_mutation(monkeypatch):
    # Pin the sources so the test doesn't race live DB writes.
    monkeypatch.setattr(identity, "_learned_weights",
                        lambda: {"python_dev": 1.0, "terse": 0.98})
    a = identity.fingerprint()
    b = identity.fingerprint()
    assert a == b


# ── Invariant 1: capability replacement must not modify identity ─────────────

def test_provider_swap_does_not_modify_identity(monkeypatch):
    import providers.registry as registry

    before = identity.snapshot()

    # Swap the brain-model capability: different backend, fresh registry cache
    # (construction is lazy/cheap — no network, no key needed).
    monkeypatch.setenv("BRAIN_PROVIDER", "anthropic")
    monkeypatch.setattr(registry, "_model_cache", {})
    provider = registry.get_provider("brain")
    assert type(provider).__name__ == "AnthropicProvider"

    after = identity.snapshot()
    assert identity.fingerprint(before) == identity.fingerprint(after), (
        f"provider swap mutated identity: {identity.changed_paths(before, after)}"
    )


def test_embedding_provider_rebuild_does_not_modify_identity(monkeypatch):
    import providers.registry as registry

    before = identity.fingerprint()
    monkeypatch.setattr(registry, "_embed_cache", {})
    try:
        registry.get_embedding_provider()
    except Exception:
        pass  # backend may be unavailable in CI — the invariant still holds
    assert identity.fingerprint() == before


# ── Invariant 2: runtime restart preserves identity ──────────────────────────

def test_cache_reset_preserves_identity():
    # Simulate the restart-relevant part: drop the in-process weights cache so
    # the next snapshot re-reads durable state from disk.
    import decision.weights as weights

    before = identity.fingerprint()
    with weights._lock:
        weights._cache, weights._cache_ts = {}, 0.0
    after = identity.fingerprint()
    assert before == after, "identity must live in durable state, not process memory"


# ── Invariant 3: mutations are attributable to the right subtree ─────────────

def test_learned_change_touches_only_learned_subtree(monkeypatch):
    before = identity.snapshot()
    monkeypatch.setattr(
        identity, "_learned_weights",
        lambda: {**before["learned"]["decision_weights"], "python_dev": 0.42},
    )
    after = identity.snapshot()

    paths = identity.changed_paths(before, after)
    assert paths, "a learning event must change the fingerprintable content"
    assert all(p.startswith("learned.") for p in paths), paths
    assert "learned.decision_weights.python_dev" in paths
    assert identity.fingerprint(before) != identity.fingerprint(after)


def test_intrinsic_change_touches_only_intrinsic_subtree(monkeypatch):
    before = identity.snapshot()
    monkeypatch.setattr(
        identity, "_intrinsic_profile",
        lambda: {"name": "Dash", "communication_style": "terse"},
    )
    after = identity.snapshot()

    paths = identity.changed_paths(before, after)
    assert paths
    assert all(p.startswith("intrinsic.") for p in paths), paths


def test_no_mutation_no_changed_paths(monkeypatch):
    monkeypatch.setattr(identity, "_learned_weights", lambda: {"a": 1.0})
    a = identity.snapshot()
    b = identity.snapshot()
    assert identity.changed_paths(a, b) == []
