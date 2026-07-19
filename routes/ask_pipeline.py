"""routes/ask_pipeline.py — the one chat pipeline: route → invoke → persist.

Both POST /ask and POST /ask/stream (routes/core.py) run a chat request
through this module. Transport (JSON vs SSE) and provider (coordinator vs
Anthropic) are the *only* things the endpoints decide; everything a chat
request must leave behind — thread turn, session row, telemetry, traces,
run log, decision link, contradiction record, COS bookkeeping — happens in
`finish_run`, once, identically for every path.

History: /ask carried all of this inline (~340 lines) and /ask/stream carried
none of it, so chats from the streaming UI were invisible to threads,
telemetry, and the learning loop. The behavioral contract the two endpoints
now share is documented in docs/records/REFACTOR_ANALYSIS_2026-07.md §1.1.

Lifecycle:

    run = begin_run(req, key_id=...)     # ids, thread ctx, doc ctx, tracers
    pre = route_preview(req, run.run_id) # who should act (single call site)
    ...invoke (endpoint-specific)...     # fills run.response/agent_used/...
    extras = finish_run(run)             # ALL persistence
    build_response(run, extras)          # JSON body (or SSE `done` payload)

On invoke failure call `fail_run(run, error)` instead of `finish_run`.
"""

import os
import sqlite3
import time
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.contract import Result
from core.logger import log_response
from core.run_log import RunLog
from infrastructure.db import path as _dbpath
import cognition.run_tracer as run_tracer

from .deps import (
    _cos, session_history, _SESSIONS_DB, _CONTRADICTIONS_DB,
    AskRequest, AskResponse,
)

# ── Append-only transparent run log (core/run_log.py) ────────────────────────
# Lazy singleton so the table is created once per process, not per request.
_run_log: RunLog | None = None


def _get_run_log() -> RunLog | None:
    global _run_log
    if _run_log is None:
        try:
            _run_log = RunLog()
        except Exception:
            return None
    return _run_log


# ── Routing telemetry ────────────────────────────────────────────────────────

TELEMETRY_DB = _dbpath("telemetry")


