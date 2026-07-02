"""
identity.py — the Identity contract (read-only aggregator).

Amagra's identity — who the system is for, what principles govern it, and what
it has learned — has always existed, but scattered: preferences in
config/profile.json, goals in the task-graph store, permissions in api_keys,
accumulated learning in decision weights + calibration + memory. No subsystem
*owned* it, so nothing could state (let alone test) the invariant that matters:

    Capability replacement must not modify identity.
    Identity changes only through learning. Orchestration changes only
    through engineering. Capabilities change only through replacement.

This module is that ownership surface. It is a **pure consumer** (same posture
as infrastructure/transparency.py): it stores nothing and mutates nothing —
every subsystem keeps its own storage. What it adds is a single serializable
view, split by *how each part is allowed to change*:

    intrinsic — changes rarely, via explicit configuration or governance
                (profile, goals, permissions)
    learned   — changes continuously, via attributable learning events
                (decision weights, calibration, memory)

plus a stable `fingerprint()` so the invariants above become regression tests
(see tests/test_identity.py) instead of slogans, and `changed_paths()` so any
identity drift is attributable to a specific subtree.

See docs/design/IDENTITY.md for the architectural contract.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List

IDENTITY_SCHEMA_VERSION = 1

# Volatile top-level keys excluded from the fingerprint: they change on every
# call without any identity mutation having occurred.
_FINGERPRINT_EXCLUDE = ("meta",)


# ── Intrinsic sources ─────────────────────────────────────────

def _intrinsic_profile() -> Dict[str, Any]:
    """User preferences / values from config/profile.json (may be absent)."""
    try:
        from core.user_profile import _load_profile
        return _load_profile() or {}
    except Exception:
        return {}


def _intrinsic_goals() -> Dict[str, Any]:
    """Persistent goals from the task-graph store (titles + status only)."""
    try:
        from infrastructure.task_graph import list_graphs
        graphs = list_graphs() or []
        return {
            "count": len(graphs),
            "goals": [
                {"goal": g.get("goal", "")[:120], "status": g.get("status", "")}
                for g in graphs[:20]
            ],
        }
    except Exception:
        return {}


def _intrinsic_permissions() -> Dict[str, Any]:
    """Access grants as tier structure — never key material (hashes stay in
    core/api_keys.py; list_keys already excludes raw keys)."""
    try:
        from core.api_keys import list_keys
        keys = list_keys() or []
        tiers: Dict[str, int] = {}
        for k in keys:
            t = k.get("tier", "unknown")
            tiers[t] = tiers.get(t, 0) + 1
        return {
            "active_keys": sum(1 for k in keys if k.get("active")),
            "tiers":       tiers,
        }
    except Exception:
        return {}


# ── Learned sources ───────────────────────────────────────────

def _learned_weights() -> Dict[str, Any]:
    """Per-agent decision weights — the long-term routing experience."""
    try:
        from decision.weights import load
        return {a: round(float(w), 4) for a, w in load().items()}
    except Exception:
        return {}


def _learned_calibration() -> Dict[str, Any]:
    """Per-agent confidence calibration (EMA + sample count)."""
    try:
        from decision.weights import get_all_calibration
        return get_all_calibration() or {}
    except Exception:
        return {}


def _learned_memory() -> Dict[str, Any]:
    """Memory shape (counts + quality by type) — references, not contents.
    The records themselves stay in the MemoryStore; identity carries the
    reference surface (what kinds of experience exist, and how much)."""
    try:
        from memory_core.db import memory_stats
        stats = memory_stats() or {}
        return {
            "total":   stats.get("total", 0),
            "by_type": {
                t: {"count": v.get("count", 0)}
                for t, v in (stats.get("by_type") or {}).items()
            },
        }
    except Exception:
        return {}


# ── The contract surface ──────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    """
    One serializable view of identity, split by mutation discipline.

    Every source degrades to {} when its subsystem is absent (fresh install,
    partial deployment) — the *shape* of identity is always present even when
    its content is empty.
    """
    return {
        "intrinsic": {
            "profile":     _intrinsic_profile(),
            "goals":       _intrinsic_goals(),
            "permissions": _intrinsic_permissions(),
        },
        "learned": {
            "decision_weights": _learned_weights(),
            "calibration":      _learned_calibration(),
            "memory":           _learned_memory(),
        },
        "meta": {
            "schema_version": IDENTITY_SCHEMA_VERSION,
            "ts":             time.time(),
        },
    }


def fingerprint(snap: Dict[str, Any] | None = None) -> str:
    """
    Stable hash of the identity content (volatile meta excluded).

    Two snapshots taken with no intervening learning event or configuration
    change must fingerprint identically — this is what the invariant tests
    assert across provider swaps, cache resets, and runtime restarts.
    """
    snap = snap if snap is not None else snapshot()
    content = {k: v for k, v in snap.items() if k not in _FINGERPRINT_EXCLUDE}
    canonical = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def changed_paths(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    """
    Dotted paths that differ between two snapshots (meta excluded) — the
    attribution surface: any identity change names the exact subtree that
    moved, so "why did identity change?" always has a concrete answer
    (e.g. 'learned.decision_weights.python_dev').
    """
    diffs: List[str] = []

    def _walk(a: Any, b: Any, path: str) -> None:
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                _walk(a.get(key), b.get(key), f"{path}.{key}" if path else key)
        elif a != b:
            diffs.append(path)

    a = {k: v for k, v in before.items() if k not in _FINGERPRINT_EXCLUDE}
    b = {k: v for k, v in after.items() if k not in _FINGERPRINT_EXCLUDE}
    _walk(a, b, "")
    return diffs
