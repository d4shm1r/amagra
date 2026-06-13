"""
Run-level trace logger for the LLM execution pipeline.

Captures the complete decision path of a single /ask invocation in real time:
  prompt → routing → generate → critic → [reject → retry] → finish

Unlike trace_builder.py (retroactive, batch), this module writes live during
execution so every step is recorded as it happens.

Writes to logs/runs.db. Consumed by /runs API endpoints and the debugger UI.
"""

import json, os, sqlite3, threading, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

_BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNS_DB = os.path.join(_BASE, "logs", "runs.db")
_LOCK    = threading.Lock()
_ACTIVE: dict[str, "_RunCtx"] = {}   # run_id → live context

_CRITIC_GATE_THRESHOLD = 0.70


@dataclass
class _RunCtx:
    run_id:  str
    t_start: float
    query:   str
    steps:   list = field(default_factory=list)
    # routing
    brain_agent:   str   = ""
    router_agent:  str   = ""
    conflict:      bool  = False
    confidence:    float = 0.67
    regret:        float = 0.0
    complexity:    str   = "simple"
    reflect_level: str   = "none"
    # critic gate
    critic_initial:   Optional[float] = None
    critic_retry:     Optional[float] = None
    accepted_first:   Optional[bool]  = None


# ── DB setup ──────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_RUNS_DB), exist_ok=True)
    c = sqlite3.connect(_RUNS_DB, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _init() -> None:
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id           TEXT PRIMARY KEY,
            timestamp        TEXT NOT NULL,
            query            TEXT,
            status           TEXT DEFAULT 'running',
            agent            TEXT,
            decision_id      INTEGER,
            session_id       INTEGER,
            duration_ms      INTEGER,
            brain_agent      TEXT,
            router_agent     TEXT,
            conflict         INTEGER DEFAULT 0,
            confidence       REAL    DEFAULT 0.67,
            regret           REAL    DEFAULT 0.0,
            complexity       TEXT,
            reflect_level    TEXT,
            critic_initial   REAL,
            critic_threshold REAL,
            critic_retry     REAL,
            accepted_first   INTEGER,
            retry_improved   INTEGER,
            steps            TEXT,
            root_cause       TEXT,
            root_cause_label TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_ts ON runs(timestamp)")
    c.commit()
    c.close()


_init()


# ── Public API ────────────────────────────────────────────────

def start(query: str) -> str:
    """Open a new run trace. Returns run_id to thread through the pipeline."""
    run_id = str(uuid.uuid4())
    ctx = _RunCtx(run_id=run_id, t_start=time.time(), query=query)
    _add_step(ctx, "prompt", {"query": query[:200]})
    with _LOCK:
        _ACTIVE[run_id] = ctx
    c = _conn()
    c.execute(
        "INSERT INTO runs (run_id, timestamp, query, status) VALUES (?,?,?,?)",
        (run_id, datetime.now(timezone.utc).isoformat(), query[:500], "running"),
    )
    c.commit()
    c.close()
    return run_id


def record_routing(run_id: str, *, brain_agent: str, router_agent: str,
                   conflict: bool, confidence: float, regret: float,
                   complexity: str, reflect_level: str) -> None:
    ctx = _get(run_id)
    if not ctx:
        return
    ctx.brain_agent   = brain_agent
    ctx.router_agent  = router_agent
    ctx.conflict      = conflict
    ctx.confidence    = confidence
    ctx.regret        = regret
    ctx.complexity    = complexity
    ctx.reflect_level = reflect_level
    _add_step(ctx, "routing", {
        "agent":      brain_agent,
        "router":     router_agent,
        "conflict":   conflict,
        "confidence": round(confidence, 3),
    })


def record_generate(run_id: str, agent: str) -> None:
    ctx = _get(run_id)
    if ctx:
        _add_step(ctx, "generate", {"agent": agent})


def record_critic(run_id: str, *, score_initial: float,
                  accepted_on_first: bool,
                  score_retry: Optional[float] = None) -> None:
    ctx = _get(run_id)
    if not ctx:
        return
    ctx.critic_initial = score_initial
    ctx.accepted_first = accepted_on_first
    if accepted_on_first:
        _add_step(ctx, "critic_accept", {
            "score":     round(score_initial, 3),
            "threshold": _CRITIC_GATE_THRESHOLD,
        })
    else:
        _add_step(ctx, "critic_reject", {
            "score":     round(score_initial, 3),
            "threshold": _CRITIC_GATE_THRESHOLD,
        })
        ctx.critic_retry = score_retry
        if score_retry is not None:
            improved = score_retry >= score_initial
            _add_step(
                ctx,
                "retry_accept" if improved else "retry_no_improvement",
                {"score": round(score_retry, 3)},
            )


def finish(run_id: str, *, agent: str, decision_id: int = -1,
           session_id: int = -1, duration_ms: int = 0) -> None:
    """Close the trace, derive root cause, and persist to DB."""
    ctx = _get(run_id)
    if not ctx:
        return

    root_cause, root_cause_label = _derive_root_cause(ctx)
    status = _derive_status(ctx, root_cause)
    _add_step(ctx, "finish", {"agent": agent, "status": status, "duration_ms": duration_ms})

    retry_improved: Optional[int] = None
    if ctx.critic_initial is not None and ctx.critic_retry is not None:
        retry_improved = 1 if ctx.critic_retry > ctx.critic_initial else 0

    c = _conn()
    c.execute("""
        UPDATE runs SET
            status=?, agent=?, decision_id=?, session_id=?,
            duration_ms=?,
            brain_agent=?, router_agent=?, conflict=?,
            confidence=?, regret=?, complexity=?, reflect_level=?,
            critic_initial=?, critic_threshold=?, critic_retry=?,
            accepted_first=?, retry_improved=?,
            steps=?, root_cause=?, root_cause_label=?
        WHERE run_id=?
    """, (
        status, agent,
        decision_id if decision_id > 0 else None,
        session_id  if session_id  > 0 else None,
        duration_ms,
        ctx.brain_agent, ctx.router_agent, int(ctx.conflict),
        round(ctx.confidence, 4), round(ctx.regret, 4),
        ctx.complexity, ctx.reflect_level,
        ctx.critic_initial, _CRITIC_GATE_THRESHOLD, ctx.critic_retry,
        (1 if ctx.accepted_first else 0) if ctx.accepted_first is not None else None,
        retry_improved,
        json.dumps(ctx.steps),
        root_cause, root_cause_label,
        run_id,
    ))
    c.commit()
    c.close()

    with _LOCK:
        _ACTIVE.pop(run_id, None)


def mark_failed(run_id: str, error: str = "") -> None:
    """Mark a run as failed due to an unhandled exception."""
    ctx = _get(run_id)
    if ctx:
        _add_step(ctx, "error", {"error": error[:200]})
        c = _conn()
        c.execute(
            "UPDATE runs SET status='fail', steps=?, root_cause='exception', "
            "root_cause_label=? WHERE run_id=?",
            (json.dumps(ctx.steps), error[:300], run_id),
        )
        c.commit()
        c.close()
        with _LOCK:
            _ACTIVE.pop(run_id, None)


# ── Read API ──────────────────────────────────────────────────

def similar_by_cause(root_cause: str, limit: int = 20,
                     exclude_run_id: str = "") -> list:
    """Return other runs sharing the same root cause code."""
    if not root_cause or root_cause == "none":
        return []
    try:
        c = _conn()
        rows = c.execute("""
            SELECT run_id, timestamp, query, status, agent,
                   duration_ms, critic_initial, accepted_first
            FROM runs
            WHERE root_cause = ? AND run_id != ?
            ORDER BY rowid DESC LIMIT ?
        """, (root_cause, exclude_run_id, limit)).fetchall()
        c.close()
        return [
            {
                "run_id":         r[0],
                "timestamp":      r[1],
                "query":          (r[2] or "")[:120],
                "status":         r[3],
                "agent":          r[4],
                "duration_ms":    r[5],
                "critic_initial": r[6],
                "accepted_first": r[7],
            }
            for r in rows
        ]
    except Exception:
        return []


def count_by_cause(root_cause: str) -> int:
    """Count how many runs share a root cause (for UI badge)."""
    if not root_cause or root_cause == "none":
        return 0
    try:
        c = _conn()
        n = c.execute(
            "SELECT COUNT(*) FROM runs WHERE root_cause=?", (root_cause,)
        ).fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def recent(limit: int = 50) -> list:
    """Return recent runs for the dashboard list view."""
    try:
        c = _conn()
        rows = c.execute("""
            SELECT run_id, timestamp, query, status, agent,
                   duration_ms, confidence, regret, conflict,
                   root_cause, root_cause_label,
                   critic_initial, accepted_first, reflect_level
            FROM runs
            ORDER BY rowid DESC LIMIT ?
        """, (limit,)).fetchall()
        c.close()
        return [
            {
                "run_id":           r[0],
                "timestamp":        r[1],
                "query":            (r[2] or "")[:120],
                "status":           r[3],
                "agent":            r[4],
                "duration_ms":      r[5],
                "confidence":       r[6],
                "regret":           r[7],
                "conflict":         bool(r[8]),
                "root_cause":       r[9],
                "root_cause_label": r[10],
                "critic_initial":   r[11],
                "accepted_first":   r[12],
                "reflect_level":    r[13],
            }
            for r in rows
        ]
    except Exception:
        return []


def get_run(run_id: str) -> Optional[dict]:
    """Return a single run with full steps timeline for the trace viewer."""
    try:
        c = _conn()
        row = c.execute("""
            SELECT run_id, timestamp, query, status, agent,
                   decision_id, session_id, duration_ms,
                   brain_agent, router_agent, conflict,
                   confidence, regret, complexity, reflect_level,
                   critic_initial, critic_threshold, critic_retry,
                   accepted_first, retry_improved,
                   steps, root_cause, root_cause_label
            FROM runs WHERE run_id=?
        """, (run_id,)).fetchone()
        c.close()
        if not row:
            return None
        return {
            "run_id":           row[0],
            "timestamp":        row[1],
            "query":            row[2],
            "status":           row[3],
            "agent":            row[4],
            "decision_id":      row[5],
            "session_id":       row[6],
            "duration_ms":      row[7],
            "brain_agent":      row[8],
            "router_agent":     row[9],
            "conflict":         bool(row[10]),
            "confidence":       row[11],
            "regret":           row[12],
            "complexity":       row[13],
            "reflect_level":    row[14],
            "critic_initial":   row[15],
            "critic_threshold": row[16],
            "critic_retry":     row[17],
            "accepted_first":   bool(row[18]) if row[18] is not None else None,
            "retry_improved":   bool(row[19]) if row[19] is not None else None,
            "steps":            json.loads(row[20] or "[]"),
            "root_cause":       row[21],
            "root_cause_label": row[22],
        }
    except Exception:
        return None


# ── Internals ─────────────────────────────────────────────────

def _get(run_id: str) -> Optional[_RunCtx]:
    return _ACTIVE.get(run_id)


def _add_step(ctx: _RunCtx, name: str, data: dict) -> None:
    t_offset = int((time.time() - ctx.t_start) * 1000)
    ctx.steps.append({"t": t_offset, "name": name, "data": data})


def _derive_root_cause(ctx: _RunCtx) -> tuple[str, str]:
    """
    Rule-based root cause derivation — no LLM call needed.
    Returns (code, human-readable label).
    """
    if ctx.critic_initial is not None and ctx.critic_initial < _CRITIC_GATE_THRESHOLD:
        if ctx.critic_retry is not None and ctx.critic_retry < ctx.critic_initial:
            return (
                "critic_misclassification",
                f"Critic rejected answer (score {ctx.critic_initial:.2f}); "
                f"retry scored lower ({ctx.critic_retry:.2f}) — possible miscalibration",
            )
        if not ctx.accepted_first:
            return (
                "critic_threshold",
                f"Initial response scored {ctx.critic_initial:.2f} < "
                f"threshold {_CRITIC_GATE_THRESHOLD} — retry accepted",
            )
    if ctx.confidence < 0.40:
        return (
            "low_confidence",
            f"Routing confidence {ctx.confidence:.2f} below 0.40 — forced full reflection",
        )
    if ctx.regret > 0.30:
        return (
            "routing_regret",
            f"Regret signal {ctx.regret:.2f} — suboptimal agent may have been selected",
        )
    if ctx.conflict:
        return (
            "routing_conflict",
            "Brain and router disagreed — brain overrode router's suggestion",
        )
    return "none", ""


def _derive_status(ctx: _RunCtx, root_cause: str) -> str:
    if root_cause == "critic_misclassification":
        return "fail"
    if root_cause in ("critic_threshold", "low_confidence",
                      "routing_regret", "routing_conflict"):
        return "partial"
    return "pass"
