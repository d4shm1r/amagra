import os
import time
import sqlite3
import uuid
import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from orchestration.coordinator import coordinator
from core.logger import log_response, read_log
import cognition.run_tracer as run_tracer
from infrastructure.db import path as _dbpath

from .deps import (
    _cos, session_history, _SESSIONS_DB, _CONTRADICTIONS_DB,
    AskRequest, AskResponse,
)

router = APIRouter()

_TELEMETRY_DB = _dbpath("telemetry")

def _init_telemetry():
    os.makedirs(os.path.dirname(_TELEMETRY_DB), exist_ok=True)
    conn = sqlite3.connect(_TELEMETRY_DB, timeout=5)
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
        conn = sqlite3.connect(_TELEMETRY_DB, timeout=3)
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

# ── Thread helpers ────────────────────────────────────────────

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


@router.get("/")
def root():
    _has_claude = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    return {
        "status": "online",
        "agents": 10,
        "model":  "phi4-mini + claude-sonnet-4-6" if _has_claude else "phi4-mini",
    }


@router.get("/health")
def health():
    _api_key_set   = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    _brain_backend = os.environ.get("BRAIN_PROVIDER", "ollama")
    _enhance_model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
    result: dict = {
        "status":    "online",
        "timestamp": datetime.now().isoformat(),
        "model":     "phi4-mini",
        "agents":    10,
        "ollama":    "unknown",
        "memory":    {},
        "uci":       None,
        "intelligence": {
            "brain_provider":    _brain_backend,
            "enhance_model":     _enhance_model if _api_key_set else None,
            "claude_available":  _api_key_set,
            "streaming":         _api_key_set,
        },
    }

    # Ollama connectivity
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        result["ollama"] = "online"
    except Exception:
        result["ollama"] = "offline"
        result["status"] = "degraded"

    # Memory backend
    try:
        from memory_core.backend import get_backend
        info = get_backend().backend_info()
        result["memory"] = {"backend": info.get("type"), "total": info.get("total")}
    except Exception:
        pass

    # Live UCI (cached, won't block)
    try:
        from infrastructure.metrics_engine import compute_uci
        result["uci"] = compute_uci()
    except Exception:
        pass

    return result


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request):
    start = time.time()

    _weights_snap_before: dict = {}
    try:
        from decision.weights import load as _load_weights
        _weights_snap_before = _load_weights()
    except Exception:
        pass

    _run_id = run_tracer.start(req.message)

    if _cos:
        try:
            _cos.begin_request(req.message, run_id=_run_id, action="unknown")
        except Exception:
            pass

    try:
        import cognition.context_snapshot as _cx
        from orchestration.query_normalizer import normalize as _qnorm
        _sig = _qnorm(req.message, "")
        _cx.begin(_run_id, req.message,
                  normalized_query=f"{_sig.domain}/{_sig.answer_shape}/{_sig.verbosity}")
    except Exception:
        pass

    # ── Tenant scoping — propagate key_id so all memory search/save calls
    #    in this request are automatically filtered to the calling tenant (S2).
    try:
        from memory_core.db import _current_owner_key_id as _owner_cv
        _key_id      = getattr(request.state, "key_id", None)
        _owner_token = _owner_cv.set(_key_id)
    except Exception:
        _owner_token = None

    # ── Conversation threading ────────────────────────────────────
    _thread_id = req.thread_id or str(uuid.uuid4())
    _ctx_msgs  = _load_thread_context(_thread_id, n=4)

    _doc_ctx = _get_document_context(req.message, req.context_files or [])
    _task_msg = f"{_doc_ctx}\n\n{req.message}" if _doc_ctx else req.message

    _invoke_input = {
        "messages":               [*_ctx_msgs, {"role": "user", "content": _task_msg}],
        "active_agent":           "",
        "task":                   _task_msg,
        "result":                 "",
        "next_agent":             "",
        "memory":                 {},
        "force_agent":            req.force_agent or "",
        "brain_decision":         {},
        "reflect":                False,
        "reflect_type":           "general",
        "reflect_level":          "none",
        "contradiction_detected": False,
        "force_reflect_level":    req.force_reflect_level or "",
        "run_id":                 _run_id,
    }

    # ── Anthropic provider path — when caller requests it explicitly or
    #    PREFER_ANTHROPIC=1 is set and an API key is available.
    _anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    _use_anthropic = (
        _anthropic_key
        and (req.provider == "anthropic" or os.environ.get("PREFER_ANTHROPIC", "0") == "1")
    )
    if _use_anthropic:
        try:
            from orchestration.core_brain import think as _think
            from models.state import AgentState as _AgentState
            _dummy: _AgentState = {  # type: ignore[misc]
                "messages": [{"role": "user", "content": req.message}],
                "active_agent": "", "task": req.message, "result": "",
                "next_agent": "", "memory": {}, "force_agent": req.force_agent or "",
                "brain_decision": {}, "reflect": False, "reflect_type": "general",
                "reflect_level": "none", "contradiction_detected": False,
                "force_reflect_level": req.force_reflect_level or "",
                "run_id": _run_id, "model_tier": "fast",
            }
            _dec       = _think(req.message, _dummy)
            _agent_name = (_dec.agent_strategy[0] if _dec.agent_strategy else None) or "knowledge_learning"
            _sys_prompt = _get_agent_system_prompt(_agent_name)
            from providers.anthropic import AnthropicProvider as _AP
            _ap_model    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            _ap_provider = _AP(model=_ap_model, api_key=_anthropic_key)
            loop         = asyncio.get_event_loop()
            _ap_response = await loop.run_in_executor(
                None,
                lambda: _ap_provider.generate(req.message, system_prompt=_sys_prompt),
            )
            duration_ms = int((time.time() - start) * 1000)
            agent_used  = _agent_name
            response    = _ap_response
            _bd_for_log = {
                "signal_domain": _dec.signal_domain,
                "signal_shape":  _dec.signal_shape,
                "signal_conf":   round(_dec.signal_conf, 2),
                "complexity":    _dec.complexity,
                "confidence":    round(getattr(_dec, "confidence", 0.67), 2),
                "action":        getattr(_dec, "action", "generate"),
                "memories_used": [],
            }
            result = {"brain_decision": _bd_for_log, "active_agent": agent_used}
        except Exception as _ap_err:
            run_tracer.mark_failed(_run_id, str(_ap_err))
            raise HTTPException(status_code=500, detail=f"Anthropic provider error: {_ap_err}")
    else:
        try:
            loop   = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: coordinator.invoke(_invoke_input))
        except ConnectionRefusedError:
            run_tracer.mark_failed(_run_id, "LLM backend offline")
            raise HTTPException(status_code=503, detail="LLM backend offline — start Ollama with: ollama serve")
        except Exception as e:
            run_tracer.mark_failed(_run_id, str(e))
            raise HTTPException(status_code=500, detail=str(e))

        duration_ms = int((time.time() - start) * 1000)
        agent_used  = result.get("active_agent", "unknown")
        response    = result["messages"][-1].content
        _bd_for_log = result.get("brain_decision", {})

    _save_turn(_thread_id, req.message, response, agent_used)
    bd = _bd_for_log
    _log_telemetry(
        req.message, agent_used,
        float(bd.get("signal_conf", 0.0)),
        bd.get("complexity", "simple"),
        duration_ms,
    )
    log_response(agent_used, req.message)
    try:
        _conn = sqlite3.connect(_dbpath("traces"))
        _conn.execute("""CREATE TABLE IF NOT EXISTS traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, agent TEXT, user_message TEXT,
            routing_reason TEXT, duration_ms INTEGER
        )""")
        for _col, _typ in [("signal_domain", "TEXT"), ("signal_shape", "TEXT"), ("signal_conf", "REAL")]:
            try: _conn.execute(f"ALTER TABLE traces ADD COLUMN {_col} {_typ}")
            except Exception: pass
        _bd = _bd_for_log
        _conn.execute(
            "INSERT INTO traces (timestamp, agent, user_message, routing_reason, duration_ms, signal_domain, signal_shape, signal_conf) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), agent_used, req.message[:200],
             f"routed to {agent_used}", duration_ms,
             _bd.get("signal_domain", "general"), _bd.get("signal_shape", "explanation"),
             round(float(_bd.get("signal_conf", 0.0)), 3))
        )
        _conn.commit()
        _conn.close()
    except Exception:
        pass

    confidence = _bd_for_log.get("confidence", 0.67)
    entry = {
        "ts":          datetime.now().strftime('%H:%M:%S'),
        "user":        req.message,
        "agent":       agent_used,
        "response":    response,
        "duration_ms": duration_ms,
    }
    session_history.append(entry)
    _session_id = -1
    try:
        _sc = sqlite3.connect(_SESSIONS_DB)
        _cur = _sc.execute(
            "INSERT INTO sessions (timestamp, user_input, response, agent, duration_ms, confidence) "
            "VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), req.message[:500],
             response[:2000], agent_used, duration_ms, confidence),
        )
        _session_id = _cur.lastrowid
        _sc.commit()
        _sc.close()
    except Exception:
        pass

    if _session_id > 0:
        try:
            _lnk_decisions = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "decisions.db")
            _dc = sqlite3.connect(_lnk_decisions)
            _dec_row = _dc.execute(
                "SELECT id FROM brain_decisions WHERE run_id=? LIMIT 1",
                (_run_id,),
            ).fetchone()
            if _dec_row:
                _dec_id = _dec_row[0]
                _dc.execute("UPDATE brain_decisions SET session_id=? WHERE id=?",
                            (_session_id, _dec_id))
                _dc.commit()
                _sc2 = sqlite3.connect(_SESSIONS_DB)
                _sc2.execute("UPDATE sessions SET decision_id=? WHERE id=?",
                             (_dec_id, _session_id))
                _sc2.commit()
                _sc2.close()
            _dc.close()
        except Exception:
            pass

    try:
        _linked_dec_id = locals().get("_dec_id", -1) or -1
        run_tracer.finish(
            _run_id,
            agent=agent_used,
            decision_id=int(_linked_dec_id) if _linked_dec_id else -1,
            session_id=_session_id,
            duration_ms=duration_ms,
        )
    except Exception:
        pass

    bd = _bd_for_log
    memories_used = []
    try:
        import memory_core.db as _mdb
        memories_used = _mdb.get_last_accessed_content(req.message, n=4)
    except Exception:
        pass

    _weight_before = 0.0
    _weight_after  = 0.0
    _weight_delta  = 0.0
    try:
        from decision.weights import load as _load_weights
        _weights_snap_after = _load_weights()
        _weight_before = round(_weights_snap_before.get(agent_used, 1.0), 4)
        _weight_after  = round(_weights_snap_after.get(agent_used, 1.0), 4)
        _weight_delta  = round(_weight_after - _weight_before, 4)
    except Exception:
        pass

    _contradiction = bool(result.get("contradiction_detected", False))
    if _contradiction:
        try:
            _cc = sqlite3.connect(_CONTRADICTIONS_DB)
            _cc.execute(
                "INSERT INTO contradictions (timestamp, agent, query, response_snip, reflect_level) "
                "VALUES (?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), agent_used,
                 req.message[:200], response[:120],
                 result.get("reflect_level", "none")),
            )
            _cc.commit()
            _cc.close()
        except Exception:
            pass

    try:
        _cx.finalize(_run_id, response, session_id=_session_id)
    except Exception:
        pass

    if _cos:
        try:
            _cos.request.action = bd.get("action", "unknown")
            _cos.end_request(
                agent            = agent_used,
                outcome          = "completed",
                response_snippet = response[:300],
            )
        except Exception:
            pass

    # Reset tenant ContextVar so it doesn't leak into unrelated tasks
    try:
        if _owner_token is not None:
            _owner_cv.reset(_owner_token)
    except Exception:
        pass

    return AskResponse(
        response=response,
        agent_used=agent_used,
        routing_reason=f"Routed to {agent_used}",
        duration_ms=duration_ms,
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
        reflect_level=result.get("reflect_level", "none"),
        confidence=round(float(bd.get("confidence", 0.67)), 2),
        regret=round(float(bd.get("regret", 0.0)), 3),
        contradiction_detected=_contradiction,
        memories_used=memories_used,
        gram_winner=result.get("gram_winner", ""),
        gram_log=result.get("gram_log", ""),
        weight_before=_weight_before,
        weight_after=_weight_after,
        weight_delta=_weight_delta,
        pipeline_agents=result.get("pipeline_agents", []),
        pipeline_responses=result.get("pipeline_responses", []),
        context_id=_run_id,
        thread_id=_thread_id,
        model_used=(
            os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            if _use_anthropic else "phi4-mini"
        ),
    )


