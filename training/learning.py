# ~/agentic-ai/learning.py
# ─────────────────────────────────────────────────────────────
# THE single learning update pathway.
#
# All weight changes flow through apply_learning_update().
# Nothing else writes to agent_weights directly.
#
# Signal contract:
#   performance — ground truth quality [0.0, 1.0]
#                 reflected:     reflection_score from grounded_evaluate()
#                 not reflected: critic_gate score (grounded_evaluate() on
#                                accepted response); falls back to proxy
#                                (0.75 no-conflict / 0.55 conflict) only
#                                when task/response was empty or gate errored
#   regret      — routing optimality gap: max(alt_confs) - chosen_conf
#   confidence  — brain's prior estimate for this agent
#
# Derived inside (never by callers):
#   calibration_bias  = EMA(confidence - performance)
#   learning_signal   = performance - 0.5 * regret
#   instability       = 1 - (1-regret)(1-|cal_bias|)(1-weight_var)  (soft-OR)
#   adaptive_alpha    = 0.05 * f(instability)
#   delta             = clamp(alpha * (signal - weight), -0.02, +0.02)
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import math

from decision.weights import (
    adjust,
    load      as load_weights,
    update_calibration,
    get_calibration,
    KNOWN_AGENTS, BOUNDS,
)
from infrastructure.math_metrics import instability_conjunctive

BASE_ALPHA      = 0.05
SLOW_THRESHOLD  = 0.60   # log threshold: alpha has dropped below ~40% of BASE_ALPHA
_ALPHA_STEEPNESS = 8.0   # sigmoid steepness — controls how sharply alpha decays with I


def apply_learning_update(
    agent:       str,
    confidence:  float,
    regret:      float,
    performance: float,
    metadata:    dict | None = None,
) -> dict:
    """
    The system's only weight-update entry point.

    agent       — which agent handled the request
    confidence  — brain's pre-decision confidence score
    regret      — routing optimality gap (0.0 for single-domain tasks)
    performance — quality of the response [0.0, 1.0]:
                    reflected tasks:     reflection_score from grounded_evaluate()
                    non-reflected tasks: proxy based on routing agreement
    metadata    — optional context dict (stored in returned summary)

    Returns a summary dict with every computed intermediate value.
    This is the authoritative record of what happened and why.
    """
    # ── A. Calibration ────────────────────────────────────────
    # Update rolling EMA of (confidence, performance) divergence.
    update_calibration(agent, confidence, performance)
    cal      = get_calibration(agent)
    cal_bias = cal["error"] if cal["count"] >= 5 else 0.0  # avg_conf - avg_perf

    # ── B. Learning signal ────────────────────────────────────
    # Penalizes performance by routing regret:
    # high regret = we might have gotten better results elsewhere.
    learning_signal = round(performance - 0.5 * regret, 4)

    # ── C. Instability composite ──────────────────────────────
    # Three sources of uncertainty:
    #   routing regret     — was this even the right agent?   (OCAC A1)
    #   calibration bias   — do confidence estimates track reality?  (OCAC A3)
    #   weight variance    — are agents diverging from neutral / is the
    #                        update still a contraction?       (OCAC A2)
    # The OCAC "H theorem" formalization proves A1/A2/A3 are each *individually
    # necessary* for stability (each has its own counterexample), so they are
    # conjunctive: any one failing is destabilising. A weighted average would
    # let a healthy term mask a failure, so we use the soft-OR
    # I = 1 - ∏(1 - tᵢ), which spikes as soon as a single condition degrades.
    weights  = load_weights()
    vals     = list(weights.values())
    wt_mean  = sum(vals) / len(vals) if vals else 1.0
    wt_var   = sum((v - wt_mean) ** 2 for v in vals) / len(vals) if vals else 0.0
    instability = round(instability_conjunctive(regret, cal_bias, wt_var), 4)

    # ── D. Adaptive alpha ─────────────────────────────────────
    # Smooth sigmoid decay: alpha(I) = BASE_ALPHA / (1 + exp(k*(I - 0.5)))
    # At I=0: ~BASE_ALPHA. At I=0.5: BASE_ALPHA/2. At I≥0.9: effectively 0.
    # No hard steps — gradient flows through the entire instability range.
    alpha = BASE_ALPHA / (1.0 + math.exp(_ALPHA_STEEPNESS * (instability - 0.5)))
    if alpha < 2e-3:
        alpha = 0.0
        print(
            f"[learning] {agent}: frozen "
            f"(instability={instability:.3f}, "
            f"regret={regret:.3f}, cal_bias={cal_bias:.3f})"
        )

    # ── E. Bounded weight update ──────────────────────────────
    current = weights.get(agent, 1.0)
    lo, hi  = BOUNDS
    if alpha > 0:
        raw_delta     = alpha * (learning_signal - current)
        bounded_delta = max(-0.02, min(0.02, raw_delta))
        new_weight    = round(max(lo, min(hi, current + bounded_delta)), 4)
        adjust(agent, bounded_delta)
    else:
        bounded_delta = 0.0
        new_weight    = current

    # ── F. Decay non-chosen agents 0.001 toward neutral ───────
    # Prevents stale high/low weights from agents not recently selected.
    for a in KNOWN_AGENTS:
        if a != agent:
            w = weights.get(a, 1.0)
            if abs(w - 1.0) >= 0.001:
                adjust(a, -0.001 if w > 1.0 else +0.001)

    summary = {
        "agent":            agent,
        "confidence":       confidence,
        "performance":      performance,
        "regret":           regret,
        "learning_signal":  learning_signal,
        "cal_bias":         round(cal_bias, 4),
        "wt_variance":      round(wt_var, 5),
        "instability":      instability,
        "alpha":            round(alpha, 4),
        "delta":            round(bounded_delta, 4),
        "weight_before":    current,
        "weight_after":     new_weight,
        "frozen":           alpha == 0.0,
        "metadata":         metadata or {},
    }

    if instability >= SLOW_THRESHOLD and alpha > 0.0:
        print(
            f"[learning] {agent}: slow mode "
            f"(instability={instability:.3f}, alpha={alpha:.4f}, "
            f"signal={learning_signal:.3f}, delta={bounded_delta:.4f})"
        )

    # Persist the weight transition so drift_status can reconstruct per-agent
    # tracks for the signed lens-of-stability test (math_metrics.drift_status_v2).
    # Best-effort: a telemetry failure must never break the learning path.
    if new_weight != current:
        try:
            from infrastructure.event_bus import emit, EventType
            emit(EventType.ROUTING_WEIGHT_CHANGED, {
                "agent":         agent,
                "weight_before": current,
                "weight_after":  new_weight,
                "delta":         round(bounded_delta, 4),
                # α at this step IS the per-agent contraction modulus
                # (K = 1−α); neutral_mode_drift needs it to find the
                # slowest-contracting mode. (weights._neutral_mode)
                "alpha":         round(alpha, 4),
            })
        except Exception as e:
            print(f"[learning] weight-change emit failed: {e}")

    return summary
