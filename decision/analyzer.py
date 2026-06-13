# ~/agentic-ai/decision_analyzer.py
# ─────────────────────────────────────────────────────────────
# Reads decision events and adjusts agent weights.
#
# Signal semantics (no human feedback required):
#   no conflict → brain choice agrees with keyword evidence → reinforce
#   conflict    → brain over-selected this domain → penalize
#   reflect     → response needed quality checking → mild penalty
#
# Weight change per decision:
#   no conflict, no reflect  →  +0.02
#   no conflict, reflect     →  +0.01
#   conflict, no reflect     →  -0.02
#   conflict, reflect        →  -0.03
#
# These are deliberately small. Weights move over dozens of decisions,
# not after one. A single conflict won't collapse an agent's weight.
# ─────────────────────────────────────────────────────────────

from decision.weights import adjust, load as load_weights, _defaults, BOUNDS, KNOWN_AGENTS


def analyze(brain_agent: str, router_agent: str,
            conflict: bool, reflect: bool) -> None:
    """
    DEPRECATED — no longer called by coordinator.
    Weight updates now flow through learning.apply_learning_update().
    Kept for backward compatibility with rebuild_from_history().
    """
    # This path is kept only so rebuild_from_history() can replay old decisions
    # using the pre-consolidation logic. New decisions use learning.py exclusively.
    delta = -0.02 if conflict else +0.02
    if reflect:
        delta -= 0.01
    adjust(brain_agent, delta)

    weights = load_weights()
    for agent in KNOWN_AGENTS:
        if agent != brain_agent:
            current = weights.get(agent, 1.0)
            if abs(current - 1.0) >= 0.001:
                adjust(agent, -0.001 if current > 1.0 else +0.001)


def rebuild_from_history(n: int = 500) -> dict:
    """
    Recompute weights from the last n logged decisions, starting from
    defaults. Useful after resetting the weights file or diagnosing drift.
    Returns the recomputed weight dict (does NOT save it automatically).
    """
    from decision.log import recent

    rows    = recent(n)
    weights = _defaults()
    lo, hi  = BOUNDS

    for row in reversed(rows):      # oldest → newest
        agent    = row.get("final_agent", "")
        conflict = row.get("conflict", False)
        reflect  = row.get("reflect",  False)
        if agent not in weights:
            continue
        delta = -0.02 if conflict else +0.02
        if reflect:
            delta -= 0.01
        weights[agent] = round(max(lo, min(hi, weights[agent] + delta)), 4)

    return weights


def summary() -> dict:
    """
    Per-agent stats: decision history + weights + calibration + regret.
    Used by the /decisions endpoint and the Brain tab dashboard.
    """
    from decision.log import recent, agent_regret_mean
    from decision.weights import to_confidence, get_all_calibration

    rows    = recent(200)
    weights = load_weights()
    cal_all = get_all_calibration()
    stats: dict = {}

    for row in rows:
        a = row.get("final_agent", "unknown")
        if a not in stats:
            stats[a] = {"count": 0, "conflicts": 0, "reflected": 0}
        stats[a]["count"]     += 1
        stats[a]["conflicts"] += int(row.get("conflict", False))
        stats[a]["reflected"] += int(row.get("reflect",  False))

    for a, s in stats.items():
        n   = s["count"]
        cal = cal_all.get(a, {})
        s["weight"]          = weights.get(a, 1.0)
        s["stability"]       = round(1.0 - s["conflicts"] / n, 3) if n else 1.0
        s["confidence"]      = to_confidence(a)
        s["cal_error"]       = round(abs(cal.get("error", 0.0)), 3)
        s["avg_reflection"]  = cal.get("avg_reflection", None)
        s["cal_samples"]     = cal.get("count", 0)
        s["avg_regret"]      = agent_regret_mean(a, 50)

    return stats