@router.get("/threads")
def list_threads(limit: int = 30, include_archived: bool = False):
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        q = ("SELECT id, title, created_at, updated_at, turn_count, COALESCE(archived,0) "
             "FROM threads")
        if not include_archived:
            q += " WHERE COALESCE(archived,0)=0"
        q += " ORDER BY updated_at DESC LIMIT ?"
        rows = conn.execute(q, (limit,)).fetchall()
        conn.close()
        return {"threads": [
            {"id": r[0], "title": r[1] or "Untitled", "created_at": r[2],
             "updated_at": r[3], "turn_count": r[4] or 0, "archived": bool(r[5])}
            for r in rows
        ]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/threads/{thread_id}/turns")
def get_thread_turns(thread_id: str, limit: int = 20):
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        rows = conn.execute(
            "SELECT ts, user_msg, agent_msg, agent FROM turns "
            "WHERE thread_id=? ORDER BY id ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
        conn.close()
        return {"thread_id": thread_id, "turns": [
            {"ts": r[0], "user": r[1], "agent_response": r[2], "agent": r[3]}
            for r in rows
        ]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: str):
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        conn.execute("DELETE FROM turns   WHERE thread_id=?", (thread_id,))
        conn.execute("DELETE FROM threads WHERE id=?",        (thread_id,))
        conn.commit()
        conn.close()
        return {"deleted": thread_id}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


class ThreadRename(BaseModel):
    title: str


@router.patch("/threads/{thread_id}")
def rename_thread(thread_id: str, body: ThreadRename):
    """Rename a thread (overrides the auto-title taken from the first message)."""
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title must not be empty")
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        cur = conn.execute(
            "UPDATE threads SET title=?, updated_at=? WHERE id=?",
            (title[:200], datetime.now(timezone.utc).isoformat(), thread_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    return {"id": thread_id, "title": title[:200]}


@router.post("/threads/{thread_id}/fork")
def fork_thread(thread_id: str, upto: int = 0):
    """Copy a thread (and its turns) into a new one. upto>0 keeps only the first N turns."""
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        src = conn.execute("SELECT title FROM threads WHERE id=?", (thread_id,)).fetchone()
        if not src:
            conn.close()
            raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
        rows = conn.execute(
            "SELECT ts, user_msg, agent_msg, agent FROM turns "
            "WHERE thread_id=? ORDER BY id ASC",
            (thread_id,),
        ).fetchall()
        if upto > 0:
            rows = rows[:upto]
        new_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        new_title = f"{src[0] or 'Untitled'} (fork)"[:200]
        conn.execute(
            "INSERT INTO threads (id, title, created_at, updated_at, turn_count, archived) "
            "VALUES (?,?,?,?,?,0)",
            (new_id, new_title, now, now, len(rows)),
        )
        conn.executemany(
            "INSERT INTO turns (thread_id, ts, user_msg, agent_msg, agent) VALUES (?,?,?,?,?)",
            [(new_id, r[0], r[1], r[2], r[3]) for r in rows],
        )
        conn.commit()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"id": new_id, "title": new_title, "turn_count": len(rows), "forked_from": thread_id}


@router.post("/threads/{thread_id}/archive")
def archive_thread(thread_id: str, archived: bool = True):
    """Archive (or unarchive with ?archived=false) a thread — hides it from the default list."""
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        cur = conn.execute(
            "UPDATE threads SET archived=?, updated_at=? WHERE id=?",
            (1 if archived else 0, datetime.now(timezone.utc).isoformat(), thread_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    return {"id": thread_id, "archived": bool(archived)}


@router.get("/telemetry/routing")
def telemetry_routing(limit: int = 200):
    try:
        conn = sqlite3.connect(_TELEMETRY_DB, timeout=5)
        rows = conn.execute(
            "SELECT agent, signal_conf, complexity, duration_ms, correct "
            "FROM routing_telemetry ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

        from collections import Counter
        agents = Counter(r[0] for r in rows)
        total  = len(rows)
        labeled = [(r[0], r[4]) for r in rows if r[4] is not None]
        correct  = sum(1 for _, c in labeled if c == 1)
        accuracy = round(correct / len(labeled), 3) if labeled else None
        avg_conf = round(sum(r[1] or 0 for r in rows) / total, 3) if total else 0

        return {
            "total":          total,
            "accuracy":       accuracy,
            "labeled":        len(labeled),
            "avg_confidence": avg_conf,
            "agent_dist":     dict(agents.most_common()),
            "recent":         [
                {"agent": r[0], "conf": r[1], "complexity": r[2],
                 "ms": r[3], "correct": r[4]}
                for r in rows[:50]
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/agents")
def list_agents():
    return {"agents": [
        {"id": "coordinator",       "label": "Coordinator",         "icon": "👑", "color": "#FFD700", "role": "supervisor"},
        {"id": "it_networking",     "label": "IT & Networking",      "icon": "🌐", "color": "#00FF88", "role": "specialist"},
        {"id": "python_dev",        "label": "Python Dev",           "icon": "🐍", "color": "#3B82F6", "role": "specialist"},
        {"id": "dotnet_dev",        "label": "Blazor Dev",           "icon": "⚡", "color": "#7C3AED", "role": "specialist"},
        {"id": "ai_ml",             "label": "AI & ML",              "icon": "🤖", "color": "#F472B6", "role": "specialist"},
        {"id": "knowledge_learning","label": "Knowledge & Learning", "icon": "📚", "color": "#A78BFA", "role": "specialist"},
    ]}


@router.get("/runs")
def get_runs(limit: int = 50):
    return {"runs": run_tracer.recent(limit=limit)}


# /runs/similar/{root_cause} must be registered BEFORE /runs/{run_id}
@router.get("/runs/similar/{root_cause}")
def similar_runs(root_cause: str, exclude: str = "", limit: int = 20):
    return {
        "root_cause": root_cause,
        "runs":       run_tracer.similar_by_cause(root_cause, limit=limit, exclude_run_id=exclude),
        "total":      run_tracer.count_by_cause(root_cause),
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    trace = run_tracer.get_run(run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace


@router.post("/runs/{run_id}/replay")
def replay_run(run_id: str):
    original = run_tracer.get_run(run_id)
    if not original:
        raise HTTPException(status_code=404, detail="Run not found")
    query = (original.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="No query stored for this run")

    _run_id = run_tracer.start(query)
    _start  = time.time()
    try:
        result = coordinator.invoke({
            "messages":               [{"role": "user", "content": query}],
            "active_agent":           "",
            "task":                   query,
            "result":                 "",
            "next_agent":             "",
            "memory":                 {},
            "force_agent":            "",
            "brain_decision":         {},
            "reflect":                False,
            "reflect_type":           "general",
            "reflect_level":          "none",
            "contradiction_detected": False,
            "force_reflect_level":    "",
            "run_id":                 _run_id,
        })
    except ConnectionRefusedError:
        run_tracer.mark_failed(_run_id, "LLM backend offline")
        raise HTTPException(status_code=503, detail="LLM backend offline")
    except Exception as e:
        run_tracer.mark_failed(_run_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms = int((time.time() - _start) * 1000)
    agent_used  = result.get("active_agent", "unknown")
    run_tracer.finish(_run_id, agent=agent_used, duration_ms=duration_ms)
    return {
        "new_run_id":      _run_id,
        "original_run_id": run_id,
        "trace":           run_tracer.get_run(_run_id),
    }


@router.get("/history")
def get_history():
    try:
        conn = sqlite3.connect(_SESSIONS_DB)
        rows = conn.execute(
            "SELECT id, timestamp, user_input, response, agent, duration_ms "
            "FROM sessions ORDER BY id DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return {"history": [
            {"id": r[0], "ts": r[1], "user": r[2], "response": r[3],
             "agent": r[4], "duration_ms": r[5]}
            for r in reversed(rows)
        ]}
    except Exception:
        return {"history": session_history[-50:]}


class _ReplayRequest(BaseModel):
    query: str
    session_id: int | None = None

@router.post("/ask/replay")
def ask_replay(req: _ReplayRequest):
    """Re-run a past query with the current agent set. Returns original + replay side-by-side."""
    original = None
    if req.session_id is not None:
        try:
            conn = sqlite3.connect(_SESSIONS_DB)
            row  = conn.execute(
                "SELECT user_input, response, agent, duration_ms FROM sessions WHERE id=?",
                (req.session_id,)
            ).fetchone()
            conn.close()
            if row:
                original = {"user": row[0], "response": row[1],
                            "agent": row[2], "duration_ms": row[3]}
        except Exception:
            pass

    start = time.time()
    try:
        result = coordinator.invoke({
            "messages":               [{"role": "user", "content": req.query}],
            "active_agent":           "",
            "task":                   req.query,
            "result":                 "",
            "next_agent":             "",
            "memory":                 {},
            "force_agent":            "",
            "brain_decision":         {},
            "reflect":                False,
            "reflect_type":           "general",
            "reflect_level":          "none",
            "contradiction_detected": False,
            "force_reflect_level":    "",
            "run_id":                 f"replay-{int(time.time())}",
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms   = int((time.time() - start) * 1000)
    replay_agent  = result.get("active_agent", "unknown")
    replay_resp   = result["messages"][-1].content

    return {
        "query":    req.query,
        "original": original,
        "replay": {
            "response":    replay_resp,
            "agent":       replay_agent,
            "duration_ms": duration_ms,
        },
        "agent_changed":  original is not None and original["agent"] != replay_agent,
    }


@router.delete("/history")
def clear_history():
    session_history.clear()
    return {"status": "cleared"}


@router.get("/logs")
def get_logs():
    return {"logs": read_log(100)}


@router.get("/status")
def get_status():
    memories, by_agent = 0, {}
    done, failed, pending = 0, 0, 0
    try:
        conn = sqlite3.connect(_dbpath("memory"))
        memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        rows = conn.execute("SELECT agent_name, COUNT(*) FROM memories GROUP BY agent_name").fetchall()
        by_agent = {r[0]: r[1] for r in rows}
        conn.close()
    except Exception:
        pass
    try:
        conn = sqlite3.connect(_dbpath("tasks"))
        done    = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        failed  = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]
        conn.close()
    except Exception:
        pass
    _api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    return {
        "memories": memories,
        "by_agent": by_agent,
        "tasks": {"done": done, "failed": failed, "pending": pending},
        "model": "phi4-mini",
        "gpu": "RTX 2050",
        "model_tiers": {
            "fast":      "phi4-mini (local)",
            "standard":  "claude-sonnet-4-6 (API)" if _api_key_set else "phi4-mini (no API key)",
            "reasoning": "claude-sonnet-4-6 (API)" if _api_key_set else "phi4-mini (no API key)",
        },
        "claude_active": _api_key_set,
    }


@router.get("/metrics")
def get_metrics():
    metrics = {
        "memory":   {"total": 0, "by_agent": {}, "by_type": {}, "prune_candidates": 0, "never_used": 0},
        "tasks":    {"total": 0, "done": 0, "failed": 0, "pending": 0},
        "traces":   {"total": 0, "avg_latency_ms": 0, "last_agent": ""},
        "learning": {"regret_mean": 0.0, "calibration": {}, "weight_stability": {}},
    }
    try:
        import memory_core.db as _mdb
        ms = _mdb.memory_stats()
        metrics["memory"]["total"]            = ms["total"]
        metrics["memory"]["by_agent"]         = ms["by_agent"]
        metrics["memory"]["by_type"]          = ms["by_type"]
        metrics["memory"]["prune_candidates"] = ms["prune_candidates"]
        metrics["memory"]["never_used"]       = ms["never_used"]
    except Exception:
        pass
    try:
        conn = sqlite3.connect(_dbpath("tasks"))
        for status in ["done", "failed", "pending", "running"]:
            count = conn.execute("SELECT COUNT(*) FROM tasks WHERE status=?", (status,)).fetchone()[0]
            metrics["tasks"][status] = count
        metrics["tasks"]["total"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        conn.close()
    except Exception:
        pass
    try:
        conn = sqlite3.connect(_dbpath("traces"))
        metrics["traces"]["total"] = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        avg = conn.execute("SELECT AVG(duration_ms) FROM traces").fetchone()[0]
        metrics["traces"]["avg_latency_ms"] = round(avg) if avg else 0
        last = conn.execute("SELECT agent FROM traces ORDER BY id DESC LIMIT 1").fetchone()
        metrics["traces"]["last_agent"] = last[0] if last else ""
        conn.close()
    except Exception:
        pass
    try:
        from decision.log import regret_mean
        from decision.weights import get_all_calibration, load as load_weights
        metrics["learning"]["regret_mean"] = regret_mean(100)
        metrics["learning"]["calibration"] = {
            agent: {
                "error":          cal["error"],
                "samples":        cal["count"],
                "avg_confidence": cal["avg_confidence"],
                "avg_reflection": cal["avg_reflection"],
            }
            for agent, cal in get_all_calibration().items()
        }
        weights = load_weights()
        vals    = list(weights.values())
        if len(vals) > 1:
            mean     = sum(vals) / len(vals)
            variance = round(sum((v - mean) ** 2 for v in vals) / len(vals), 5)
        else:
            variance = 0.0
        metrics["learning"]["weight_stability"] = {
            "weights":  weights,
            "variance": variance,
        }
    except Exception:
        pass
    return metrics


# ── Streaming endpoint ────────────────────────────────────────
# Uses Claude's streaming API to deliver real-time token-by-token responses.
# Falls back to a chunked non-streaming response when no API key is set.

_AGENT_PROMPTS: dict[str, str] = {}

def _get_agent_system_prompt(agent: str) -> str:
    """Return the raw system prompt template for a given agent."""
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
        from user_profile import get_profile_context
        return template.format(user_profile=get_profile_context())
    except Exception:
        return template


@router.post("/ask/stream")
async def ask_stream(req: AskRequest):
    """
    SSE streaming response.

    When ANTHROPIC_API_KEY is set: routes the query, selects the appropriate
    agent system prompt, and streams directly via Claude Sonnet.

    When no API key: runs the standard coordinator and streams the result in
    one chunk (degraded but non-breaking).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # ── Get routing decision (always local, fast) ─────────────
    _decision_meta: dict = {}
    try:
        from orchestration.core_brain import think
        from models.state import AgentState
        _dummy_state: AgentState = {  # type: ignore[misc]
            "messages": [{"role": "user", "content": req.message}],
            "active_agent": "", "task": req.message, "result": "",
            "next_agent": "", "memory": {}, "force_agent": req.force_agent or "",
            "brain_decision": {}, "reflect": False, "reflect_type": "general",
            "reflect_level": "none", "contradiction_detected": False,
            "force_reflect_level": req.force_reflect_level or "",
            "run_id": "", "model_tier": "fast",
        }
        decision      = think(req.message, _dummy_state)
        agent_name    = decision.agent_strategy[0] if decision.agent_strategy else "knowledge_learning"
        complexity    = decision.complexity
        system_prompt = _get_agent_system_prompt(agent_name)
        _decision_meta = {
            "signal_domain":    decision.signal_domain,
            "signal_shape":     decision.signal_shape,
            "signal_verbosity": decision.signal_verbosity,
            "signal_conf":      round(decision.signal_conf, 2),
            "action":           decision.action,
            "complexity":       decision.complexity,
            "confidence":       round(getattr(decision, "confidence", 0.67), 2),
        }
    except Exception:
        agent_name    = "knowledge_learning"
        complexity    = "simple"
        system_prompt = "You are Amagra, an elite AI assistant. Be direct and precise."

    model_tier = {"compound": "reasoning", "moderate": "standard"}.get(complexity, "fast")

    _stream_doc_ctx = _get_document_context(req.message, req.context_files or [])
    _stream_msg     = f"{_stream_doc_ctx}\n\n{req.message}" if _stream_doc_ctx else req.message

    async def _event_stream():
        yield f"data: {json.dumps({'type': 'routing', 'agent': agent_name, 'complexity': complexity, 'model_tier': model_tier, **_decision_meta})}\n\n"

        if api_key:
            # ── Claude streaming path ──────────────────────────
            try:
                from providers.anthropic import AnthropicProvider
                stream_model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
                provider     = AnthropicProvider(model=stream_model, api_key=api_key)
                async for chunk in provider.stream(_stream_msg, system_prompt=system_prompt):
                    if chunk:
                        yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'agent': agent_name, 'model': stream_model, **_decision_meta})}\n\n"
                return
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
                # fall through to non-streaming path

        # ── Fallback: run coordinator, emit as one chunk ───────
        try:
            import cognition.run_tracer as _rt
            _run_id = _rt.start(req.message)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: coordinator.invoke({
                    "messages":              [{"role": "user", "content": _stream_msg}],
                    "active_agent": "", "task": _stream_msg, "result": "",
                    "next_agent": "", "memory": {}, "force_agent": req.force_agent or "",
                    "brain_decision": {}, "reflect": False, "reflect_type": "general",
                    "reflect_level": "none", "contradiction_detected": False,
                    "force_reflect_level": req.force_reflect_level or "",
                    "run_id": _run_id, "model_tier": "fast",
                })
            )
            bd       = result.get("brain_decision", {})
            fallback_agent = result.get("active_agent", agent_name)
            yield f"data: {json.dumps({'type': 'token', 'text': result['messages'][-1].content})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'agent': fallback_agent, 'model': 'phi4-mini', **_decision_meta, 'reflect_level': result.get('reflect_level', 'none'), 'memories_used': bd.get('memories_used', [])})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
