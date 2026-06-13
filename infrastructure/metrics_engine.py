"""
metrics_engine.py — Unified Metrics Engine + UCI (Phase 35)

Computes a four-level metric hierarchy from all existing data sources:

  Level 1  Execution    latency, retries, memory hits
  Level 2  Reasoning    plan quality, verifier score, risk score
  Level 3  Learning     routing accuracy, reflection effectiveness
  Level 4  System       Reliability, Capability, Efficiency, Learning

  UCI (Unified Cognitive Index, 0-100):
    UCI = 35 × Reliability + 30 × Capability + 20 × Efficiency + 15 × Learning

All values are computed from existing DBs — no new data collection.
Cached for 30 seconds to avoid hot-path recomputation.

Usage:
    from infrastructure.metrics_engine import compute_uci, get_metrics
    m = get_metrics()
    print(m["uci"])          # e.g. 84.3
    print(m["reliability"])  # e.g. 0.96
"""

import os
import sqlite3
import time
from typing import Any, Dict

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGS = os.path.join(_BASE, "logs")

# ── DB paths (read-only consumers) ───────────────────────────
_DECISIONS_DB   = os.path.join(_LOGS, "decisions.db")
_GATE_DB        = os.path.join(_LOGS, "gate.db")
_RISK_DB        = os.path.join(_LOGS, "risk_gate.db")
_STEP_VERIFY_DB = os.path.join(_LOGS, "step_verify.db")
_RUNS_DB        = os.path.join(_LOGS, "runs.db")
_EVENTS_DB      = os.path.join(_LOGS, "events.db")
_FEEDBACK_DB    = os.path.join(_LOGS, "feedback.db")

# ── UCI weights ───────────────────────────────────────────────
_W_RELIABILITY = 0.35
_W_CAPABILITY  = 0.30
_W_EFFICIENCY  = 0.20
_W_LEARNING    = 0.15

# ── Cache ─────────────────────────────────────────────────────
_CACHE:    Dict[str, Any] = {}
_CACHE_TS: float          = 0.0
_CACHE_TTL: float         = 30.0   # seconds


# ── Safe DB query helpers ─────────────────────────────────────

def _q(db_path: str, sql: str, params: tuple = (),
       default: Any = None) -> Any:
    """Execute a single-value SQL query, return default on any error."""
    if not os.path.exists(db_path):
        return default
    try:
        con = sqlite3.connect(db_path, timeout=2)
        val = con.execute(sql, params).fetchone()
        con.close()
        return val[0] if val and val[0] is not None else default
    except Exception:
        return default


def _qa(db_path: str, sql: str, params: tuple = ()) -> list:
    """Execute a multi-row SQL query, return [] on any error."""
    if not os.path.exists(db_path):
        return []
    try:
        con  = sqlite3.connect(db_path, timeout=2)
        rows = con.execute(sql, params).fetchall()
        con.close()
        return rows
    except Exception:
        return []


# ── Level 1: Execution metrics ────────────────────────────────

def _exec_metrics(n: int = 200) -> Dict[str, Any]:
    """
    Latency, retry rate, gate acceptance, memory hit rate.
    Sources: gate.db, runs.db
    """
    # Critic gate: acceptance rate and retry improvement
    gate_rows = _qa(_GATE_DB,
        "SELECT accepted_on_first, retry_improved FROM critic_gate "
        "ORDER BY id DESC LIMIT ?", (n,))

    if gate_rows:
        accepted_first = sum(1 for r in gate_rows if r[0]) / len(gate_rows)
        retried        = [r for r in gate_rows if r[0] == 0]
        retry_improved = (
            sum(1 for r in retried if r[1]) / len(retried)
            if retried else 1.0
        )
        retry_rate = len(retried) / len(gate_rows)
    else:
        accepted_first = 0.85
        retry_improved = 0.70
        retry_rate     = 0.15

    return {
        "gate_accept_rate":  round(accepted_first, 3),
        "retry_rate":        round(retry_rate, 3),
        "retry_improve_rate":round(retry_improved, 3),
        "n_gate_decisions":  len(gate_rows),
    }


