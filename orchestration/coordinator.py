import os
import time
import sys
import sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
import cognition.run_tracer as run_tracer

from models.state import AgentState
from orchestration.router import hybrid_router
from orchestration.core_brain import think
from decision.log import log as log_decision
from training.learning import apply_learning_update

# ── Specialist agents ─────────────────────────────────────────
from agents.it_networking      import it_agent
from agents.python_dev         import python_agent, PYTHON_SYSTEM_PROMPT
from agents.dotnet_dev         import dotnet_agent, DOTNET_SYSTEM_PROMPT
from agents.ai_ml              import ai_ml_agent
from agents.knowledge_learning import knowledge_agent
from agents.terse              import terse_agent
from agents.web_dev            import web_dev_agent
from agents.devops             import devops_agent
from agents.data_analyst       import data_analyst_agent
from agents.writer             import writer_agent
from agents.registry           import AGENT_IDS as _REGISTRY_IDS

from cognition.dual_trajectory import dual_trajectory_invoke
from cognition.deep_pipeline import run_deep_pipeline
from cognition.reflection import grounded_evaluate

_COS_SESSION_ID = "cos-session-main"
try:
    from models.cognitive_state import get_session_state as _get_cos
    _cos = _get_cos(_COS_SESSION_ID)
except Exception:
    _cos = None

VALID_AGENTS = {
    "it_networking", "python_dev", "dotnet_dev",
    "ai_ml", "knowledge_learning", "terse",
    "web_dev", "devops", "data_analyst", "writer",
}

# Catch registry drift at startup — fails loudly before any request is served.
assert VALID_AGENTS == _REGISTRY_IDS, (
    f"Registry drift detected!\n"
    f"  coordinator has: {sorted(VALID_AGENTS)}\n"
    f"  registry has:    {sorted(_REGISTRY_IDS)}\n"
    f"  missing in coordinator: {sorted(_REGISTRY_IDS - VALID_AGENTS)}\n"
    f"  missing in registry:    {sorted(VALID_AGENTS - _REGISTRY_IDS)}"
)

# Proxy performance scores for non-reflected decisions.
# Used when no reflection ran and we have no grounded quality signal.
_PROXY_PERF_NO_CONFLICT = 0.75   # brain + router agreed → reasonable quality assumed
_PROXY_PERF_CONFLICT    = 0.55   # brain overrode router → lower quality assumed

# Pre-commit acceptance barrier threshold.
# Lowered from 0.70 → 0.65 to match the recalibrated grounded_evaluate()
# scorer (base_score 0.82, syntax-only code check). Prior threshold was
# calibrated for subprocess execution which produced many false negatives
# on phi4-mini responses importing unavailable libraries.
_CRITIC_GATE_THRESHOLD = 0.65

from infrastructure.db import path as _dbpath
_GATE_DB_PATH     = _dbpath("gate")
_DECISIONS_DB     = _dbpath("decisions")
_DT_CONF_THRESHOLD = 0.52   # dual-trajectory forced when agent avg_confidence drops below this
_GATE_DB_INITED = False

def _agent_avg_confidence(agent: str, n: int = 20) -> float:
    """Return recent mean confidence for this agent from the decision log."""
    try:
        conn = sqlite3.connect(_DECISIONS_DB, timeout=5)
        rows = conn.execute(
            "SELECT confidence FROM brain_decisions WHERE final_agent=? ORDER BY id DESC LIMIT ?",
            (agent, n),
        ).fetchall()
        conn.close()
        if not rows:
            return 0.67
        return sum(r[0] for r in rows) / len(rows)
    except Exception:
        return 0.67


