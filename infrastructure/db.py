"""
infrastructure/db.py — one place that knows where every SQLite database lives.

Historically each module computed its own path
(`os.path.join(..., "logs", "x.db")`), scattering ~26 hardcoded DB paths across
~20 modules. This registry centralizes them so:

  * there is a single source of truth for every database location, and
  * setting the env var AMAGRA_DB=/path/to/amagra.db collapses *all* logical
    databases into one file (single-file mode) without touching any caller — the
    planned 1.0.x consolidation becomes a one-env-var flip.

Default behavior is unchanged: separate files in their existing locations, so
adopting this module is a pure refactor with no data migration.

Usage
-----
    from infrastructure import db
    conn = db.connect("runs")          # sqlite3.Connection
    p    = db.path("decisions")        # absolute path, if you need the string
"""

import os
import sqlite3

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Logical name -> path relative to the project root (current separate-file layout).
REGISTRY: dict[str, str] = {
    # Durable user data
    "memory":         os.path.join("memory", "agent_memory.db"),
    "api_keys":       os.path.join("memory", "api_keys.db"),
    "stripe_events":  os.path.join("memory", "stripe_events.db"),
    "registrations":  os.path.join("memory", "registrations.db"),
    # Task queue (project root)
    "tasks":          "tasks.db",
    # Telemetry / decision cluster
    "decisions":      os.path.join("logs", "decisions.db"),
    "runs":           os.path.join("logs", "runs.db"),
    "gate":           os.path.join("logs", "gate.db"),
    "risk_gate":      os.path.join("logs", "risk_gate.db"),
    "events":         os.path.join("logs", "events.db"),
    "feedback":       os.path.join("logs", "feedback.db"),
    "sessions":       os.path.join("logs", "sessions.db"),
    "contradictions": os.path.join("logs", "contradictions.db"),
    "snapshots":      os.path.join("logs", "snapshots.db"),
    "world_model":    os.path.join("logs", "world_model.db"),
    "step_verify":    os.path.join("logs", "step_verify.db"),
    "traces":         os.path.join("logs", "traces.db"),
    "arena":          os.path.join("logs", "arena.db"),
    "telemetry":      os.path.join("logs", "telemetry.db"),
}


def _single_file() -> str:
    """The single-file override, if AMAGRA_DB is set (read live so tests can set it)."""
    return os.environ.get("AMAGRA_DB", "").strip()


def path(name: str) -> str:
    """Absolute filesystem path for a logical database name. Ensures the parent dir exists."""
    if name not in REGISTRY:
        raise KeyError(f"unknown database '{name}'; known: {sorted(REGISTRY)}")

    from infrastructure.paths import base_dir
    root = base_dir()  # project dir by default; AMAGRA_DATA_DIR relocates (packaged app)

    single = _single_file()
    if single:
        target = single if os.path.isabs(single) else os.path.join(root, single)
    else:
        target = os.path.join(root, REGISTRY[name])

    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return target


def connect(name: str, **kwargs) -> sqlite3.Connection:
    """sqlite3.connect for a logical database name (parent dir is created if needed)."""
    return sqlite3.connect(path(name), **kwargs)


def distinct_paths() -> list[str]:
    """Every distinct DB file path the registry resolves to.

    In default (separate-file) mode this is one path per logical name; in
    single-file mode (AMAGRA_DB set) it collapses to the single file. Useful for
    one-time setup over the *physical* databases (e.g. enabling WAL) without
    touching the same file N times.
    """
    seen: dict[str, None] = {}
    for name in REGISTRY:
        seen.setdefault(path(name), None)
    return list(seen)