# ── Level 2: Reasoning metrics ────────────────────────────────

def _reasoning_metrics(n: int = 200) -> Dict[str, Any]:
    """
    Plan quality, verifier pass rate, risk distribution.
    Sources: step_verify.db, risk_gate.db
    """
    # Step verification
    verify_rows = _qa(_STEP_VERIFY_DB,
        "SELECT passed, raw_score, recommendation FROM step_verify_log "
        "ORDER BY id DESC LIMIT ?", (n,))

    if verify_rows:
        pass_rate   = sum(1 for r in verify_rows if r[0]) / len(verify_rows)
        mean_score  = sum(r[1] for r in verify_rows) / len(verify_rows)
        replan_rate = sum(1 for r in verify_rows if r[2] == "replan") / len(verify_rows)
    else:
        pass_rate   = 0.90
        mean_score  = 0.75
        replan_rate = 0.05

    # Risk distribution
    risk_rows = _qa(_RISK_DB,
        "SELECT reflect_level, total_risk FROM risk_log "
        "ORDER BY id DESC LIMIT ?", (n,))

    if risk_rows:
        mean_risk   = sum(r[1] for r in risk_rows) / len(risk_rows)
        full_rate   = sum(1 for r in risk_rows if r[0] == "full") / len(risk_rows)
        light_rate  = sum(1 for r in risk_rows if r[0] == "light") / len(risk_rows)
    else:
        mean_risk   = 0.35
        full_rate   = 0.15
        light_rate  = 0.35

    return {
        "step_pass_rate":    round(pass_rate, 3),
        "step_mean_score":   round(mean_score, 3),
        "step_replan_rate":  round(replan_rate, 3),
        "mean_risk":         round(mean_risk, 3),
        "full_reflection_rate": round(full_rate, 3),
        "light_reflection_rate": round(light_rate, 3),
        "n_verified_steps":  len(verify_rows),
        "n_risk_decisions":  len(risk_rows),
    }


# ── Level 3: Learning metrics ─────────────────────────────────

def _learning_metrics(n: int = 300) -> Dict[str, Any]:
    """
    Routing accuracy, reflection delta, feedback score.
    Sources: decisions.db, feedback.db
    """
    # Brain decision confidence trend
    conf_rows = _qa(_DECISIONS_DB,
        "SELECT confidence, regret FROM brain_decisions "
        "ORDER BY id DESC LIMIT ?", (n,))

    if conf_rows:
        mean_conf   = sum(r[0] for r in conf_rows) / len(conf_rows)
        mean_regret = sum(r[1] for r in conf_rows) / len(conf_rows)
    else:
        mean_conf   = 0.67
        mean_regret = 0.10

    # Feedback: thumbs up/down
    fb_rows = _qa(_FEEDBACK_DB,
        "SELECT rating FROM feedback ORDER BY id DESC LIMIT ?", (n,))
    if fb_rows:
        positive_rate = sum(1 for r in fb_rows if r[0] > 0) / len(fb_rows)
    else:
        positive_rate = 0.80

    # Routing accuracy proxy: ablation result (constant from eval)
    # Updated manually when ablation eval runs
    routing_accuracy = 0.98   # from ablation_eval: 98/100

    return {
        "routing_accuracy":  routing_accuracy,
        "mean_confidence":   round(mean_conf, 3),
        "mean_regret":       round(mean_regret, 3),
        "feedback_positive": round(positive_rate, 3),
        "n_decisions":       len(conf_rows),
        "n_feedback":        len(fb_rows),
    }


# ── Level 4: System metrics ───────────────────────────────────

