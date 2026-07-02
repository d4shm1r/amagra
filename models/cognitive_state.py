"""
cognitive_state.py — Unified Cognitive State (Phase 35)

A session-scoped object that every component can read from and
write to. Replaces the ad-hoc dict passing between components.

CognitiveState wraps:
  - WorldModel       (project continuity across requests)
  - Plan             (current execution plan)
  - RiskSignal       (most recent risk assessment)
  - RuntimeMetrics   (live snapshot from metrics_engine)
  - EventBus         (single emit point)

It is NOT a LangGraph state (AgentState stays for the graph).
It IS the session-level substrate that spans multiple requests.

Lifecycle:
  1. Session starts → CognitiveState.new(session_id)
  2. Each request → state.begin_request(query, run_id)
  3. Components update via state.set_plan(), state.set_risk(), etc.
  4. Request ends → state.end_request(agent, outcome)
  5. Session ends → state persists automatically via WorldModel

Usage:
    from models.cognitive_state import CognitiveState, get_session_state

    state = get_session_state(session_id)
    state.begin_request(query="Build FastAPI with JWT", run_id="abc123")
    state.set_plan(plan)
    state.set_risk(risk_signal)
    state.end_request(agent="python_dev", outcome="completed")
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict

# ── Session registry (in-process cache) ──────────────────────
_SESSIONS: Dict[str, "CognitiveState"] = {}


# ── Sub-states ────────────────────────────────────────────────

@dataclass
class RequestContext:
    """Transient per-request data reset on begin_request()."""
    run_id:      str   = ""
    query:       str   = ""
    agent:       str   = ""
    action:      str   = "unknown"
    complexity:  str   = "simple"
    started_at:  float = 0.0
    ended_at:    float = 0.0

    @property
    def latency_ms(self) -> float:
        if self.ended_at and self.started_at:
            return round((self.ended_at - self.started_at) * 1000, 1)
        return 0.0


# ── Main CognitiveState ───────────────────────────────────────

@dataclass
class CognitiveState:
    session_id: str

    # ── World model (session-scoped, persists) ────────────────
    world: Any = None              # WorldModel — lazy loaded

    # ── Request context (reset each request) ─────────────────
    request: RequestContext = field(default_factory=RequestContext)

    # ── Current plan ─────────────────────────────────────────
    plan: Any = None               # planner.Plan or None

    # ── Risk signal ───────────────────────────────────────────
    risk: Any = None               # risk_gate.RiskSignal or None

    # ── Metrics snapshot ─────────────────────────────────────
    _metrics_cache: Dict[str, Any] = field(default_factory=dict)
    _metrics_ts:    float           = 0.0

    # ── Internal tracking ────────────────────────────────────
    total_requests: int   = 0
    session_start:  float = field(default_factory=time.time)

    def __post_init__(self):
        if self.world is None:
            self._load_world()

    def _load_world(self) -> None:
        try:
            from models.world_model import load_world
            self.world = load_world(self.session_id)
        except Exception as e:
            print(f"[cognitive_state] world model load error: {e}")

    # ── Request lifecycle ─────────────────────────────────────

    def begin_request(self, query: str, run_id: str = "",
                      action: str = "unknown", complexity: str = "simple") -> None:
        self.request = RequestContext(
            run_id     = run_id,
            query      = query,
            action     = action,
            complexity = complexity,
            started_at = time.time(),
        )
        self.plan = None
        self.risk = None
        self.total_requests += 1

        try:
            from infrastructure.event_bus import emit, EventType
            emit(EventType.QUERY_RECEIVED, {
                "session_id": self.session_id,
                "run_id":     run_id,
                "query":      query[:200],
                "action":     action,
                "complexity": complexity,
            })
        except Exception:
            pass

    def end_request(self, agent: str, outcome: str = "completed",
                    response_snippet: str = "",
                    quality: float | None = None, kept: str = "") -> None:
        self.request.agent    = agent
        self.request.ended_at = time.time()

        # Update world model
        if self.world:
            try:
                from models.world_model import update_from_query
                self.world = update_from_query(
                    self.world,
                    query    = self.request.query,
                    agent    = agent,
                    response = response_snippet,
                    outcome  = outcome,
                )
                if outcome == "completed":
                    self.world.add_completed(self.request.query[:100])
                self.world.save()
            except Exception as e:
                print(f"[cognitive_state] world update error: {e}")

        try:
            from infrastructure.event_bus import emit, EventType
            payload = {
                "session_id": self.session_id,
                "run_id":     self.request.run_id,
                "agent":      agent,
                "outcome":    outcome,
                "latency_ms": self.request.latency_ms,
            }
            # Responder transparency (#47): disclose the critic-gate quality
            # score as confidence and the kept response as evidence. Keys are
            # omitted when the gate didn't run — never fabricated.
            if quality is not None:
                payload["confidence"] = round(float(quality), 3)
            if kept:
                payload["evidence"] = kept
            emit(EventType.RESPONSE_GENERATED, payload)
        except Exception:
            pass

    # ── Component setters ─────────────────────────────────────

    def set_plan(self, plan: Any) -> None:
        self.plan = plan
        try:
            from infrastructure.event_bus import emit, EventType
            emit(EventType.PLAN_CREATED, {
                "session_id":    self.session_id,
                "run_id":        self.request.run_id,
                "steps":         len(plan.steps) if plan else 0,
                "mode":          plan.mode if plan else "",
                "uncertainty":   plan.uncertainty if plan else 0,
                "parallel_groups": plan.parallel_groups if plan else [],
            })
        except Exception:
            pass

    def set_risk(self, risk: Any) -> None:
        self.risk = risk
        try:
            from infrastructure.event_bus import emit, EventType
            emit(EventType.RISK_COMPUTED, {
                "session_id":   self.session_id,
                "run_id":       self.request.run_id,
                "total_risk":   risk.total_risk,
                "reflect_level":risk.reflect_level,
                "reflect_type": risk.reflect_type,
                # the breakdown that produced total_risk — the evidence
                # behind the gate's decision (makes Risk Gate transparent)
                "factors": {
                    "action_risk":         getattr(risk, "action_risk", None),
                    "routing_uncertainty": getattr(risk, "routing_uncertainty", None),
                    "planner_uncertainty": getattr(risk, "planner_uncertainty", None),
                    "complexity_risk":     getattr(risk, "complexity_risk", None),
                },
            })
        except Exception:
            pass

    def add_issue(self, description: str, step_id: str = "") -> None:
        if self.world:
            self.world.add_issue(description, step_id)

    # ── Snapshot ──────────────────────────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        """
        Full state snapshot for the UI or debugging.
        Returns a JSON-serializable dict.
        """
        return {
            "session_id":     self.session_id,
            "total_requests": self.total_requests,
            "session_age_s":  round(time.time() - self.session_start),
            "request": {
                "run_id":     self.request.run_id,
                "query":      self.request.query[:200],
                "agent":      self.request.agent,
                "action":     self.request.action,
                "complexity": self.request.complexity,
                "latency_ms": self.request.latency_ms,
            },
            "plan": {
                "steps":       len(self.plan.steps) if self.plan else 0,
                "mode":        self.plan.mode if self.plan else None,
                "uncertainty": self.plan.uncertainty if self.plan else None,
            } if self.plan else None,
            "risk": {
                "total_risk":   self.risk.total_risk,
                "reflect_level":self.risk.reflect_level,
            } if self.risk else None,
            "world": {
                "project_context": self.world.project_context,
                "current_goal":    self.world.current_goal[:100],
                "completed_count": len(self.world.completed_tasks),
                "issue_count":     len(self.world.known_issues),
                "context_summary": self.world.context_summary(),
            } if self.world else None,
            "metrics": self.metrics(),
        }

    def metrics(self, force: bool = False) -> Dict[str, Any]:
        """Current UCI metrics (cached 30s)."""
        now = time.time()
        if not force and self._metrics_cache and (now - self._metrics_ts) < 30:
            return self._metrics_cache
        try:
            from infrastructure.metrics_engine import get_metrics
            self._metrics_cache = get_metrics()
            self._metrics_ts    = now
        except Exception:
            pass
        return self._metrics_cache


# ── Session registry ──────────────────────────────────────────

def get_session_state(session_id: str) -> CognitiveState:
    """
    Get or create the CognitiveState for a session.
    One state object per session_id, cached in process memory.
    """
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = CognitiveState(session_id=session_id)
    return _SESSIONS[session_id]


def drop_session(session_id: str) -> None:
    """Remove session from in-process cache (world model already persisted)."""
    _SESSIONS.pop(session_id, None)


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    print("=" * 65)
    print("  cognitive_state.py — session lifecycle test")
    print("=" * 65)

    sid   = "test-cos-session-001"
    state = get_session_state(sid)

    # Simulate three requests
    interactions = [
        ("Build a FastAPI app with JWT auth", "build",   "python_dev",  "completed"),
        ("Debug nginx 502 when proxying",     "debug",   "it_networking","completed"),
        ("Explain JWT vs OAuth2 differences", "explain", "knowledge_learning", "completed"),
    ]

    for query, action, agent, outcome in interactions:
        state.begin_request(query, run_id=f"run-{int(time.time())}", action=action)

        # Simulate plan creation
        try:
            from orchestration.planner import plan_query
            plan = plan_query(query, action=action, agents=[agent])
            state.set_plan(plan)
        except Exception:
            pass

        # Simulate risk assessment
        try:
            from cognition.risk_gate import compute_risk
            risk = compute_risk(action, agent, confidence=0.65, log=False)
            state.set_risk(risk)
        except Exception:
            pass

        state.end_request(agent, outcome, response_snippet=f"Response to: {query}")
        print(f"\n  After '{query[:45]}...':")
        snap = state.snapshot()
        print(f"    World context: {snap['world']['project_context']}")
        print(f"    Goal:          {snap['world']['current_goal'][:60]}")
        if snap.get("plan"):
            print(f"    Plan:          {snap['plan']['steps']} steps, u={snap['plan']['uncertainty']}")
        if snap.get("risk"):
            print(f"    Risk:          {snap['risk']['total_risk']:.3f} → {snap['risk']['reflect_level']}")

    print(f"\n  UCI: {state.metrics().get('uci', 'N/A')}")
    print(f"  Session snapshot:\n{json.dumps(state.snapshot(), indent=4)[:1200]}...")