def _init_telemetry():
    os.makedirs(os.path.dirname(TELEMETRY_DB), exist_ok=True)
    conn = sqlite3.connect(TELEMETRY_DB, timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS routing_telemetry (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ts           TEXT NOT NULL,
            query_prefix TEXT NOT NULL,
            agent        TEXT NOT NULL,
            signal_conf  REAL,
            complexity   TEXT,
            duration_ms  INTEGER,
            correct      INTEGER        -- NULL=unlabeled, 1=correct, 0=wrong
        )
    """)
    conn.commit()
    conn.close()


_init_telemetry()


def _log_telemetry(query: str, agent: str, signal_conf: float, complexity: str, duration_ms: int):
    try:
        conn = sqlite3.connect(TELEMETRY_DB, timeout=3)
        conn.execute(
            "INSERT INTO routing_telemetry (ts, query_prefix, agent, signal_conf, complexity, duration_ms) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), query[:120], agent,
             round(signal_conf, 3), complexity, duration_ms),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Traces table — schema owned here, ensured once (not per request) ─────────

_traces_ready = False


def _ensure_traces() -> None:
    global _traces_ready
    if _traces_ready:
        return
    con = sqlite3.connect(_dbpath("traces"), timeout=5)
    con.execute("""CREATE TABLE IF NOT EXISTS traces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, agent TEXT, user_message TEXT,
        routing_reason TEXT, duration_ms INTEGER
    )""")
    for _col, _typ in [("signal_domain", "TEXT"), ("signal_shape", "TEXT"), ("signal_conf", "REAL")]:
        try:
            con.execute(f"ALTER TABLE traces ADD COLUMN {_col} {_typ}")
        except Exception:
            pass
    con.commit()
    con.close()
    _traces_ready = True


# ── Thread helpers ───────────────────────────────────────────────────────────

def _load_thread_context(thread_id: str, n: int = 4) -> list:
    """Return last n turns as message dicts (oldest first) for LangGraph."""
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        rows = conn.execute(
            "SELECT user_msg, agent_msg FROM turns "
            "WHERE thread_id=? ORDER BY id DESC LIMIT ?",
            (thread_id, n),
        ).fetchall()
        conn.close()
        msgs = []
        for user_msg, agent_msg in reversed(rows):
            msgs.append({"role": "user",      "content": user_msg})
            msgs.append({"role": "assistant",  "content": agent_msg})
        return msgs
    except Exception:
        return []


def _save_turn(thread_id: str, user_msg: str, agent_msg: str, agent: str) -> None:
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO threads (id, title, created_at, updated_at, turn_count) "
            "VALUES (?,?,?,?,0)",
            (thread_id, user_msg[:60], now, now),
        )
        conn.execute(
            "UPDATE threads SET updated_at=?, turn_count=turn_count+1 WHERE id=?",
            (now, thread_id),
        )
        conn.execute(
            "INSERT INTO turns (thread_id, ts, user_msg, agent_msg, agent) VALUES (?,?,?,?,?)",
            (thread_id, now, user_msg, agent_msg, agent),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[threading] save_turn error: {e}")


# ── Document context ─────────────────────────────────────────────────────────

def _get_document_context(query: str, source_files: list[str], top_k: int = 5) -> str:
    """Return relevant document chunks as a context block for injection into the prompt."""
    if not source_files:
        return ""
    try:
        import numpy as np
        from memory_core.db import DB_PATH, get_embedding
        q_arr = np.array(get_embedding(query), dtype=np.float32)
        norm  = np.linalg.norm(q_arr)
        if norm > 0:
            q_arr /= norm

        conn = sqlite3.connect(DB_PATH, timeout=5)
        rows = conn.execute(
            "SELECT content, embedding, metadata FROM memories WHERE mem_type = 'document'"
        ).fetchall()
        conn.close()

        scored: list[tuple[float, str, str]] = []
        for content, emb_blob, meta_raw in rows:
            try:
                meta = json.loads(meta_raw) if meta_raw else {}
            except Exception:
                meta = {}
            if meta.get("source_file") not in source_files:
                continue
            score = 0.0
            if emb_blob:
                emb = np.frombuffer(emb_blob, dtype=np.float32)
                score = float(np.dot(q_arr, emb))
            scored.append((score, content, meta.get("source_file", "unknown")))

        scored.sort(reverse=True)
        top = scored[:top_k]
        if not top:
            return ""

        by_file: dict[str, list[str]] = {}
        for _, content, sf in top:
            by_file.setdefault(sf, []).append(content)

        lines = ["[Document context — answer the question using the following material]"]
        for sf, chunks in by_file.items():
            lines.append(f"\nSource: {sf}")
            lines.extend(chunks)
        return "\n".join(lines)
    except Exception:
        return ""


# ── Agent system prompts (Anthropic paths) ───────────────────────────────────

_AGENT_PROMPTS: dict[str, str] = {}


def _get_agent_system_prompt(agent: str, query: str | None = None) -> str:
    """Return the formatted system prompt for a given agent.

    `query` is forwarded to get_profile_context so non-English input drops the
    private profile block on the Anthropic path too (issue #6)."""
    if not _AGENT_PROMPTS:
        try:
            from agents.it_networking     import IT_SYSTEM_PROMPT
            from agents.python_dev        import PYTHON_SYSTEM_PROMPT
            from agents.dotnet_dev        import DOTNET_SYSTEM_PROMPT
            from agents.ai_ml             import AI_ML_SYSTEM_PROMPT
            from agents.knowledge_learning import KNOWLEDGE_SYSTEM_PROMPT
            from agents.terse             import TERSE_SYSTEM_PROMPT
            from agents.web_dev           import WEB_DEV_SYSTEM_PROMPT
            from agents.devops            import DEVOPS_SYSTEM_PROMPT
            from agents.data_analyst      import DATA_ANALYST_SYSTEM_PROMPT
            from agents.writer            import WRITER_SYSTEM_PROMPT
            _AGENT_PROMPTS.update({
                "it_networking":     IT_SYSTEM_PROMPT,
                "python_dev":        PYTHON_SYSTEM_PROMPT,
                "dotnet_dev":        DOTNET_SYSTEM_PROMPT,
                "ai_ml":             AI_ML_SYSTEM_PROMPT,
                "knowledge_learning": KNOWLEDGE_SYSTEM_PROMPT,
                "terse":             TERSE_SYSTEM_PROMPT,
                "web_dev":           WEB_DEV_SYSTEM_PROMPT,
                "devops":            DEVOPS_SYSTEM_PROMPT,
                "data_analyst":      DATA_ANALYST_SYSTEM_PROMPT,
                "writer":            WRITER_SYSTEM_PROMPT,
            })
        except Exception:
            pass

    template = _AGENT_PROMPTS.get(agent, "You are Amagra, an elite AI assistant.")
    try:
        # Was `from user_profile import ...` — a module that doesn't exist, so
        # this always fell back to the raw template (with a literal
        # `{user_profile}` placeholder left in the prompt).
        from core.user_profile import get_profile_context
        return template.format(user_profile=get_profile_context(query))
    except Exception:
        return template


# ── Coordinator state ────────────────────────────────────────────────────────

def base_state(task: str, run_id: str, *, messages: list | None = None,
               force_agent: str = "", force_reflect_level: str = "") -> dict:
    """The AgentState dict every coordinator.invoke call starts from.

    Was hand-built in four places (/ask, /ask/stream fallback, /runs/replay,
    /ask/replay), each with its own drift."""
    return {
        "messages":               messages if messages is not None
                                  else [{"role": "user", "content": task}],
        "active_agent":           "",
        "task":                   task,
        "result":                 "",
        "next_agent":             "",
        "memory":                 {},
        "force_agent":            force_agent or "",
        "brain_decision":         {},
        "reflect":                False,
        "reflect_type":           "general",
        "reflect_level":          "none",
        "contradiction_detected": False,
        "force_reflect_level":    force_reflect_level or "",
        "run_id":                 run_id,
    }


# ── Routing preview (Anthropic + streaming preamble) ─────────────────────────

@dataclass
class RoutePreview:
    agent:         str
    system_prompt: str
    complexity:    str
    model_tier:    str
    meta:          dict   # decision fields for events / logs / responses


def route_preview(req: AskRequest, run_id: str = "") -> RoutePreview:
    """One call site for `core_brain.think` outside the coordinator.

    Used where a routing decision is needed *before* (or instead of) a
    coordinator run: the SSE routing preamble and the Anthropic provider path.
    The coordinator still routes internally on the local path — this does not
    double-route that case."""
    try:
        from orchestration.core_brain import think
        state = base_state(req.message, run_id,
                           force_agent=req.force_agent or "",
                           force_reflect_level=req.force_reflect_level or "")
        state["model_tier"] = "fast"
        decision   = think(req.message, state)
        agent      = (decision.agent_strategy[0] if decision.agent_strategy else None) or "knowledge_learning"
        complexity = decision.complexity
        meta = {
            "signal_domain":    decision.signal_domain,
            "signal_shape":     decision.signal_shape,
            "signal_verbosity": getattr(decision, "signal_verbosity", "normal"),
            "signal_conf":      round(decision.signal_conf, 2),
            "action":           getattr(decision, "action", "generate"),
            "complexity":       decision.complexity,
            "confidence":       round(getattr(decision, "confidence", 0.67), 2),
        }
    except Exception:
        agent, complexity, meta = "knowledge_learning", "simple", {}
    return RoutePreview(
        agent=agent,
        system_prompt=_get_agent_system_prompt(agent, req.message),
        complexity=complexity,
        model_tier={"compound": "reasoning", "moderate": "standard"}.get(complexity, "fast"),
        meta=meta,
    )


# ── The run object ───────────────────────────────────────────────────────────

@dataclass
class AskRun:
    req:        AskRequest
    run_id:     str
    thread_id:  str
    ctx_msgs:   list            # prior thread turns, oldest first
    task_msg:   str             # doc context + message
    started:    float
    weights_before: dict = field(default_factory=dict)
    # set by the endpoint after invoke:
    response:   str  = ""
    agent_used: str  = "unknown"
    result:     dict = field(default_factory=dict)   # coordinator output (or synthetic)
    bd:         dict = field(default_factory=dict)   # brain_decision meta
    model_used: str  = ""
    # internal:
    _owner_token: object     = None
    _finished:    bool       = False
    _duration_ms: int | None = None

    @property
    def provider_messages(self) -> list:
        """Thread context + current (doc-augmented) message, for provider paths."""
        return [*self.ctx_msgs, {"role": "user", "content": self.task_msg}]

    @property
    def duration_ms(self) -> int:
        """Wall time from begin_run to first access (i.e. end of invoke) —
        frozen there so persistence and the response report the same number."""
        if self._duration_ms is None:
            self._duration_ms = int((time.time() - self.started) * 1000)
        return self._duration_ms


def begin_run(req: AskRequest, key_id: int | None = None) -> AskRun:
    """Everything that happens before the model is invoked, for every path."""
    started = time.time()

    weights_before: dict = {}
    try:
        from decision.weights import load as _load_weights
        weights_before = _load_weights()
    except Exception:
        pass

    run_id = run_tracer.start(req.message)

    if _cos:
        try:
            _cos.begin_request(req.message, run_id=run_id, action="unknown")
        except Exception:
            pass

    try:
        import cognition.context_snapshot as _cx
        from orchestration.query_normalizer import normalize as _qnorm
        _sig = _qnorm(req.message, "")
        _cx.begin(run_id, req.message,
                  normalized_query=f"{_sig.domain}/{_sig.answer_shape}/{_sig.verbosity}")
    except Exception:
        pass

    # Tenant scoping — propagate key_id so memory search/save calls in this
    # request are automatically filtered to the calling tenant (S2).
    owner_token = None
    try:
        from memory_core.db import _current_owner_key_id as _owner_cv
        owner_token = _owner_cv.set(key_id)
    except Exception:
        pass

    thread_id = req.thread_id or str(uuid.uuid4())
    ctx_msgs  = _load_thread_context(thread_id, n=4)

    doc_ctx  = _get_document_context(req.message, req.context_files or [])
    task_msg = f"{doc_ctx}\n\n{req.message}" if doc_ctx else req.message

    return AskRun(
        req=req, run_id=run_id, thread_id=thread_id,
        ctx_msgs=ctx_msgs, task_msg=task_msg,
        started=started, weights_before=weights_before,
        _owner_token=owner_token,
    )


def _reset_tenant(run: AskRun) -> None:
    """Clear the tenant ContextVar so it doesn't leak into unrelated work.

    Token reset only works in the context that set it; an SSE generator runs
    in a different one, so fall back to overwriting with None."""
    try:
        from memory_core.db import _current_owner_key_id as _owner_cv
        if run._owner_token is not None:
            try:
                _owner_cv.reset(run._owner_token)
            except ValueError:
                _owner_cv.set(None)
            run._owner_token = None
    except Exception:
        pass


def fail_run(run: AskRun, error: str) -> None:
    """Invoke failed: mark the trace, release tenant scoping."""
    try:
        run_tracer.mark_failed(run.run_id, error)
    except Exception:
        pass
    _reset_tenant(run)


def finish_run(run: AskRun) -> dict:
    """ALL post-invoke persistence, identical for every endpoint/provider.

    Requires run.response / run.agent_used / run.bd / run.result to be set.
    Returns the extras `build_response` needs (session id, memories, weight
    delta, contradiction flag). Idempotent: a second call is a no-op, so a
    streaming endpoint can call it defensively."""
    if run._finished:
        return {}
    run._finished = True

    req, bd     = run.req, run.bd
    duration_ms = run.duration_ms
    agent_used  = run.agent_used
    response    = run.response

    _save_turn(run.thread_id, req.message, response, agent_used)

    _log_telemetry(
        req.message, agent_used,
        float(bd.get("signal_conf", 0.0)),
        bd.get("complexity", "simple"),
        duration_ms,
    )
    log_response(agent_used, req.message)

    try:
        _ensure_traces()
        _conn = sqlite3.connect(_dbpath("traces"))
        _conn.execute(
            "INSERT INTO traces (timestamp, agent, user_message, routing_reason, duration_ms, signal_domain, signal_shape, signal_conf) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), agent_used, req.message[:200],
             f"routed to {agent_used}", duration_ms,
             bd.get("signal_domain", "general"), bd.get("signal_shape", "explanation"),
             round(float(bd.get("signal_conf", 0.0)), 3))
        )
        _conn.commit()
        _conn.close()
    except Exception:
        pass

    # Transparent run log — one append-only row per run (core/run_log.py).
    try:
        _rl = _get_run_log()
        if _rl is not None:
            _rl.append(
                task=req.message,
                ext_id=run.run_id,
                result=Result(output=response, meta={
                    "agent":        agent_used,
                    "duration_ms":  duration_ms,
                    "complexity":   bd.get("complexity", "simple"),
                    "signal_domain": bd.get("signal_domain", "general"),
                    "signal_shape": bd.get("signal_shape", "explanation"),
                    "signal_conf":  round(float(bd.get("signal_conf", 0.0)), 3),
                }),
            )
    except Exception:
        pass

    confidence = bd.get("confidence", 0.67)
    session_history.append({
        "ts":          datetime.now().strftime('%H:%M:%S'),
        "user":        req.message,
        "agent":       agent_used,
        "response":    response,
        "duration_ms": duration_ms,
    })
    session_id = -1
    try:
        _sc = sqlite3.connect(_SESSIONS_DB)
        _cur = _sc.execute(
            "INSERT INTO sessions (timestamp, user_input, response, agent, duration_ms, confidence) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), req.message[:500],
             response[:2000], agent_used, duration_ms, confidence),
        )
        session_id = _cur.lastrowid
        _sc.commit()
        _sc.close()
    except Exception:
        pass

    # Auto-retrain the learned router every N real sessions (#15) — non-blocking.
    if session_id > 0:
        try:
            from orchestration.auto_retrain import note_session
            note_session()
        except Exception:
            pass

    # Link brain decision ↔ session. Registry path — the old inline version
    # hardcoded logs/decisions.db and silently broke under AMAGRA_DATA_DIR.
    decision_id = -1
    if session_id > 0:
        try:
            _dc = sqlite3.connect(_dbpath("decisions"))
            _dec_row = _dc.execute(
                "SELECT id FROM brain_decisions WHERE run_id=? LIMIT 1",
                (run.run_id,),
            ).fetchone()
            if _dec_row:
                decision_id = _dec_row[0]
                _dc.execute("UPDATE brain_decisions SET session_id=? WHERE id=?",
                            (session_id, decision_id))
                _dc.commit()
                _sc2 = sqlite3.connect(_SESSIONS_DB)
                _sc2.execute("UPDATE sessions SET decision_id=? WHERE id=?",
                             (decision_id, session_id))
                _sc2.commit()
                _sc2.close()
            _dc.close()
        except Exception:
            pass

    try:
        run_tracer.finish(
            run.run_id,
            agent=agent_used,
            decision_id=int(decision_id) if decision_id else -1,
            session_id=session_id,
            duration_ms=duration_ms,
        )
    except Exception:
        pass

    memories_used = []
    try:
        import memory_core.db as _mdb
        memories_used = _mdb.get_last_accessed_content(req.message, n=4)
    except Exception:
        pass

    weight_before = weight_after = weight_delta = 0.0
    try:
        from decision.weights import load as _load_weights
        weights_after = _load_weights()
        weight_before = round(run.weights_before.get(agent_used, 1.0), 4)
        weight_after  = round(weights_after.get(agent_used, 1.0), 4)
        weight_delta  = round(weight_after - weight_before, 4)
    except Exception:
        pass

    contradiction = bool(run.result.get("contradiction_detected", False))
    if contradiction:
        try:
            _cc = sqlite3.connect(_CONTRADICTIONS_DB)
            _cc.execute(
                "INSERT INTO contradictions (timestamp, agent, query, response_snip, reflect_level) "
                "VALUES (?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), agent_used,
                 req.message[:200], response[:120],
                 run.result.get("reflect_level", "none")),
            )
            _cc.commit()
            _cc.close()
        except Exception:
            pass

    try:
        import cognition.context_snapshot as _cx
        _cx.finalize(run.run_id, response, session_id=session_id)
    except Exception:
        pass

    if _cos:
        try:
            _cos.request.action = bd.get("action", "unknown")
            _cos.end_request(
                agent            = agent_used,
                outcome          = "completed",
                response_snippet = response[:300],
                quality          = run.result.get("response_quality"),
                kept             = run.result.get("gram_winner")
                                   or run.result.get("response_kept", ""),
            )
        except Exception:
            pass

    _reset_tenant(run)

    return {
        "session_id":     session_id,
        "memories_used":  memories_used,
        "weight_before":  weight_before,
        "weight_after":   weight_after,
        "weight_delta":   weight_delta,
        "contradiction":  contradiction,
    }