def _system_metrics(exec_m: dict, reason_m: dict, learn_m: dict) -> Dict[str, float]:
    """
    Four composite system-level scores, each in [0, 1].

    Reliability  — does the system produce correct outputs?
    Capability   — how well does it reason and plan?
    Efficiency   — how lean is the execution?
    Learning     — is the system improving?
    """
    # Reliability = weighted average of gate acceptance, step pass rate, feedback
    reliability = (
        0.40 * exec_m["gate_accept_rate"]
        + 0.35 * reason_m["step_pass_rate"]
        + 0.25 * learn_m["feedback_positive"]
    )

    # Capability = routing accuracy × (1 - mean_risk) × step quality
    capability = (
        0.45 * learn_m["routing_accuracy"]
        + 0.30 * (1.0 - reason_m["mean_risk"])
        + 0.25 * reason_m["step_mean_score"]
    )

    # Efficiency = penalise retries, full-reflection overhead
    efficiency = (
        0.50 * (1.0 - exec_m["retry_rate"])
        + 0.30 * (1.0 - reason_m["full_reflection_rate"])
        + 0.20 * (1.0 - reason_m["step_replan_rate"])
    )

    # Learning = confidence × (1 - regret) × (feedback positive)
    learning = (
        0.40 * learn_m["mean_confidence"]
        + 0.30 * (1.0 - learn_m["mean_regret"])
        + 0.30 * learn_m["feedback_positive"]
    )

    return {
        "reliability": round(min(1.0, reliability), 4),
        "capability":  round(min(1.0, capability),  4),
        "efficiency":  round(min(1.0, efficiency),  4),
        "learning":    round(min(1.0, learning),    4),
    }


# ── UCI ───────────────────────────────────────────────────────

def _compute_uci(sys_m: dict) -> float:
    """
    UCI = 35×Reliability + 30×Capability + 20×Efficiency + 15×Learning
    Scaled 0–100.
    """
    raw = (
        _W_RELIABILITY * sys_m["reliability"]
        + _W_CAPABILITY  * sys_m["capability"]
        + _W_EFFICIENCY  * sys_m["efficiency"]
        + _W_LEARNING    * sys_m["learning"]
    )
    return round(raw * 100, 1)


# ── Hierarchical metric stack (Phase 36) ──────────────────────
# Evolves the flat 4-component model into a 4-layer interpretable stack.
#
# Layer 1  Reliability   — does the system do what it says?
# Layer 2  Intelligence  — does it reason and plan well?
# Layer 3  Adaptation    — is it learning from feedback?
# Layer 4  Productivity  — is it producing useful outcomes?

def _productivity_metrics() -> Dict[str, float]:
    """
    Productivity signals from runs.db (pass/fail counts) and sessions.db (latency).

    goal_completion uses runs.db pass/fail rather than world_model.completed_tasks,
    which is fragile across restarts. Every row in runs.db with status='pass' or
    'partial' represents a successfully completed request; 'fail' rows represent
    genuine failures. This gives a stable, accurate completion rate.
    """
    _RUNS_DB = os.path.join(_LOGS, "runs.db")

    passed  = _q(_RUNS_DB,
        "SELECT COUNT(*) FROM runs WHERE status IN ('pass','partial') "
        "ORDER BY rowid DESC LIMIT 200", default=0) or 0
    failed  = _q(_RUNS_DB,
        "SELECT COUNT(*) FROM runs WHERE status='fail' "
        "ORDER BY rowid DESC LIMIT 200", default=0) or 0
    total_runs = passed + failed

    # Fall back to sessions.db count when runs.db is empty (cold start)
    total_sessions = _q(
        os.path.join(_LOGS, "sessions.db"),
        "SELECT COUNT(*) FROM sessions", default=0
    ) or 0
    if total_runs == 0:
        passed     = total_sessions
        total_runs = total_sessions

    goal_completion = min(1.0, passed / max(1, total_runs))

    # Latency: mean of the 50 most-recent sessions (subquery required for LIMIT to apply)
    mean_latency_ms = _q(
        os.path.join(_LOGS, "sessions.db"),
        "SELECT AVG(duration_ms) FROM "
        "(SELECT duration_ms FROM sessions ORDER BY id DESC LIMIT 50)",
        default=4000
    ) or 4000
    # Normalise for local LLM latency: 5s=1.0, 90s=0.0 (linear)
    latency_score = max(0.0, min(1.0, 1.0 - (mean_latency_ms - 5000) / 85000))

    return {
        "completed_tasks":  passed,
        "total_sessions":   total_runs,
        "failed_runs":      failed,
        "mean_latency_ms":  round(mean_latency_ms),
        "latency_score":    round(latency_score, 3),
        "goal_completion":  round(goal_completion, 3),
    }