def _ensure_gate_db():
    global _GATE_DB_INITED
    if _GATE_DB_INITED:
        return
    con = sqlite3.connect(_GATE_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS critic_gate (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT    DEFAULT CURRENT_TIMESTAMP,
            agent             TEXT,
            agent_type        TEXT,
            task_snip         TEXT,
            score_initial     REAL,
            score_retry       REAL,
            accepted_on_first INTEGER,
            retry_improved    INTEGER
        )
    """)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    _GATE_DB_INITED = True

def _log_gate(agent: str, agent_type: str, task: str,
              score_initial: float, score_retry,
              accepted_on_first: bool) -> None:
    try:
        _ensure_gate_db()
        retry_improved = None
        if score_retry is not None:
            retry_improved = 1 if score_retry > score_initial else 0
        con = sqlite3.connect(_GATE_DB_PATH)
        con.execute(
            """INSERT INTO critic_gate
               (agent, agent_type, task_snip, score_initial, score_retry,
                accepted_on_first, retry_improved)
               VALUES (?,?,?,?,?,?,?)""",
            (agent, agent_type, (task or "")[:150],
             score_initial, score_retry,
             1 if accepted_on_first else 0,
             retry_improved),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[critic_gate] log error: {e}")


# Strong correction/negation phrases unlikely to appear in normal technical prose.
# Removed: "however,", "instead,", "rather,", "to clarify", "actually," — all common
# connectives that fire on every hedged explanation without indicating a real conflict.
_CONTRADICTION_SIGNALS = frozenset([
    "that's not", "that is not", "isn't the case", "is not the case",
    "actually it", "actually that",
    "incorrect", "not true",
    "contrary to", "opposite of", "this is wrong",
    "the correct answer", "the right answer",
])

# Common English stopwords excluded from content-word overlap calculation.
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might must can could to of in on at by "
    "for with as from or and but not it its this that these those i you "
    "he she we they what which who how when where why all any if".split()
)

def _content_words(text: str) -> set:
    return {w for w in text.lower().split() if w.isalpha() and w not in _STOPWORDS}

def _check_contradiction(agent: str, task: str, response: str) -> bool:
    """
    Returns True when the new response likely contradicts a stored memory.

    Method (no LLM call):
    1. Search memory for the agent's past answers to similar queries (score ≥ 0.78).
    2. Require a strong correction signal (negation/correction phrase, not a connective).
    3. Require ≥35% content-word overlap (stopwords stripped) with the stored memory
       to confirm the response is about the same topic before escalating.
    """
    try:
        import memory_core.db as _mdb
        hits = _mdb.search(task, top_k=5, agent_name=agent,
                           caller="contradiction_check")
        resp_lower = response.lower()

        has_signal = any(sig in resp_lower for sig in _CONTRADICTION_SIGNALS)
        if not has_signal:
            return False

        resp_content = _content_words(resp_lower)
        for hit in hits:
            if hit["score"] < 0.78:
                continue
            mem_content = _content_words(hit["content"])
            # Require ≥35% shared content words — same topic, not just similar length.
            overlap = len(mem_content & resp_content) / max(len(mem_content), 1)
            if overlap >= 0.35:
                print(
                    f"[contradiction] conflict detected for {agent} "
                    f"(mem_score={hit['score']:.2f}, content_overlap={overlap:.2f})"
                )
                return True
    except Exception as e:
        print(f"[contradiction] check error: {e}")
    return False


def _write_episodic(agent: str, task: str, performance: float,
                    reflect_level: str, regret: float, confidence: float,
                    action: str, complexity: str) -> None:
    """
    Persist this interaction as an episodic memory so future routing can learn
    from past outcomes on similar queries — not just domain knowledge.
    """
    try:
        import memory_core.db as _mdb
        outcome = (
            "successful" if performance >= 0.70
            else "failed" if performance <= 0.35
            else "partial"
        )
        _mdb.save(
            agent_name=agent,
            mem_type="episodic",
            content=task[:300] if task else "unknown",
            metadata={
                "agent":         agent,
                "action":        action,
                "complexity":    complexity,
                "outcome":       outcome,
                "performance":   round(performance, 3),
                "reflect_level": reflect_level,
                "regret":        round(regret, 3),
                "confidence":    round(confidence, 3),
            },
            quality=performance,
        )
        print(f"[episodic] {outcome} | {agent} | regret={regret:.2f}")
    except Exception as e:
        print(f"[episodic] write failed: {e}")


# ── Centralized agent runner with reflection + learning ───────
# Single control point for all agents. All learning flows through
# apply_learning_update() — never directly via adjust/update_ema.

def _run_with_reflection(invoke_fn, state: AgentState):
    result        = invoke_fn(state)
    bd            = state.get("brain_decision", {})
    agent         = state.get("next_agent", "unknown")
    confidence    = bd.get("confidence", 0.67)
    regret        = bd.get("regret",     0.0)
    conflict      = bd.get("conflict",   False)
    reflect_level = state.get("reflect_level", "none")
    gram_winner   = result.get("gram_winner", "")  # A/B or "" when GRAM not used
    gram_log      = result.get("gram_log", "")

    task         = state.get("task", "")
    response_raw = result["messages"][-1].content if result.get("messages") else ""
    run_id       = state.get("run_id", "")

    run_tracer.record_generate(run_id, agent)

    try:
        import cognition.context_snapshot as _cs
        _cs.record_routing(
            agent=agent,
            confidence=confidence,
            action=bd.get("action", "unknown"),
            complexity=bd.get("complexity", "simple"),
            reason=bd.get("reflect_type", ""),
        )
        _cs.record_prompt(agent)
    except Exception:
        pass

    # ── Critic gate: pre-commit acceptance barrier ────────────────
    # Score the raw response before it is committed or streamed.
    # If it fails the threshold, regenerate once at natural Ollama
    # non-determinism (no explicit temperature knob needed); accept
    # whichever attempt scores higher.  Max 1+1 generations — no loop.
    #
    # _critic_perf: score of the response that is actually returned.
    # Replaces hardcoded proxy (0.75/0.55) as the learning signal for
    # non-reflected requests — grounding learning on real quality.
    _critic_perf: float | None = None
    if task and response_raw:
        try:
            agent_type_gate = state.get("reflect_type", "general")
            gate_eval       = grounded_evaluate(task, response_raw, agent_type_gate)
            gate_score      = gate_eval["score"]
            if gate_score < _CRITIC_GATE_THRESHOLD:
                print(
                    f"[critic_gate] score={gate_score} < {_CRITIC_GATE_THRESHOLD} "
                    f"({agent_type_gate}) → regenerating"
                )
                retry_result = invoke_fn(state)
                retry_raw    = (
                    retry_result["messages"][-1].content
                    if retry_result.get("messages") else response_raw
                )
                retry_score  = grounded_evaluate(task, retry_raw, agent_type_gate)["score"]
                if retry_score >= gate_score:
                    result       = retry_result
                    response_raw = retry_raw
                    print(f"[critic_gate] retry score={retry_score} accepted")
                else:
                    print(
                        f"[critic_gate] retry score={retry_score} no improvement, "
                        f"keeping original"
                    )
                # Learning signal = score of whichever response we're keeping
                _critic_perf = max(gate_score, retry_score)
                run_tracer.record_critic(run_id, score_initial=gate_score,
                                         accepted_on_first=False, score_retry=retry_score)
                _log_gate(agent, agent_type_gate, task, gate_score, retry_score, False)
            else:
                _critic_perf = gate_score
                run_tracer.record_critic(run_id, score_initial=gate_score,
                                         accepted_on_first=True)
                _log_gate(agent, agent_type_gate, task, gate_score, None, True)
        except Exception as e:
            print(f"[critic_gate] gate error: {e}")

    # ── Claude enhancement pass (compound/moderate queries) ──────
    # phi4-mini generates the draft; Claude elevates it to elite quality.
    # Runs after critic gate so only passing responses are enhanced.
    _complexity = bd.get("complexity", "simple")
    if response_raw and _complexity in {"compound", "moderate"}:
        try:
            from models.smart_llm import enhance_response
            from langchain_core.messages import AIMessage as _AIMsg
            _enhanced = enhance_response(task, response_raw, agent, _complexity)
            if _enhanced and _enhanced != response_raw:
                if result.get("messages"):
                    result["messages"][-1] = _AIMsg(content=_enhanced)
                response_raw = _enhanced
                print(f"[smart_llm] ✦ Claude enhanced response for {agent} ({_complexity})")
        except Exception as _e:
            print(f"[smart_llm] enhancement error: {_e}")

    # ── Contradiction gate: escalate to full reflection if response
    # appears to contradict stored memories (no LLM call needed).
    contradiction_detected = False
    if reflect_level != "full" and response_raw:
        try:
            if _check_contradiction(agent, task, response_raw):
                reflect_level          = "full"
                reflect                = True   # noqa: F841
                contradiction_detected = True
                print(f"[coordinator] contradiction → full reflection escalated for {agent}")
        except Exception as e:
            print(f"[coordinator] contradiction gate error: {e}")

    if state.get("reflect", False) or reflect_level in {"light", "full"}:
        # ── Reflected path: grounded performance signal ───────
        try:
            from cognition.reflection import reflection_loop
            from langchain_core.messages import AIMessage
            import memory_core.db as memory_db

            response     = response_raw
            reflect_type = state.get("reflect_type", "general")
            mode         = reflect_level if reflect_level in {"light", "full"} else "full"

            refined, history = reflection_loop(task, response, agent_type=reflect_type,
                                               mode=mode)

            _refl_fallback = _critic_perf if _critic_perf is not None else 0.75
            performance    = _refl_fallback
            score_initial  = _refl_fallback
            score_final    = _refl_fallback
            reflect_delta  = 0.0
            errors         = []

            if history:
                first_eval    = history[0][1]   # (response, evaluation, issues) → eval
                last_eval     = history[-1][1]
                score_initial = first_eval.get("score", _refl_fallback)
                score_final   = last_eval.get("score",  score_initial)
                reflect_delta = round(score_final - score_initial, 4)
                performance   = score_initial  # learning uses initial quality signal
                errors        = first_eval.get("errors", [])[:3]
                try:
                    import cognition.context_snapshot as _cs
                    _cs.record_reflection(score_initial, score_final)
                except Exception:
                    pass
                # Save reflection signal as semantic memory for future routing bias.
                # quality = score so weighted retrieval surfaces high-quality reflections.
                memory_db.save(
                    agent_name=agent,
                    mem_type="reflection",
                    content=task[:300] if task else "unknown",
                    metadata={
                        "reflection_score": performance,
                        "score_initial":    score_initial,
                        "score_final":      score_final,
                        "reflect_delta":    reflect_delta,
                        "errors":           errors,
                        "agent":            agent,
                        "confidence":       confidence,
                    },
                    quality=performance,
                )

            # Single learning update with real quality signal
            apply_learning_update(
                agent=agent,
                confidence=confidence,
                regret=regret,
                performance=performance,
                metadata={
                    "source":        "reflection",
                    "reflect_type":  reflect_type,
                    "reflect_delta": reflect_delta,
                },
            )

            if refined and refined != response:
                print(f"[reflection] {reflect_type} response improved")
                result = {
                    **result,
                    "messages": [*result["messages"][:-1], AIMessage(content=refined)],
                    "result":   refined,
                }

            # Episodic memory — record outcome for future routing signals.
            _write_episodic(
                agent=agent, task=task, performance=performance,
                reflect_level=reflect_level, regret=regret, confidence=confidence,
                action=bd.get("action", "unknown"), complexity=bd.get("complexity", "simple"),
            )
        except Exception as e:
            print(f"[reflection] skipped: {e}")

    else:
        # ── Non-reflected path: critic gate score as performance signal ──
        # Use the score grounded_evaluate() assigned to the accepted response.
        # Falls back to conflict-adjusted proxy only if the gate didn't run
        # (empty task/response, or gate errored).
        if _critic_perf is not None:
            perf_signal = _critic_perf
            perf_source = "critic_gate"
        else:
            perf_signal = _PROXY_PERF_NO_CONFLICT if not conflict else _PROXY_PERF_CONFLICT
            perf_source = "proxy"
        print(f"[learning] {agent}: perf={perf_signal:.3f} source={perf_source}")
        try:
            apply_learning_update(
                agent=agent,
                confidence=confidence,
                regret=regret,
                performance=perf_signal,
                metadata={"source": perf_source, "conflict": conflict},
            )
        except Exception as e:
            print(f"[learning] update failed: {e}")

        _write_episodic(
            agent=agent, task=task, performance=perf_signal,
            reflect_level="none", regret=regret, confidence=confidence,
            action=bd.get("action", "unknown"), complexity=bd.get("complexity", "simple"),
        )

    # Propagate transparency flags into result so api.py can surface them
    updates = {}
    if contradiction_detected:
        updates["contradiction_detected"] = True
    if gram_winner:
        updates["gram_winner"] = gram_winner
        updates["gram_log"]    = gram_log
    if updates:
        result = {**result, **updates}

    # ── Post-execution step verification → event_bus ─────────────
    if task and response_raw:
        try:
            import types
            from cognition.step_verifier import verify_step as _verify
            from infrastructure.event_bus import emit as _emit, EventType as _ET

            _pseudo = types.SimpleNamespace(
                step_id          = run_id or f"{agent}-check",
                description      = task[:200],
                agent            = agent,
                uncertainty      = round(1.0 - float(bd.get("signal_conf", 0.5)), 3),
                success_criteria = "",
            )
            _vr = _verify(_pseudo, response_raw, retries_remaining=0, log=True)
            if _vr.recommendation == "continue":
                _emit(_ET.STEP_VERIFIED_PASS, {
                    "agent": agent, "score": _vr.raw_score,
                    "step_id": _pseudo.step_id,
                })
            else:
                _emit(_ET.STEP_VERIFIED_FAIL, {
                    "agent": agent, "score": _vr.raw_score,
                    "step_id": _pseudo.step_id,
                    "recommendation": _vr.recommendation,
                    "issues": _vr.issues[:3] if _vr.issues else [],
                })
                if _cos:
                    for iss in (_vr.issues or [])[:2]:
                        try:
                            _cos.add_issue(iss, step_id=_pseudo.step_id)
                        except Exception:
                            pass
        except Exception as _ve:
            print(f"[verifier] post-exec check skipped: {_ve}")

    return result


# ── Coordinator node ──────────────────────────────────────────

def coordinator_node(state: AgentState):
    task = state.get("task", "") or state["messages"][-1].content

    # Hard override — skip all reasoning
    if state.get("force_agent") and state["force_agent"] != "":
        forced = state["force_agent"]
        print(f"\n👑 Coordinator → force-routed to: [{forced}]")
        return {"next_agent": forced, "active_agent": forced}

    # ── Core brain: primary intent engine ─────────────────────
    t0 = time.time()
    try:
        decision = think(task, state)
    except Exception as e:
        print(f"[coordinator] brain failure: {e} — falling back to router")
        fallback = hybrid_router(state)
        fallback = fallback if fallback in VALID_AGENTS else "knowledge_learning"
        return {
            "next_agent":     fallback,
            "active_agent":   fallback,
            "task":           task,
            "run_id":         state.get("run_id", ""),
            "brain_decision": {"error": str(e), "fallback": fallback},
            "reflect":        False,
            "reflect_type":   "general",
            "reflect_level":  "none",
        }
    duration    = int((time.time() - t0) * 1000)
    brain_agent = decision.agent_strategy[0]

    # ── Confidence gate: very low confidence escalates to full reflection ─
    if decision.confidence < 0.40 and decision.reflect_level != "full":
        decision.reflect_level = "full"
        decision.reflect       = True
        print(f"   ⚠ Low confidence ({decision.confidence:.2f}) → full reflection forced")

    # ── Instability gate: system-level drift adds light verification ─
    # Downgraded to "light" (grounded eval only) — full LLM reflection on every
    # drifting query costs more than the quality gain on phi4-mini.
    if decision.reflect_level == "none":
        try:
            from decision.weights import drift_status
            drift = drift_status()
            if not drift["healthy"]:
                regret_signal  = drift.get("regret_mean_50", 0.0) > 0.30
                cal_errors     = drift.get("calibration_errors", {})
                cal_signal     = any(abs(e) > 0.30 for e in cal_errors.values())
                if regret_signal or cal_signal:
                    decision.reflect_level = "light"
                    decision.reflect       = True
                    reason = "regret" if regret_signal else "calibration"
                    print(f"   ⚠ Instability → light reflection added ({reason})")
        except Exception as e:
            print(f"[coordinator] instability check failed: {e}")

    # ── User reflection override (System 1/2/3 toggle) ────────
    force_rl = state.get("force_reflect_level", "")
    if force_rl in {"none", "light", "full"}:
        decision.reflect_level = force_rl
        decision.reflect       = force_rl != "none"
        print(f"   👤 User override → reflect_level={force_rl}")

    # ── Router: diagnostic comparison only ────────────────────
    router_agent = hybrid_router(state)
    conflict     = (router_agent != "coordinator" and router_agent != brain_agent)
    final_agent  = brain_agent  # brain always wins

    if conflict:
        print(
            f"\n👑 Coordinator → ⚡ conflict: router=[{router_agent}] "
            f"brain=[{brain_agent}] → brain wins"
        )
    elif router_agent != "coordinator":
        print(f"\n👑 Coordinator → [{final_agent}] (brain+router agree, {duration}ms)")
    else:
        print(f"\n👑 Coordinator → [{final_agent}] (brain decision, {duration}ms)")

    if decision.needs_plan:
        print("   Plan:")
        for step in decision.plan:
            print(f"   {step}")

    # ── Log routing decision (observability only — no learning here) ──
    run_id = state.get("run_id", "")
    log_decision(
        task=task,
        action=decision.action,
        complexity=decision.complexity,
        brain_agent=brain_agent,
        router_agent=router_agent if router_agent != "coordinator" else "none",
        final_agent=final_agent,
        conflict=conflict,
        reflect=decision.reflect,
        reflect_type=decision.reflect_type,
        duration_ms=duration,
        regret=decision.regret,
        reflect_level=decision.reflect_level,
        confidence=decision.confidence,
        run_id=run_id,
    )
    run_tracer.record_routing(
        run_id,
        brain_agent=brain_agent,
        router_agent=router_agent if router_agent != "coordinator" else "none",
        conflict=conflict,
        confidence=decision.confidence,
        regret=decision.regret,
        complexity=decision.complexity,
        reflect_level=decision.reflect_level,
    )

    # ── Deep Pipeline: compound multi-agent queries ──────────────
    # When the brain identifies a compound task with multiple real-domain agents,
    # route to the pipeline node instead of a single specialist.
    is_pipeline = (
        decision.complexity == "compound"
        and len([a for a in decision.agent_strategy
                 if a in VALID_AGENTS and a != "knowledge_learning"]) > 1
    )
    if is_pipeline:
        final_agent = "pipeline"
        print(
            f"\n👑 Coordinator → pipeline | "
            f"agents={decision.agent_strategy} | "
            f"complexity=compound"
        )

    return {
        "next_agent":   final_agent,
        "active_agent": final_agent,
        "task":         task,
        "run_id":       state.get("run_id", ""),
        "brain_decision": {
            "intent":         decision.intent,
            "action":         decision.action,
            "complexity":     decision.complexity,
            "agent_strategy": decision.agent_strategy,
            "needs_plan":     decision.needs_plan,
            "plan":           decision.plan,
            "confidence":     decision.confidence,
            "low_confidence": decision.confidence < 0.40,
            "regret":         decision.regret,
            "conflict":       conflict,
            "signal_domain":    decision.signal_domain,
            "signal_shape":     decision.signal_shape,
            "signal_verbosity": decision.signal_verbosity,
            "signal_conf":      decision.signal_conf,
            "pipeline":         is_pipeline,
        },
        "reflect":       decision.reflect,
        "reflect_type":  decision.reflect_type,
        "reflect_level": decision.reflect_level,
        "model_tier":    {"compound": "reasoning", "moderate": "standard"}.get(
            decision.complexity, "fast"
        ),
    }


# ── Routing function ──────────────────────────────────────────
# Reads the decision already made by coordinator_node.
# No re-routing — the brain already decided.

def route_to_agent(state: AgentState) -> str:
    agent = state.get("next_agent", "knowledge_learning")
    if agent == "pipeline":
        return "pipeline"
    return agent if agent in VALID_AGENTS else "knowledge_learning"


# ── Specialist wrapper nodes ──────────────────────────────────
# All agents pass through _run_with_reflection which handles both
# the reflection path and the proxy learning update path.

def run_it(state):        return _run_with_reflection(it_agent.invoke, state)

def run_python(state):
    avg_conf = _agent_avg_confidence("python_dev")
    force_dt = avg_conf < _DT_CONF_THRESHOLD
    if force_dt:
        print(f"[coordinator] python_dev avg_conf={avg_conf:.2f} < {_DT_CONF_THRESHOLD} → dual-trajectory forced")
    return _run_with_reflection(
        lambda s: dual_trajectory_invoke(python_agent.invoke, s, PYTHON_SYSTEM_PROMPT, force=force_dt),
        state,
    )

def run_dotnet(state):
    avg_conf = _agent_avg_confidence("dotnet_dev")
    force_dt = avg_conf < _DT_CONF_THRESHOLD
    if force_dt:
        print(f"[coordinator] dotnet_dev avg_conf={avg_conf:.2f} < {_DT_CONF_THRESHOLD} → dual-trajectory forced")
    return _run_with_reflection(
        lambda s: dual_trajectory_invoke(dotnet_agent.invoke, s, DOTNET_SYSTEM_PROMPT, force=force_dt),
        state,
    )
def run_ai_ml(state):       return _run_with_reflection(ai_ml_agent.invoke, state)
def run_knowledge(state):   return _run_with_reflection(knowledge_agent.invoke, state)
def run_terse(state):       return _run_with_reflection(terse_agent.invoke, state)
def run_web_dev(state):     return _run_with_reflection(web_dev_agent.invoke, state)
def run_devops(state):      return _run_with_reflection(devops_agent.invoke, state)
def run_data_analyst(state):return _run_with_reflection(data_analyst_agent.invoke, state)
def run_writer(state):      return _run_with_reflection(writer_agent.invoke, state)


def run_pipeline(state: AgentState):
    """
    Deep Pipeline node — executes compound tasks through multiple agents.
    Each agent runs through its own _run_with_reflection wrapper so
    learning + episodic memory work unchanged.
    """
    bd      = state.get("brain_decision", {})
    agents  = [a for a in bd.get("agent_strategy", []) if a in VALID_AGENTS]
    task    = state.get("task", "")

    agent_runner_map = {
        "python_dev":        run_python,
        "dotnet_dev":        run_dotnet,
        "it_networking":     run_it,
        "ai_ml":             run_ai_ml,
        "knowledge_learning": run_knowledge,
        "terse":             run_terse,
        "web_dev":           run_web_dev,
        "devops":            run_devops,
        "data_analyst":      run_data_analyst,
        "writer":            run_writer,
    }

    print(f"[pipeline] compound task → {agents}")
    result = run_deep_pipeline(
        query=task,
        agents=agents,
        state=state,
        agent_runner_map=agent_runner_map,
    )
    if _cos and result.get("plan"):
        try:
            _cos.set_plan(result["plan"])
        except Exception:
            pass
    # Keep active_agent as "pipeline" so api.py labels this correctly
    return {**result, "active_agent": "pipeline", "next_agent": "pipeline"}


# ── Build graph ───────────────────────────────────────────────

def build_coordinator():
    graph = StateGraph(AgentState)

    graph.add_node("coordinator",        coordinator_node)
    graph.add_node("it_networking",      run_it)
    graph.add_node("python_dev",         run_python)
    graph.add_node("dotnet_dev",         run_dotnet)
    graph.add_node("ai_ml",              run_ai_ml)
    graph.add_node("knowledge_learning", run_knowledge)
    graph.add_node("terse",              run_terse)
    graph.add_node("web_dev",            run_web_dev)
    graph.add_node("devops",             run_devops)
    graph.add_node("data_analyst",       run_data_analyst)
    graph.add_node("writer",             run_writer)
    graph.add_node("pipeline",           run_pipeline)

    graph.add_edge(START, "coordinator")

    graph.add_conditional_edges(
        "coordinator",
        route_to_agent,
        {
            "it_networking":      "it_networking",
            "python_dev":         "python_dev",
            "dotnet_dev":         "dotnet_dev",
            "ai_ml":              "ai_ml",
            "knowledge_learning": "knowledge_learning",
            "terse":              "terse",
            "web_dev":            "web_dev",
            "devops":             "devops",
            "data_analyst":       "data_analyst",
            "writer":             "writer",
            "pipeline":           "pipeline",
        }
    )

    for node in list(VALID_AGENTS) + ["pipeline"]:
        graph.add_edge(node, END)

    return graph.compile()


coordinator = build_coordinator()
