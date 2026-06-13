from fastapi import APIRouter, HTTPException, Request

from .deps import _cos

router = APIRouter()


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