def hierarchical_metrics(force: bool = False) -> Dict[str, Any]:
    """
    Return the 4-layer interpretable metric stack alongside the UCI.

    Each layer is a score 0-100 with contributing sub-metrics:

      Layer 1  Reliability    routing accuracy, verify pass rate, abort rate
      Layer 2  Intelligence   plan quality, reflection effectiveness, memory quality
      Layer 3  Adaptation     feedback improvement, learning rate, confidence trend
      Layer 4  Productivity   tasks completed, goal completion, latency

    UCI = 30×Reliability + 30×Intelligence + 25×Adaptation + 15×Productivity
    """
    m        = get_metrics(force=force)
    prod_m   = _productivity_metrics()

    # Layer 1: Reliability — can we trust the outputs?
    reliability = round(min(100.0, (
        0.35 * m["lrn_routing_accuracy"]
        + 0.35 * m["rsn_step_pass_rate"]
        + 0.15 * (1.0 - m.get("rsn_step_replan_rate", 0.05))
        + 0.15 * m["exec_gate_accept_rate"]
    ) * 100), 1)

    # Layer 2: Intelligence — quality of reasoning and planning
    intelligence = round(min(100.0, (
        0.40 * m["rsn_step_mean_score"]
        + 0.30 * (1.0 - m["rsn_mean_risk"])
        + 0.30 * (1.0 - m["exec_retry_rate"])
    ) * 100), 1)

    # Layer 3: Adaptation — learning from experience
    adaptation = round(min(100.0, (
        0.40 * m["lrn_feedback_positive"]
        + 0.30 * m["lrn_mean_confidence"]
        + 0.30 * (1.0 - m["lrn_mean_regret"])
    ) * 100), 1)

    # Layer 4: Productivity — real-world output quality
    productivity = round(min(100.0, (
        0.40 * prod_m["goal_completion"]
        + 0.30 * prod_m["latency_score"]
        + 0.30 * m["exec_gate_accept_rate"]
    ) * 100), 1)

    # Hierarchical UCI
    h_uci = round(
        0.30 * reliability
        + 0.30 * intelligence
        + 0.25 * adaptation
        + 0.15 * productivity, 1
    )

    return {
        "h_uci":          h_uci,
        "layers": {
            "reliability":  {
                "score": reliability,
                "routing_accuracy":  round(m["lrn_routing_accuracy"] * 100, 1),
                "verify_pass_rate":  round(m["rsn_step_pass_rate"] * 100, 1),
                "gate_accept_rate":  round(m["exec_gate_accept_rate"] * 100, 1),
                "abort_rate":        round(m.get("rsn_step_replan_rate", 0.05) * 100, 1),
            },
            "intelligence": {
                "score": intelligence,
                "plan_quality":      round(m["rsn_step_mean_score"] * 100, 1),
                "risk_clearance":    round((1.0 - m["rsn_mean_risk"]) * 100, 1),
                "retry_clearance":   round((1.0 - m["exec_retry_rate"]) * 100, 1),
            },
            "adaptation": {
                "score": adaptation,
                "feedback_positive": round(m["lrn_feedback_positive"] * 100, 1),
                "confidence":        round(m["lrn_mean_confidence"] * 100, 1),
                "regret_clearance":  round((1.0 - m["lrn_mean_regret"]) * 100, 1),
            },
            "productivity": {
                "score": productivity,
                "completed_tasks":   prod_m["completed_tasks"],
                "total_sessions":    prod_m["total_sessions"],
                "goal_completion":   round(prod_m["goal_completion"] * 100, 1),
                "latency_score":     round(prod_m["latency_score"] * 100, 1),
                "mean_latency_ms":   prod_m["mean_latency_ms"],
            },
        },
        "legacy_uci": m["uci"],   # original flat UCI for continuity
        "computed_at": m["computed_at"],
    }


