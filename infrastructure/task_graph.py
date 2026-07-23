# ~/agentic-ai/task_graph.py
# ─────────────────────────────────────────────────────────────
# Task Graph: schema + state store for multi-step goal execution.
#
# A TaskGraph is a goal decomposed into ordered steps.
# Steps declare dependencies; the executor respects them.
#
# Storage: tasks.db — two new tables alongside existing `tasks`.
#
# Tables:
#   task_graphs   — one row per goal
#   task_steps    — one row per step within a goal
# ─────────────────────────────────────────────────────────────

import sqlite3
import json
from datetime import datetime, timezone

from infrastructure.db import path as _dbpath, tune as _tune
DB_PATH = _dbpath("tasks")

VALID_AGENTS = {
    "it_networking", "python_dev", "dotnet_dev",
    "ai_ml", "knowledge_learning", "terse",
}

VALID_STEP_STATUSES = {"pending", "running", "completed", "failed", "skipped"}
VALID_GRAPH_STATUSES = {"pending", "running", "completed", "failed", "paused"}

# Legal step state transitions. Any attempt outside this matrix raises TransitionError.
# retry_step() is the only path that re-opens a failed step (failed → pending via SQL directly).
STEP_TRANSITIONS = {
    "pending":   {"running"},
    "running":   {"completed", "failed"},
    "completed": set(),   # terminal
    "failed":    set(),   # terminal — retry_step() bypasses this intentionally
    "skipped":   set(),   # terminal
}

# Legal graph state transitions.
GRAPH_TRANSITIONS = {
    "pending":   {"running"},
    "running":   {"completed", "failed", "paused"},
    "paused":    {"running", "failed"},
    "completed": set(),   # terminal
    "failed":    {"pending"},  # retry_step re-opens the graph via direct SQL
}


class TransitionError(Exception):
    """Raised when a state transition is illegal."""


def _assert_step_transition(graph_id: int, step_id: str, to_status: str):
    """Read current step status and raise TransitionError if the move is illegal."""
    c = _conn()
    row = c.execute(
        "SELECT status FROM task_steps WHERE graph_id=? AND step_id=?",
        (graph_id, step_id)
    ).fetchone()
    c.close()
    if not row:
        raise TransitionError(f"step '{step_id}' not found in graph {graph_id}")
    from_status = row["status"]
    allowed = STEP_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TransitionError(
            f"step '{step_id}': illegal transition {from_status!r} → {to_status!r}"
        )


def _assert_graph_transition(graph_id: int, to_status: str):
    """Read current graph status and raise TransitionError if the move is illegal."""
    c = _conn()
    row = c.execute("SELECT status FROM task_graphs WHERE id=?", (graph_id,)).fetchone()
    c.close()
    if not row:
        raise TransitionError(f"graph {graph_id} not found")
    from_status = row["status"]
    allowed = GRAPH_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TransitionError(
            f"graph {graph_id}: illegal transition {from_status!r} → {to_status!r}"
        )


# Structured failure types — replaces raw exception strings.
# Keep this list exhaustive; map new exceptions to the closest type.
FAILURE_TYPES = {
    "empty_response",    # agent returned nothing
    "trivial_response",  # response too short to be useful
    "refusal",           # agent refused ("I cannot", "I'm unable", ...)
    "code_missing",      # prompt requested code but none was produced
    "agent_error",       # coordinator raised an unexpected exception
    "timeout",           # inference took too long
    "dependency_error",  # a required previous step was unavailable
    "unknown",           # catch-all
}


def _conn():
    # Fresh per-call connection (never shared across threads); busy_timeout+WAL
    # applied centrally — see #195.
    c = _tune(sqlite3.connect(DB_PATH, check_same_thread=False))
    c.execute("PRAGMA synchronous=NORMAL;")
    c.row_factory = sqlite3.Row
    return c


