"""
suggestion_engine.py — proactive suggestions derived from world-model issues,
event-bus failure patterns, and skill coverage gaps.
"""
from __future__ import annotations
import re

_MAX_SUGGESTIONS = 4


def _shorten(text: str, n: int = 58) -> str:
    return text[:n] + ("…" if len(text) > n else "")


def _agent_for(desc: str) -> str:
    try:
        from infrastructure.skill_graph import select_skills
        skills = select_skills(desc, n=1)
        return skills[0].agent if skills else "auto"
    except Exception:
        return "auto"


def generate_suggestions(
    session_id: str = "cos-session-main",
    n: int = _MAX_SUGGESTIONS,
) -> list[dict]:
    suggestions: list[dict] = []

    # ── 1. World-model known issues ─────────────────────────────
    try:
        from models.world_model import load_world
        world = load_world(session_id)
        for issue in reversed(world.known_issues[-4:]):
            desc = (issue.get("description") or "").strip()
            if not desc:
                continue
            suggestions.append({
                "title":     f"Resolve: {_shorten(desc)}",
                "rationale": "Flagged by the verifier / world model",
                "query":     f"Fix this issue: {desc}",
                "agent":     _agent_for(desc),
                "source":    "verifier",
                "priority":  "high",
            })
    except Exception:
        pass

    # ── 2. Event-bus failure patterns ───────────────────────────
    try:
        from infrastructure.event_bus import recent_events
        events = recent_events(n=40)
        seen_steps: set[str] = set()
        for ev in events:
            et = (ev.get("type") or "")
            if "fail" not in et:
                continue
            payload = ev.get("payload") or {}
            step_id = str(payload.get("step_id") or payload.get("agent") or "")
            if not step_id or step_id in seen_steps:
                continue
            seen_steps.add(step_id)
            agent = payload.get("agent") or "auto"
            label = re.sub(r"[_\-]", " ", step_id).title()
            suggestions.append({
                "title":     f"Retry: {_shorten(label, 50)}",
                "rationale": f"Step failed recently (agent: {agent})",
                "query":     f"Retry the failed step: {step_id}",
                "agent":     agent,
                "source":    "event_bus",
                "priority":  "medium",
            })
    except Exception:
        pass

    # ── 3. Reflection gap ────────────────────────────────────────
    if len(suggestions) < n:
        try:
            from infrastructure.event_bus import recent_events
            events = recent_events(n=20)
            has_reflect = any("reflect" in (e.get("type") or "") for e in events)
            if not has_reflect:
                suggestions.append({
                    "title":     "Enable light reflection",
                    "rationale": "No reflection activity detected in recent history",
                    "query":     "Enable light reflect mode and re-run the last query",
                    "agent":     "auto",
                    "source":    "system",
                    "priority":  "low",
                })
        except Exception:
            pass

    # ── 4. Deduplicate and cap ───────────────────────────────────
    seen: set[str] = set()
    result: list[dict] = []
    for s in suggestions:
        key = s["title"][:35]
        if key not in seen:
            seen.add(key)
            result.append(s)
        if len(result) >= n:
            break

    return result