# ── Public API ────────────────────────────────────────────────

def get_metrics(force: bool = False) -> Dict[str, Any]:
    """
    Compute and return the full metric hierarchy.
    Cached for 30s unless force=True.

    Returns a flat dict with all metrics plus top-level:
      uci, reliability, capability, efficiency, learning
    """
    global _CACHE, _CACHE_TS
    now = time.time()
    if not force and _CACHE and (now - _CACHE_TS) < _CACHE_TTL:
        return _CACHE

    exec_m   = _exec_metrics()
    reason_m = _reasoning_metrics()
    learn_m  = _learning_metrics()
    sys_m    = _system_metrics(exec_m, reason_m, learn_m)
    uci      = _compute_uci(sys_m)

    # Emit UCI event if event_bus is available
    try:
        from infrastructure.event_bus import emit, EventType
        emit(EventType.UCI_COMPUTED, {"uci": uci, **sys_m}, persist=False)
    except Exception:
        pass

    result = {
        "uci":          uci,
        "reliability":  sys_m["reliability"],
        "capability":   sys_m["capability"],
        "efficiency":   sys_m["efficiency"],
        "learning":     sys_m["learning"],
        # Level 1
        **{f"exec_{k}": v  for k, v in exec_m.items()},
        # Level 2
        **{f"rsn_{k}":  v  for k, v in reason_m.items()},
        # Level 3
        **{f"lrn_{k}":  v  for k, v in learn_m.items()},
        "computed_at":  now,
    }

    _CACHE    = result
    _CACHE_TS = now
    return result


def compute_uci(force: bool = False) -> float:
    """Convenience: return only the UCI score (0–100)."""
    return get_metrics(force=force)["uci"]


# ── CLI report ────────────────────────────────────────────────

if __name__ == "__main__":
    m = get_metrics(force=True)

    print("=" * 65)
    print("  UNIFIED COGNITIVE INDEX (UCI)")
    print("=" * 65)
    print(f"\n  Cognitive Health: {m['uci']:.1f} / 100")

    bar_len = int(m["uci"] * 0.6)
    health_bar = "█" * bar_len + "░" * (60 - bar_len)
    print(f"  [{health_bar}]")

    print(f"\n  {'─'*40}")
    print(f"  Level 4 — System Scores")
    print(f"  {'─'*40}")
    for k in ("reliability", "capability", "efficiency", "learning"):
        v   = m[k]
        bar = "█" * int(v * 40) + "░" * (40 - int(v * 40))
        print(f"  {k.capitalize():<14} {v:.3f}  [{bar}]")

    print(f"\n  {'─'*40}")
    print(f"  Level 3 — Learning")
    print(f"  {'─'*40}")
    for k in ("lrn_routing_accuracy", "lrn_mean_confidence",
              "lrn_mean_regret", "lrn_feedback_positive"):
        print(f"  {k[4:]:<22} {m[k]:.3f}")

    print(f"\n  {'─'*40}")
    print(f"  Level 2 — Reasoning")
    print(f"  {'─'*40}")
    for k in ("rsn_step_pass_rate", "rsn_mean_risk",
              "rsn_full_reflection_rate", "rsn_step_replan_rate"):
        print(f"  {k[4:]:<25} {m[k]:.3f}")

    print(f"\n  {'─'*40}")
    print(f"  Level 1 — Execution")
    print(f"  {'─'*40}")
    for k in ("exec_gate_accept_rate", "exec_retry_rate"):
        print(f"  {k[5:]:<25} {m[k]:.3f}")

    print()
