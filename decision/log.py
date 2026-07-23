# ~/agentic-ai/decision_log.py
# ─────────────────────────────────────────────────────────────
# Logs every core_brain decision to SQLite.
# Answers: what did the brain decide, what did the router want,
# did they conflict, and was reflection triggered?
#
# Used by coordinator.py (write) and api.py /decisions (read).
# ─────────────────────────────────────────────────────────────

import sqlite3
import os
from datetime import datetime, timezone

from infrastructure.db import path as _dbpath, tune as _tune
DB_PATH = _dbpath("decisions")


def _conn():
    # Fresh connection per call, used and closed within one frame (never shared
    # across threads) — see #195 and tests/test_db_thread_safety.py.
    return _tune(sqlite3.connect(DB_PATH, check_same_thread=False))


def init():
    os.makedirs("logs", exist_ok=True)
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS brain_decisions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            run_id        TEXT    DEFAULT '',
            task          TEXT,
            action        TEXT,
            complexity    TEXT,
            brain_agent   TEXT,
            router_agent  TEXT,
            final_agent   TEXT,
            conflict      INTEGER,
            reflect       INTEGER,
            reflect_type  TEXT,
            reflect_level TEXT    DEFAULT 'none',
            duration_ms   INTEGER,
            regret        REAL    DEFAULT 0.0,
            confidence    REAL    DEFAULT 0.67
        )
    """)
    for migration in [
        "ALTER TABLE brain_decisions ADD COLUMN regret REAL DEFAULT 0.0",
        "ALTER TABLE brain_decisions ADD COLUMN reflect_level TEXT DEFAULT 'none'",
        "ALTER TABLE brain_decisions ADD COLUMN confidence REAL DEFAULT 0.67",
        "ALTER TABLE brain_decisions ADD COLUMN run_id TEXT DEFAULT ''",
    ]:
        try:
            c.execute(migration)
        except Exception:
            pass
    # Indexes must come after migrations so the columns they reference exist.
    c.execute("CREATE INDEX IF NOT EXISTS idx_final  ON brain_decisions(final_agent);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_run_id ON brain_decisions(run_id);")
    c.commit()
    c.close()


def log(task: str, action: str, complexity: str,
        brain_agent: str, router_agent: str, final_agent: str,
        conflict: bool, reflect: bool, reflect_type: str,
        duration_ms: int = 0, regret: float = 0.0,
        reflect_level: str = "none", confidence: float = 0.67,
        run_id: str = "") -> int:
    """
    Log a brain decision. Returns the inserted row ID so callers can link
    this decision to a session record (session_id FK).
    Returns -1 on failure.
    """
    try:
        c = _conn()
        cur = c.execute("""
            INSERT INTO brain_decisions
            (timestamp, run_id, task, action, complexity, brain_agent,
             router_agent, final_agent, conflict, reflect, reflect_type,
             reflect_level, duration_ms, regret, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            run_id or "",
            task[:200],
            action, complexity,
            brain_agent, router_agent, final_agent,
            int(conflict), int(reflect), reflect_type,
            reflect_level, duration_ms,
            round(regret, 4), round(confidence, 4),
        ))
        row_id = cur.lastrowid
        c.commit()
        c.close()
        return row_id
    except Exception as e:
        print(f"[decision_log] write error: {e}")
        return -1