def init_db():
    """Create task graph tables if they don't exist. Safe to call on every import."""
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS task_graphs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            goal         TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'pending',
            created_at   TEXT,
            started_at   TEXT,
            completed_at TEXT,
            metadata     TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS task_steps (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            graph_id     INTEGER NOT NULL,
            step_id      TEXT    NOT NULL,
            agent        TEXT    NOT NULL,
            prompt       TEXT    NOT NULL,
            depends_on   TEXT    NOT NULL DEFAULT '[]',
            status       TEXT    NOT NULL DEFAULT 'pending',
            input_data   TEXT    DEFAULT '{}',
            output_data  TEXT    DEFAULT '{}',
            started_at   TEXT,
            completed_at TEXT,
            error        TEXT,
            attempt      INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (graph_id) REFERENCES task_graphs(id)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_steps_graph ON task_steps(graph_id);")
    c.commit()
    # Migration: add failure_type column if this is an older DB.
    try:
        c.execute("ALTER TABLE task_steps ADD COLUMN failure_type TEXT")
        c.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    c.close()


def reset_running():
    """On startup: any step/graph left in 'running' from a previous crash → reset to 'pending'."""
    c = _conn()
    now = datetime.now(timezone.utc).isoformat()
    c.execute(
        "UPDATE task_steps SET status='pending', started_at=NULL WHERE status='running'"
    )
    c.execute(
        "UPDATE task_graphs SET status='pending', started_at=NULL WHERE status='running'"
    )
    c.commit()
    c.close()


def create_graph(goal: str, steps: list, metadata: dict = None) -> int:
    """
    Create a task graph from a goal and step list.

    Each step dict:
      id         — unique within this graph (e.g. "design")
      agent      — which specialist handles it
      prompt     — the task description for that agent
      depends_on — list of step IDs that must complete first (default [])

    Returns the graph_id.
    Raises ValueError on invalid input.
    """
    if not goal or not goal.strip():
        raise ValueError("goal cannot be empty")
    if not steps:
        raise ValueError("steps cannot be empty")

    seen_ids = set()
    for i, s in enumerate(steps):
        sid = s.get("id", "").strip()
        if not sid:
            raise ValueError(f"step[{i}] missing 'id'")
        if sid in seen_ids:
            raise ValueError(f"duplicate step id: '{sid}'")
        if s.get("agent", "").strip() not in VALID_AGENTS:
            raise ValueError(f"step '{sid}': invalid agent '{s.get('agent')}'")
        if not s.get("prompt", "").strip():
            raise ValueError(f"step '{sid}': prompt is empty")
        # Validate deps BEFORE registering sid — this catches self-references
        # (A depends_on ["A"]) because A is not yet in seen_ids at check time.
        for dep in s.get("depends_on", []):
            if dep not in seen_ids:
                raise ValueError(
                    f"step '{sid}' depends_on '{dep}' which is not declared before it"
                )
        seen_ids.add(sid)

    ts = datetime.now(timezone.utc).isoformat()
    c = _conn()
    cur = c.cursor()
    cur.execute(
        "INSERT INTO task_graphs (goal, status, created_at, metadata) VALUES (?, 'pending', ?, ?)",
        (goal.strip(), ts, json.dumps(metadata) if metadata else None),
    )
    graph_id = cur.lastrowid
    for step in steps:
        cur.execute(
            """INSERT INTO task_steps
               (graph_id, step_id, agent, prompt, depends_on, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (
                graph_id,
                step["id"].strip(),
                step["agent"].strip(),
                step["prompt"].strip(),
                json.dumps(step.get("depends_on", [])),
            ),
        )
    c.commit()
    c.close()
    return graph_id


def get_graph(graph_id: int) -> dict | None:
    """Return full graph dict with steps list, or None if not found."""
    c = _conn()
    row = c.execute(
        "SELECT id, goal, status, created_at, started_at, completed_at, metadata "
        "FROM task_graphs WHERE id=?",
        (graph_id,)
    ).fetchone()
    if not row:
        c.close()
        return None
    graph = dict(row)
    graph["metadata"] = json.loads(graph["metadata"]) if graph["metadata"] else {}
    steps = c.execute(
        "SELECT step_id, agent, prompt, depends_on, status, "
        "input_data, output_data, started_at, completed_at, error, attempt, "
        "COALESCE(failure_type, '') as failure_type "
        "FROM task_steps WHERE graph_id=? ORDER BY id",
        (graph_id,)
    ).fetchall()
    c.close()
    graph["steps"] = [_deserialize_step(s) for s in steps]
    return graph


def list_graphs(limit: int = 30) -> list:
    """Return summary list of recent task graphs (no step details)."""
    c = _conn()
    rows = c.execute(
        "SELECT id, goal, status, created_at, started_at, completed_at "
        "FROM task_graphs ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    c.close()
    result = []
    for row in rows:
        g = dict(row)
        # Quick step counts
        cc = _conn()
        counts = cc.execute(
            "SELECT status, COUNT(*) FROM task_steps WHERE graph_id=? GROUP BY status",
            (g["id"],)
        ).fetchall()
        cc.close()
        g["step_counts"] = {r[0]: r[1] for r in counts}
        g["total_steps"] = sum(g["step_counts"].values())
        result.append(g)
    return result


def next_pending_step(graph_id: int) -> dict | None:
    """
    Return the next step to execute: status='pending' with all dependencies completed.
    Returns None if no step is ready (all done, all blocked, or graph finished).
    """
    c = _conn()
    steps = c.execute(
        "SELECT step_id, agent, prompt, depends_on, status, input_data, attempt "
        "FROM task_steps WHERE graph_id=? ORDER BY id",
        (graph_id,)
    ).fetchall()
    c.close()

    completed = {s["step_id"] for s in steps if s["status"] == "completed"}
    for s in steps:
        if s["status"] != "pending":
            continue
        deps = json.loads(s["depends_on"] or "[]")
        if all(d in completed for d in deps):
            return dict(s)
    return None


def mark_step_running(graph_id: int, step_id: str, input_data: dict):
    _assert_step_transition(graph_id, step_id, "running")
    ts = datetime.now(timezone.utc).isoformat()
    c = _conn()
    c.execute(
        "UPDATE task_steps SET status='running', started_at=?, input_data=?, attempt=attempt+1 "
        "WHERE graph_id=? AND step_id=?",
        (ts, json.dumps(input_data), graph_id, step_id)
    )
    c.commit()
    c.close()


def mark_step_completed(graph_id: int, step_id: str, output_data: dict):
    _assert_step_transition(graph_id, step_id, "completed")
    ts = datetime.now(timezone.utc).isoformat()
    c = _conn()
    c.execute(
        "UPDATE task_steps SET status='completed', completed_at=?, output_data=?, error=NULL "
        "WHERE graph_id=? AND step_id=?",
        (ts, json.dumps(output_data), graph_id, step_id)
    )
    c.commit()
    c.close()


def mark_step_failed(graph_id: int, step_id: str, error: str,
                     failure_type: str = "unknown"):
    _assert_step_transition(graph_id, step_id, "failed")
    if failure_type not in FAILURE_TYPES:
        failure_type = "unknown"
    ts = datetime.now(timezone.utc).isoformat()
    c = _conn()
    c.execute(
        "UPDATE task_steps SET status='failed', completed_at=?, error=?, failure_type=? "
        "WHERE graph_id=? AND step_id=?",
        (ts, error[:500], failure_type, graph_id, step_id)
    )
    c.commit()
    c.close()


def update_graph_status(graph_id: int, status: str):
    _assert_graph_transition(graph_id, status)
    ts = datetime.now(timezone.utc).isoformat()
    c = _conn()
    field = "started_at" if status == "running" else "completed_at"
    c.execute(
        f"UPDATE task_graphs SET status=?, {field}=? WHERE id=?",
        (status, ts, graph_id)
    )
    c.commit()
    c.close()


def retry_step(graph_id: int, step_id: str) -> bool:
    """Reset a failed step to pending so it can be retried. Returns False if step not failed."""
    c = _conn()
    row = c.execute(
        "SELECT status FROM task_steps WHERE graph_id=? AND step_id=?",
        (graph_id, step_id)
    ).fetchone()
    if not row or row["status"] != "failed":
        c.close()
        return False
    c.execute(
        "UPDATE task_steps SET status='pending', error=NULL WHERE graph_id=? AND step_id=?",
        (graph_id, step_id)
    )
    # Also re-open the graph if it was failed/completed
    c.execute(
        "UPDATE task_graphs SET status='pending', completed_at=NULL WHERE id=? AND status IN ('failed','completed')",
        (graph_id,)
    )
    c.commit()
    c.close()
    return True


def is_graph_complete(graph_id: int) -> bool:
    c = _conn()
    rows = c.execute(
        "SELECT status FROM task_steps WHERE graph_id=?", (graph_id,)
    ).fetchall()
    c.close()
    return all(r["status"] == "completed" for r in rows)


def has_failed_step(graph_id: int) -> bool:
    c = _conn()
    row = c.execute(
        "SELECT COUNT(*) FROM task_steps WHERE graph_id=? AND status='failed'",
        (graph_id,)
    ).fetchone()
    c.close()
    return row[0] > 0


def _deserialize_step(row) -> dict:
    s = dict(row)
    s["depends_on"]  = json.loads(s["depends_on"] or "[]")
    s["input_data"]  = json.loads(s["input_data"] or "{}")
    s["output_data"] = json.loads(s["output_data"] or "{}")
    return s


# Auto-init on import
init_db()
reset_running()
