import os
import time
import sqlite3
import uuid
import json
import queue
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from infrastructure.version import __version__
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from orchestration.coordinator import coordinator
from core.logger import read_log
import cognition.run_tracer as run_tracer
from infrastructure.db import path as _dbpath
from infrastructure.inference_limit import inference_slot

from .deps import (
    session_history, _SESSIONS_DB,
    AskRequest, AskResponse,
)
from . import ask_pipeline as pipeline
from .ask_pipeline import TELEMETRY_DB as _TELEMETRY_DB, base_state

router = APIRouter()


# NOTE: "/" is owned by the bundled UI (api.py serves ui/build there). Machine
# clients use /health or the richer /status (defined below) — the old minimal
# root JSON was redundant and was removed when the UI moved to the same origin.


@router.get("/health")
def health():
    _api_key_set   = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    _brain_backend = os.environ.get("BRAIN_PROVIDER", "ollama")
    _enhance_model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
    result: dict = {
        "status":    "online",
        "version":   __version__,
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


def _is_offline_error(exc: Exception) -> bool:
    """True when `exc` looks like the LLM backend being unreachable (errno 111
    and friends) — even when wrapped by httpx / requests / the ollama client,
    which is why a bare `except ConnectionRefusedError` misses it and the error
    used to leak as a raw 500 instead of a friendly 503."""
    seen: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if isinstance(e, ConnectionRefusedError):
            return True
        if isinstance(e, OSError) and getattr(e, "errno", None) == 111:
            return True
        e = e.__cause__ or e.__context__
    msg = str(exc).lower()
    return any(s in msg for s in (
        "connection refused", "[errno 111]", "max retries exceeded",
        "failed to establish a new connection", "all connection attempts failed",
        "cannot connect to host", "connection error",
    ))


_OFFLINE_DETAIL = ("LLM backend offline — start Ollama (ollama serve) "
                   "or check your provider in Settings → Model")


def _anthropic_selected(req: AskRequest) -> bool:
    """Anthropic provider path — when the caller requests it explicitly or
    PREFER_ANTHROPIC=1 is set and an API key is available."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY", "")
        and (req.provider == "anthropic" or os.environ.get("PREFER_ANTHROPIC", "0") == "1")
    )


async def _invoke_coordinator(state: dict) -> dict:
    """The one place the local model is invoked. Gated: a burst of concurrent
    calls OOMs the GPU. Raises the raw exception — callers map it via
    `_map_invoke_error` after marking the run failed."""
    loop = asyncio.get_event_loop()
    async with inference_slot():
        return await loop.run_in_executor(None, lambda: coordinator.invoke(state))


def _map_invoke_error(e: Exception) -> HTTPException:
    if isinstance(e, ConnectionRefusedError) or _is_offline_error(e):
        return HTTPException(status_code=503, detail=_OFFLINE_DETAIL)
    return HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request):
    run = pipeline.begin_run(req, key_id=getattr(request.state, "key_id", None))

    if _anthropic_selected(req):
        try:
            pre = pipeline.route_preview(req, run_id=run.run_id)
            from providers.anthropic import AnthropicProvider as _AP
            _ap_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            provider  = _AP(model=_ap_model, api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            loop = asyncio.get_event_loop()
            run.response = await loop.run_in_executor(
                None,
                lambda: provider.generate(run.task_msg,
                                          system_prompt=pre.system_prompt,
                                          messages=run.provider_messages),
            )
            run.agent_used = pre.agent
            run.bd         = {**pre.meta, "memories_used": []}
            run.result     = {"brain_decision": run.bd, "active_agent": pre.agent}
            run.model_used = _ap_model
        except Exception as _ap_err:
            pipeline.fail_run(run, str(_ap_err))
            raise HTTPException(status_code=500, detail=f"Anthropic provider error: {_ap_err}")
    else:
        state = base_state(run.task_msg, run.run_id,
                           messages=run.provider_messages,
                           force_agent=req.force_agent or "",
                           force_reflect_level=req.force_reflect_level or "")
        try:
            run.result = await _invoke_coordinator(state)
        except Exception as e:
            pipeline.fail_run(run, "LLM backend offline" if isinstance(e, ConnectionRefusedError) else str(e))
            raise _map_invoke_error(e)
        run.agent_used = run.result.get("active_agent", "unknown")
        run.response   = run.result["messages"][-1].content
        run.bd         = run.result.get("brain_decision", {})
        run.model_used = "phi4-mini"

    extras = pipeline.finish_run(run)
    return pipeline.build_response(run, extras)


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


@router.post("/threads/{thread_id}/truncate")
def truncate_thread(thread_id: str, keep: int = 0):
    """Drop all turns after the first `keep` (oldest-first). Backs edit-and-resend:
    editing turn N truncates to keep=N, then the new /ask appends the replacement."""
    if keep < 0:
        raise HTTPException(status_code=400, detail="keep must be >= 0")
    try:
        conn = sqlite3.connect(_SESSIONS_DB, timeout=5)
        exists = conn.execute("SELECT 1 FROM threads WHERE id=?", (thread_id,)).fetchone()
        if not exists:
            conn.close()
            raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
        # Identify the turn ids to keep (oldest first), delete the rest.
        keep_ids = [r[0] for r in conn.execute(
            "SELECT id FROM turns WHERE thread_id=? ORDER BY id ASC LIMIT ?",
            (thread_id, keep),
        ).fetchall()]
        if keep_ids:
            placeholders = ",".join("?" * len(keep_ids))
            conn.execute(
                f"DELETE FROM turns WHERE thread_id=? AND id NOT IN ({placeholders})",
                (thread_id, *keep_ids),
            )
        else:
            conn.execute("DELETE FROM turns WHERE thread_id=?", (thread_id,))
        remaining = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE thread_id=?", (thread_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE threads SET turn_count=?, updated_at=? WHERE id=?",
            (remaining, datetime.now(timezone.utc).isoformat(), thread_id),
        )
        conn.commit()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"id": thread_id, "turn_count": remaining}


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

        # Signed, mode-resolved stability: the slowest-contracting agent mode
        # (min α ⇒ K nearest 1) and its signed drift — what pooled variance
        # can't see. Best-effort so a metrics failure never 503s the endpoint.
        try:
            from decision.weights import _neutral_mode
            neutral_mode = _neutral_mode()
        except Exception:
            neutral_mode = {"agent": None, "K": 0.0,
                            "signed_drift": 0.0, "regime": "flat"}

        return {
            "total":          total,
            "accuracy":       accuracy,
            "labeled":        len(labeled),
            "avg_confidence": avg_conf,
            "agent_dist":     dict(agents.most_common()),
            "neutral_mode":   neutral_mode,
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


# /runs/cost must be registered BEFORE /runs/{run_id}
@router.get("/runs/cost")
def runs_cost(limit: int = 200):
    """Inference-cost summary over recent runs (Cognition Productivity axis).
    All-zero in the local-only default — escalation is opt-in (AMAGRA_HYBRID)."""
    return run_tracer.cost_summary(limit=limit)


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
        result = coordinator.invoke(base_state(query, _run_id))
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
        result = coordinator.invoke(base_state(req.query, f"replay-{int(time.time())}"))
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

@router.post("/ask/stream")
async def ask_stream(req: AskRequest, request: Request):
    """
    SSE streaming response — same pipeline as /ask, different transport.

    When ANTHROPIC_API_KEY is set: routes the query, selects the appropriate
    agent system prompt, and streams token-by-token via Claude.

    When no API key: runs the standard coordinator, forwarding its real
    lifecycle events as they happen, and delivers the result in one chunk.

    Either way the run is persisted through `pipeline.finish_run` after the
    last token — a streamed chat leaves exactly the same records as /ask
    (threads, session, telemetry, traces, run log; contract §1.1).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    run = pipeline.begin_run(req, key_id=getattr(request.state, "key_id", None))
    pre = pipeline.route_preview(req, run_id=run.run_id)

    async def _event_stream():
        yield _sse({"type": "routing", "agent": pre.agent, "complexity": pre.complexity,
                    "model_tier": pre.model_tier, "thread_id": run.thread_id,
                    "context_id": run.run_id, **pre.meta})

        if api_key:
            # ── Claude streaming path ──────────────────────────
            try:
                from providers.anthropic import AnthropicProvider
                stream_model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
                provider     = AnthropicProvider(model=stream_model, api_key=api_key)
                acc: list[str] = []
                async for chunk in provider.stream(run.task_msg,
                                                   system_prompt=pre.system_prompt,
                                                   messages=run.provider_messages):
                    if chunk:
                        acc.append(chunk)
                        yield _sse({"type": "token", "text": chunk})
                run.response   = "".join(acc)
                run.agent_used = pre.agent
                run.bd         = dict(pre.meta)
                run.result     = {"brain_decision": run.bd, "active_agent": pre.agent}
                run.model_used = stream_model
                extras = pipeline.finish_run(run)
                yield _sse({"type": "done", "agent": pre.agent, "model": stream_model,
                            "thread_id": run.thread_id, "context_id": run.run_id,
                            **pre.meta,
                            "memories_used": extras.get("memories_used", [])})
                return
            except Exception as exc:
                yield _sse({"type": "error", "detail": str(exc)})
                # fall through to non-streaming path

        # ── Fallback: run coordinator, stream its real lifecycle events ───
        # The coordinator emits agent.selected / step.verified.* as the work
        # actually happens, from an executor thread. Forward the events
        # belonging to *this* run so the client sees progress that occurred
        # rather than progress on a timer. SimpleQueue because the emitting
        # thread is not the event loop's.
        try:
            from infrastructure.event_bus import (
                subscribe as _subscribe, unsubscribe as _unsubscribe,
                EventType as _ET,
            )
            _steps = queue.SimpleQueue()

            def _on_step(key, payload, ts):
                # The bus is global and requests are concurrent — run_id is
                # what makes a forwarded step provably ours.
                if payload.get("run_id") == run.run_id:
                    _steps.put({"type": "step", "event": key, "payload": payload})

            _watched = (_ET.AGENT_SELECTED, _ET.STEP_VERIFIED_PASS, _ET.STEP_VERIFIED_FAIL)
            for _et in _watched:
                _subscribe(_et, _on_step)

            state = base_state(run.task_msg, run.run_id,
                               messages=run.provider_messages,
                               force_agent=req.force_agent or "",
                               force_reflect_level=req.force_reflect_level or "")
            try:
                async with inference_slot():  # gate local inference (GPU OOM guard)
                    _work = asyncio.get_event_loop().run_in_executor(
                        None, lambda: coordinator.invoke(state)
                    )
                    while not _work.done():
                        try:
                            yield f"data: {json.dumps(_steps.get_nowait())}\n\n"
                        except queue.Empty:
                            await asyncio.sleep(0.05)
                    result = await _work
            finally:
                for _et in _watched:
                    _unsubscribe(_et, _on_step)

            # Events emitted between the final poll and completion.
            while True:
                try:
                    yield f"data: {json.dumps(_steps.get_nowait())}\n\n"
                except queue.Empty:
                    break

            run.result     = result
            run.agent_used = result.get("active_agent", pre.agent)
            run.response   = result["messages"][-1].content
            run.bd         = result.get("brain_decision", {})
            run.model_used = "phi4-mini"
            extras = pipeline.finish_run(run)
            yield _sse({"type": "token", "text": run.response})
            yield _sse({"type": "done", "agent": run.agent_used, "model": "phi4-mini",
                        "thread_id": run.thread_id, "context_id": run.run_id,
                        **pre.meta,
                        "reflect_level": result.get("reflect_level", "none"),
                        "memories_used": extras.get("memories_used",
                                                    run.bd.get("memories_used", []))})
        except Exception as exc:
            pipeline.fail_run(run, str(exc))
            yield _sse({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