def build_response(run: AskRun, extras: dict) -> AskResponse:
    """The JSON body for /ask; also the source of the SSE `done` payload."""
    bd = run.bd
    return AskResponse(
        response=run.response,
        agent_used=run.agent_used,
        routing_reason=f"Routed to {run.agent_used}",
        duration_ms=run.duration_ms,
        timestamp=datetime.now().isoformat(),
        signal_domain=bd.get("signal_domain", "general"),
        signal_shape=bd.get("signal_shape", "explanation"),
        signal_verbosity=bd.get("signal_verbosity", "normal"),
        signal_conf=round(float(bd.get("signal_conf", 0.0)), 2),
        action=bd.get("action", "unknown"),
        complexity=bd.get("complexity", "simple"),
        model_tier={"compound": "reasoning", "moderate": "standard"}.get(
            bd.get("complexity", "simple"), "fast"
        ),
        reflect_level=run.result.get("reflect_level", "none"),
        confidence=round(float(bd.get("confidence", 0.67)), 2),
        regret=round(float(bd.get("regret", 0.0)), 3),
        contradiction_detected=extras.get("contradiction", False),
        memories_used=extras.get("memories_used", []),
        gram_winner=run.result.get("gram_winner", ""),
        gram_log=run.result.get("gram_log", ""),
        weight_before=extras.get("weight_before", 0.0),
        weight_after=extras.get("weight_after", 0.0),
        weight_delta=extras.get("weight_delta", 0.0),
        pipeline_agents=run.result.get("pipeline_agents", []),
        pipeline_responses=run.result.get("pipeline_responses", []),
        context_id=run.run_id,
        thread_id=run.thread_id,
        model_used=run.model_used,
    )
