import asyncio
import json
import queue
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .deps import _cos

router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/plan/graph")
def plan_graph():
    """Serialize the current Plan into nodes + edges for DAG visualization."""
    if not _cos:
        raise HTTPException(status_code=503, detail="CognitiveState not available")
    plan = _cos.plan
    if not plan:
        return {"nodes": [], "edges": [], "levels": [], "meta": None}

    # Build level lookup from parallel_groups
    level_of = {}
    for lvl_idx, group in enumerate(plan.parallel_groups):
        for sid in group:
            level_of[sid] = lvl_idx

    nodes = [
        {
            "id":               s.step_id,
            "description":      s.description,
            "agent":            s.agent,
            "status":           s.status,
            "uncertainty":      round(s.uncertainty, 3),
            "success_criteria": s.success_criteria,
            "action_type":      s.action_type,
            "depends_on":       s.depends_on,
            "result_snippet":   s.result_snippet,
            "elapsed_ms":       getattr(s, "elapsed_ms", 0.0),
            "level":            level_of.get(s.step_id, 0),
        }
        for s in plan.steps
    ]

    edges = [
        {"source": dep, "target": s.step_id}
        for s in plan.steps
        for dep in s.depends_on
    ]

    return {
        "nodes":  nodes,
        "edges":  edges,
        "levels": plan.parallel_groups,
        "meta": {
            "query":       plan.query,
            "mode":        plan.mode,
            "uncertainty": round(plan.uncertainty, 3),
            "steps":       len(plan.steps),
            "elapsed_ms":  round(plan.elapsed_ms, 1),
        },
    }


@router.get("/cos/state")
def cos_state():
    if not _cos:
        raise HTTPException(status_code=503, detail="CognitiveState not available")
    return _cos.snapshot()


@router.get("/cos/world")
def cos_world(request: Request, org: str | None = None):
    """
    Return the world model for this session.
    Team-tier keys may pass ?org=<org_id> to read the shared org world model,
    or it is inferred from the request.state.org_id set by the auth middleware.
    """
    session_id = (
        org
        or getattr(request.state, "org_id", None)
        or (_cos.session_id if _cos else "cos-session-main")
    )

    try:
        from models.world_model import load_world
        w = load_world(session_id)
    except Exception:
        if not _cos or not _cos.world:
            raise HTTPException(status_code=503, detail="World model not available")
        w = _cos.world

    return {
        "session_id":      w.session_id,
        "project_context": w.project_context,
        "current_goal":    w.current_goal,
        "entities":        w.entities,
        "completed_tasks": w.completed_tasks[-10:],
        "known_issues":    w.known_issues[-10:],
        "interaction_log": w.interaction_log[-20:],
        "context_summary": w.context_summary(),
        "updated_at":      w.updated_at,
    }


