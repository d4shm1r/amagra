"""
event_bus.py — Runtime Event Bus (Phase 35)

Decouples every component from every other component.
Components emit typed events; subscribers react without
needing to know who emitted.

Design:
  - In-process singleton (one bus per Python process)
  - Synchronous emit (fire-and-forget; exceptions in handlers
    are caught and logged, never re-raised)
  - Thread-safe (RLock around subscriber map)
  - SQLite persistence to logs/events.db for replay and analytics
  - Wildcard subscriptions via prefix matching (e.g. "plan.*")

Usage:
    from infrastructure.event_bus import emit, subscribe, EventType

    # Subscribe
    subscribe(EventType.STEP_COMPLETED, my_handler)

    # Emit
    emit(EventType.PLAN_CREATED, {"steps": 4, "mode": "llm"})

Handlers receive: handler(event_type: str, payload: dict, ts: float)
"""

import json
import os
import sqlite3
import threading
import time
from collections import defaultdict
from enum import Enum
from typing import Callable

_DB_PATH   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "logs", "events.db")
_DB_INITED = False
_LOCK      = threading.RLock()
_HANDLERS: dict[str, list[Callable]] = defaultdict(list)


# ── Event taxonomy ────────────────────────────────────────────

class EventType(str, Enum):
    # Session lifecycle
    SESSION_STARTED        = "session.started"
    SESSION_ENDED          = "session.ended"

    # Query lifecycle
    QUERY_RECEIVED         = "query.received"
    AGENT_SELECTED         = "agent.selected"
    RESPONSE_GENERATED     = "response.generated"

    # Planning
    PLAN_CREATED           = "plan.created"
    PLAN_STEP_STARTED      = "plan.step.started"
    PLAN_STEP_COMPLETED    = "plan.step.completed"
    PLAN_STEP_FAILED       = "plan.step.failed"
    PLAN_STEP_RETRY        = "plan.step.retry"
    PLAN_ABORTED           = "plan.aborted"
    PLAN_COMPLETED         = "plan.completed"

    # Verification
    STEP_VERIFIED_PASS     = "step.verified.pass"
    STEP_VERIFIED_FAIL     = "step.verified.fail"

    # Risk
    RISK_COMPUTED          = "risk.computed"
    REFLECTION_TRIGGERED   = "reflection.triggered"
    REFLECTION_COMPLETED   = "reflection.completed"

    # Memory
    MEMORY_RETRIEVED       = "memory.retrieved"
    MEMORY_STORED          = "memory.stored"
    CONTRADICTION_DETECTED = "contradiction.detected"

    # Learning
    ROUTING_WEIGHT_CHANGED = "routing.weight.changed"
    LEARNING_UPDATE        = "learning.update"

    # World model
    WORLD_MODEL_UPDATED    = "world.model.updated"

    # Metrics
    UCI_COMPUTED           = "uci.computed"


# ── DB persistence ────────────────────────────────────────────

def _ensure_db() -> None:
    global _DB_INITED
    if _DB_INITED:
        return
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,
            event_type TEXT    NOT NULL,
            session_id TEXT,
            run_id     TEXT,
            payload    TEXT
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_ev_type ON events(event_type)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ev_ts   ON events(ts)")
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    _DB_INITED = True


def _persist(event_type: str, payload: dict, ts: float) -> None:
    try:
        _ensure_db()
        con = sqlite3.connect(_DB_PATH, timeout=2)
        con.execute(
            "INSERT INTO events (ts, event_type, session_id, run_id, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, event_type,
             payload.get("session_id"), payload.get("run_id"),
             json.dumps(payload)),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[event_bus] persist error: {e}")


# ── Public API ────────────────────────────────────────────────

def subscribe(event_type: "str | EventType", handler: Callable) -> None:
    """Register handler for event_type (or prefix with '*' suffix)."""
    key = str(event_type)
    with _LOCK:
        _HANDLERS[key].append(handler)


def unsubscribe(event_type: "str | EventType", handler: Callable) -> None:
    key = str(event_type)
    with _LOCK:
        _HANDLERS[key] = [h for h in _HANDLERS[key] if h is not handler]


def emit(event_type: "str | EventType", payload: dict = None,
         persist: bool = True) -> None:
    """
    Emit an event to all matching subscribers.

    Handlers are called synchronously. Any exception in a handler is
    caught and printed — it never interrupts the emitter.

    persist=False skips SQLite write (useful for high-frequency events).
    """
    key     = str(event_type)
    payload = payload or {}
    ts      = time.time()

    # Collect matching handlers: exact match + wildcard prefix
    with _LOCK:
        handlers = list(_HANDLERS.get(key, []))
        # Wildcard: "plan.*" matches "plan.created", "plan.step.started", etc.
        prefix = key.rsplit(".", 1)[0] + ".*"
        handlers += list(_HANDLERS.get(prefix, []))
        handlers += list(_HANDLERS.get("*", []))   # global wildcard

    for handler in handlers:
        try:
            handler(key, payload, ts)
        except Exception as e:
            print(f"[event_bus] handler error ({key}): {e}")

    if persist:
        _persist(key, payload, ts)


def recent_events(n: int = 50, event_type: str = None) -> list:
    """Fetch recent events from the DB for the UI / analytics."""
    try:
        _ensure_db()
        con = sqlite3.connect(_DB_PATH, timeout=2)
        if event_type:
            rows = con.execute(
                "SELECT ts, event_type, payload FROM events "
                "WHERE event_type=? ORDER BY id DESC LIMIT ?",
                (event_type, n)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT ts, event_type, payload FROM events "
                "ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        con.close()
        return [
            {"ts": r[0], "type": r[1], "payload": json.loads(r[2] or "{}")}
            for r in rows
        ]
    except Exception:
        return []


def event_counts(since_ts: float = None) -> dict:
    """Aggregate event counts by type (for UCI dashboard)."""
    try:
        _ensure_db()
        con   = sqlite3.connect(_DB_PATH, timeout=2)
        since = since_ts or (time.time() - 3600)   # default: last hour
        rows  = con.execute(
            "SELECT event_type, COUNT(*) FROM events "
            "WHERE ts >= ? GROUP BY event_type", (since,)
        ).fetchall()
        con.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}
