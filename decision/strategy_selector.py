"""
strategy_selector.py — expected-value strategy selection (Decision Intelligence, #1).

Strategy memory answers "what worked before" as raw stats. This turns those
stats into a *decision*: for a task class, which strategy maximizes expected
value once you trade success probability against cost and latency?

    EV(strategy) = value · P(success) − latency_penalty − cost_penalty

Two honesty guards make this trustworthy on sparse local data:

  * **Shrinkage.** P(success) is smoothed with a Beta(α,β) prior, so a lucky 1/1
    reads as ~0.67, not 1.0 — a strategy must earn confidence with attempts.
  * **Abstention.** With no evidence for a task class, select() returns None so
    the caller keeps its current router instead of acting on a guess.

The weights/budgets are documented heuristics, not learned — this is the engine
the decision-intelligence layer needs; calibrating the constants (and proving it
beats the baseline on held-out tasks) is the remaining work for #1.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from decision.strategy_memory import StrategyMemory, StrategyStat

# ── Tunable policy constants (heuristics — calibrate later) ──────────
VALUE_SUCCESS = 1.0        # reward for a correct answer, in "value units"
LATENCY_WEIGHT = 0.30      # max value a strategy can lose to latency
LATENCY_BUDGET_MS = 30_000 # latency at/above which the full LATENCY_WEIGHT applies
COST_WEIGHT = 0.0          # no reliable token-cost signal yet → cost penalty off
COST_BUDGET = 1_000.0
# Beta prior: (1,1) = Laplace/uniform → 1/1 shrinks to 2/3, 0/0 sits at 1/2.
PRIOR_ALPHA = 1.0
PRIOR_BETA = 1.0


@dataclass
class EVEstimate:
    strategy: str
    attempts: int
    graded: int
    p_success: float          # shrinkage-smoothed
    avg_cost: float
    avg_latency_ms: float
    expected_value: float
    breakdown: dict = field(default_factory=dict)  # transparent term-by-term


def _smoothed_p(successes: int, graded: int,
                alpha: float = PRIOR_ALPHA, beta: float = PRIOR_BETA) -> float:
    """Beta-smoothed success rate. Ungraded evidence (graded=0) falls back to the
    prior mean, so a strategy with only unknown outcomes reads as the prior, not
    0% or 100%."""
    return (successes + alpha) / (graded + alpha + beta)


def expected_value(stat: StrategyStat, *,
                   value: float = VALUE_SUCCESS,
                   latency_weight: float = LATENCY_WEIGHT,
                   latency_budget_ms: float = LATENCY_BUDGET_MS,
                   cost_weight: float = COST_WEIGHT,
                   cost_budget: float = COST_BUDGET) -> EVEstimate:
    p = _smoothed_p(stat.successes, stat.graded)
    lat_pen = latency_weight * min(1.0, (stat.avg_latency_ms or 0.0) / latency_budget_ms)
    cost_pen = cost_weight * min(1.0, (stat.avg_cost or 0.0) / cost_budget) if cost_weight else 0.0
    ev = value * p - lat_pen - cost_pen
    return EVEstimate(
        strategy=stat.strategy, attempts=stat.attempts, graded=stat.graded,
        p_success=round(p, 3), avg_cost=stat.avg_cost, avg_latency_ms=stat.avg_latency_ms,
        expected_value=round(ev, 4),
        breakdown={"value_term": round(value * p, 4),
                   "latency_penalty": round(lat_pen, 4),
                   "cost_penalty": round(cost_pen, 4)},
    )


class StrategySelector:
    def __init__(self, memory: StrategyMemory | None = None, **weights) -> None:
        self.memory = memory or StrategyMemory()
        self.weights = weights  # forwarded to expected_value (override defaults)

    def rank(self, task_class: str) -> list[EVEstimate]:
        """All strategies for a task class, ranked by expected value desc."""
        estimates = [expected_value(s, **self.weights)
                     for s in self.memory.stats_for(task_class)]
        estimates.sort(key=lambda e: -e.expected_value)
        return estimates

    def select(self, task_class: str, *, min_attempts: int = 3,
               margin: float = 0.0) -> EVEstimate | None:
        """Best strategy by EV, or None (abstain) when the evidence is too thin
        to act on. `min_attempts` requires the winner to have been tried enough;
        `margin` requires it to beat the runner-up by at least this EV gap."""
        ranked = self.rank(task_class)
        if not ranked:
            return None
        top = ranked[0]
        if top.attempts < min_attempts:
            return None
        if len(ranked) > 1 and (top.expected_value - ranked[1].expected_value) < margin:
            return None
        return top


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Expected-value strategy selector")
    ap.add_argument("task_class", nargs="?", help="e.g. python/code (omit → all classes)")
    ap.add_argument("--min-attempts", type=int, default=3)
    args = ap.parse_args()

    sel = StrategySelector()
    classes = [args.task_class] if args.task_class else sel.memory.task_classes()
    if not classes:
        print("  No strategy data. Run: python3 -m decision.strategy_memory --ingest")
        return

    for tc in classes:
        ranked = sel.rank(tc)
        if not ranked:
            continue
        chosen = sel.select(tc, min_attempts=args.min_attempts)
        print(f"\n  {tc}")
        print("  " + "─" * 68)
        print(f"  {'strategy':<28}{'EV':>7}{'p':>7}{'n':>4}{'ms':>9}")
        for e in ranked:
            mark = " ←" if chosen and e.strategy == chosen.strategy else ""
            print(f"  {e.strategy:<28}{e.expected_value:>7.3f}{e.p_success:>7.2f}"
                  f"{e.attempts:>4}{e.avg_latency_ms:>9.0f}{mark}")
        verdict = (f"select → {chosen.strategy}" if chosen
                   else f"abstain (need ≥{args.min_attempts} attempts) → keep current router")
        print(f"  {verdict}")


if __name__ == "__main__":
    main()