@router.get("/cos/events")
def cos_events(n: int = 100, event_type: str = None):
    try:
        from infrastructure.event_bus import recent_events, event_counts
        return {
            "events": recent_events(n=n, event_type=event_type),
            "counts": event_counts(),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/events/stream")
async def cos_events_stream(request: Request, backlog: int = 20, health_interval: float = 20.0,
                             max_seconds: float = 1800.0):
    """Live SSE tail of the runtime event bus — the terminal-style feed.

    Unlike `/cos/events` (a poll snapshot), this holds the connection open and
    pushes every bus event as it fires, so a dock can show activity the moment
    it happens rather than on the next poll tick. A `health.tick` is interleaved
    on `health_interval` so the stream keeps producing signal even during quiet
    periods — the "still watching" half of a health-checker, not just an
    activity log. Auth follows the rest of `/cos/*` (owner API key, not public).

    `max_seconds` bounds the connection even if the transport never reports
    `is_disconnected()` (proxies and some ASGI transports don't) — the dock
    reconnects on `stream.closed` rather than a subscriber leaking forever.
    """
    from infrastructure.event_bus import subscribe, unsubscribe, recent_events
    from .core import health as _health

    _q: "queue.SimpleQueue" = queue.SimpleQueue()

    def _on_event(event_type, payload, ts):
        _q.put({"type": event_type, "payload": payload, "ts": ts})

    subscribe("*", _on_event)

    async def _gen():
        try:
            start = time.time()
            yield _sse({"type": "stream.connected", "ts": start})
            if backlog:
                # Chronological, so the dock can just append.
                yield _sse({"type": "stream.backlog",
                            "events": list(reversed(recent_events(n=backlog)))})

            last_health = start
            while time.time() - start < max_seconds:
                if await request.is_disconnected():
                    break
                try:
                    yield _sse(_q.get_nowait())
                    continue
                except queue.Empty:
                    pass

                now = time.time()
                if health_interval and now - last_health >= health_interval:
                    last_health = now
                    try:
                        yield _sse({"type": "health.tick", "payload": _health(), "ts": now})
                    except Exception:
                        pass

                await asyncio.sleep(0.3)

            yield _sse({"type": "stream.closed", "ts": time.time()})
        finally:
            unsubscribe("*", _on_event)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/cos/uci")
def cos_uci(force: bool = False):
    try:
        from infrastructure.metrics_engine import get_metrics
        return get_metrics(force=force)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/uci/hierarchical")
def cos_uci_hierarchical(force: bool = False):
    try:
        from infrastructure.metrics_engine import hierarchical_metrics
        return hierarchical_metrics(force=force)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/uci/trajectory")
def cos_uci_trajectory(n: int = 100):
    """UCI trajectory + Δ² curvature (OCAC leading indicator).

    history    — chronological UCI samples from events.db (uci.computed)
    curvature  — per-point second-difference series, peak |Δ²|, and a `bending`
                 flag that fires when curvature exceeds 2 UCI points (a sharp
                 downturn accelerating *before* the level itself drops).
    """
    try:
        from infrastructure.metrics_engine import uci_history, uci_curvature
        return {"history": uci_history(n), "curvature": uci_curvature(n)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/transparency")
def cos_transparency(window: int = 2000):
    """Classify each component as transparent / partial / opaque / mechanical
    / unobserved from the evidence + confidence its events disclose."""
    try:
        from infrastructure.transparency import classify_components
        return classify_components(window=window)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/skills")
def cos_skills(query: str = ""):
    try:
        from infrastructure.skill_graph import select_skills, _SKILLS, skill_summary
        if query:
            skills = select_skills(query, n=5)
            return {
                "query":   query,
                "matches": [
                    {"name": s.name, "agent": s.agent,
                     "category": s.category, "score": s.score,
                     "description": s.description, "complexity": s.complexity}
                    for s in skills
                ],
                "summary": skill_summary(skills),
                "top_agent": skills[0].agent if skills else "knowledge_learning",
            }
        else:
            return {
                "skills": [
                    {"name": s.name, "agent": s.agent,
                     "category": s.category, "description": s.description,
                     "complexity": s.complexity, "keywords": len(s.keywords)}
                    for s in _SKILLS
                ],
                "total": len(_SKILLS),
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/skills/entropy")
def cos_skills_entropy(window: int = 100):
    """Rolling skill-selection entropy — the saturation diagnostic that gates
    tuning of the A←R coupling gains (see infrastructure/skill_graph.py and
    docs/design/TCST_AGENT_MODEL.md §5)."""
    try:
        from infrastructure.skill_graph import entropy_report
        return entropy_report(window=window)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/verify/stats")
def verify_stats_route(n: int = 200):
    try:
        from cognition.step_verifier import verify_stats as _vs
        result = _vs(n=n)
        if not result:
            return {"n": 0, "pass_rate": None, "mean_score": None,
                    "by_recommendation": {}}
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/cos/suggestions")
def cos_suggestions(session_id: str = "cos-session-main", n: int = 4):
    try:
        from infrastructure.suggestion_engine import generate_suggestions
        return {"suggestions": generate_suggestions(session_id=session_id, n=n)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/agents/status")
def agents_status():
    import time as _time
    try:
        from infrastructure.event_bus import recent_events
        evs  = recent_events(n=80)
        now  = _time.time()
        seen: set = set()
        result = []
        for ev in evs:          # newest-first — first occurrence wins
            et  = ev.get("type", "")
            ag  = ev.get("payload", {}).get("agent")
            if not ag or ag in seen:
                continue
            seen.add(ag)
            ts  = ev.get("ts", 0)
            age = now - ts
            if "step.started" in et or "agent.selected" in et:
                status = "running" if age < 45 else "idle"
            elif ("step.completed" in et or "verified.pass" in et
                  or "response.generated" in et or "plan.completed" in et):
                status = "done" if age < 300 else "idle"
            elif "fail" in et or "error" in et or "aborted" in et:
                status = "error"
            else:
                status = "idle"
            result.append({
                "agent":      ag,
                "status":     status,
                "last_event": et,
                "ts":         ts,
                "age_s":      round(age, 1),
            })
        return {"agents": result, "ts": now}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/verify/recent")
def verify_recent(n: int = 50):
    try:
        import sqlite3
        from cognition.step_verifier import _DB_PATH, _ensure_db
        _ensure_db()
        con  = sqlite3.connect(_DB_PATH, timeout=3)
        rows = con.execute(
            "SELECT ts, step_id, agent, raw_score, threshold, passed, "
            "recommendation, issues "
            "FROM step_verify_log ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        con.close()
        return {
            "verifications": [
                {
                    "ts":             r[0],
                    "step_id":        r[1],
                    "agent":          r[2],
                    "raw_score":      round(r[3], 3),
                    "threshold":      round(r[4], 3),
                    "passed":         bool(r[5]),
                    "recommendation": r[6],
                    "issues":         r[7] or "",
                }
                for r in rows
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