def recent(limit: int = 50) -> list:
    try:
        c = _conn()
        rows = c.execute("""
            SELECT id, timestamp, task, action, complexity,
                   brain_agent, router_agent, final_agent,
                   conflict, reflect, reflect_type,
                   COALESCE(reflect_level, 'none'),
                   duration_ms,
                   COALESCE(regret, 0.0),
                   COALESCE(confidence, 0.67)
            FROM brain_decisions
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        c.close()
        return [
            {
                "id":            r[0],
                "timestamp":     r[1],
                "task":          r[2],
                "action":        r[3],
                "complexity":    r[4],
                "brain_agent":   r[5],
                "router_agent":  r[6],
                "final_agent":   r[7],
                "conflict":      bool(r[8]),
                "reflect":       bool(r[9]),
                "reflect_type":  r[10],
                "reflect_level": r[11],
                "duration_ms":   r[12],
                "regret":        r[13],
                "confidence":    r[14],
            }
            for r in rows
        ]
    except Exception:
        return []


def get_by_id(decision_id: int) -> dict | None:
    try:
        c = _conn()
        row = c.execute("""
            SELECT id, timestamp, task, action, complexity,
                   brain_agent, router_agent, final_agent,
                   conflict, reflect, reflect_type,
                   COALESCE(reflect_level, 'none'),
                   duration_ms,
                   COALESCE(regret, 0.0),
                   COALESCE(confidence, 0.67)
            FROM brain_decisions WHERE id = ?
        """, (decision_id,)).fetchone()
        c.close()
        if not row:
            return None
        return {
            "id":            row[0],
            "timestamp":     row[1],
            "task":          row[2],
            "action":        row[3],
            "complexity":    row[4],
            "brain_agent":   row[5],
            "router_agent":  row[6],
            "final_agent":   row[7],
            "conflict":      bool(row[8]),
            "reflect":       bool(row[9]),
            "reflect_type":  row[10],
            "reflect_level": row[11],
            "duration_ms":   row[12],
            "regret":        row[13],
            "confidence":    row[14],
        }
    except Exception:
        return None


def regret_mean(last_n: int = 100) -> float:
    """Mean regret over the last N decisions. 0.0 = perfect routing."""
    try:
        c = _conn()
        row = c.execute(
            "SELECT AVG(COALESCE(regret, 0.0)) FROM "
            "(SELECT regret FROM brain_decisions ORDER BY id DESC LIMIT ?)",
            (last_n,)
        ).fetchone()
        c.close()
        return round(row[0], 4) if row and row[0] is not None else 0.0
    except Exception:
        return 0.0


def agent_regret_mean(agent: str, last_n: int = 50) -> float:
    """
    Mean regret for a specific agent over its last N decisions.
    Non-zero only on multi-domain decisions where an alternative existed.
    """
    try:
        c = _conn()
        row = c.execute(
            "SELECT AVG(COALESCE(regret, 0.0)) FROM "
            "(SELECT regret FROM brain_decisions WHERE final_agent=? ORDER BY id DESC LIMIT ?)",
            (agent, last_n)
        ).fetchone()
        c.close()
        return round(row[0], 4) if row and row[0] is not None else 0.0
    except Exception:
        return 0.0


def conflict_rate(last_n: int = 100) -> dict:
    """Summary stats for dashboard or debugging.

    O7 note: the `conflict` column no longer means "brain overrode the keyword
    router" (that router was removed in #20). It now flags *routing indecision*
    — the brain's confidence for the route was below the decisiveness floor.
    `conflict_rate` is therefore the recent low-confidence-routing rate; consumers
    (e.g. the maintenance auto-rebuild trigger) read it as a routing-health signal.
    """
    try:
        c = _conn()
        # `LIMIT ?` on a bare `COUNT(*)` is a no-op — the aggregate is a single
        # row, so the limit never restricts it and every count was all-time, not
        # the last N (O7 residual). Take the window in a subquery instead, then
        # aggregate the returned rows in one pass.
        rows = c.execute(
            "SELECT conflict, reflect FROM brain_decisions ORDER BY id DESC LIMIT ?",
            (last_n,)
        ).fetchall()
        c.close()
        total     = len(rows)
        conflicts = sum(1 for r in rows if r[0])
        reflected = sum(1 for r in rows if r[1])
        return {
            "total":          total,
            "conflicts":      conflicts,
            "conflict_rate":  round(conflicts / total, 3) if total else 0,
            "reflect_rate":   round(reflected / total, 3) if total else 0,
        }
    except Exception:
        return {"total": 0, "conflicts": 0, "conflict_rate": 0, "reflect_rate": 0}


# Auto-init on import
init()
