"""
decision_econ_readiness.py — is the decision-economics layer ready to beat baseline?

OPEN_PROBLEMS O2 closes only when the EV selector **beats the signal/rule baseline
on a held-out set**. That requires two things that do not exist at user #0:
graded held-out labels (O5) and ≥2 explored strategies per class. Faking either
would turn a [C] conjecture into a false [M] — exactly what the register forbids.

So this harness reports **readiness**, not a win. It answers, honestly:

  1. Coverage   — how many task classes are *selectable* (≥2 strategies, winner
                  clears min_attempts + margin)? Until this is >0 the selector
                  abstains everywhere and wiring it changes nothing.
  2. Divergence — on the selectable classes, does the EV winner differ from the
                  baseline (the naturally-most-attempted strategy)? Divergence is
                  where the layer *could* add value; agreement means it's a no-op.
  3. Accuracy   — held-out success of selector vs baseline. Reported as PENDING
                  with a coverage line until graded outcomes accrue — never faked.

Run it after `python3 -m decision.experience --explore N` has populated
alternatives. A green readiness (coverage>0, divergence>0) is the signal that the
held-out accuracy row is finally worth computing — and that O2's "closes when" is
in reach rather than blocked on machinery.

Usage
─────
  python3 -m workbench.evaluation.decision_econ_readiness
  python3 -m workbench.evaluation.decision_econ_readiness --min-attempts 3
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from decision.strategy_memory import StrategyMemory
from decision.strategy_selector import StrategySelector, parse_strategy


@dataclass
class ClassReadiness:
    task_class: str
    n_strategies: int
    baseline: str            # most-attempted strategy (what natural traffic does)
    selector_pick: str | None  # EV winner, or None (abstain)
    diverges: bool
    ev_gap: float | None     # winner EV − runner-up EV (None when abstaining)


def _baseline_strategy(mem: StrategyMemory, task_class: str) -> str:
    """What natural traffic already does for this class = most-attempted strategy.
    This is the honest baseline the selector must beat to justify its existence."""
    stats = mem.stats_for(task_class)
    if not stats:
        return "—"
    return max(stats, key=lambda s: s.attempts).strategy


def assess(mem: StrategyMemory | None = None, *, min_attempts: int = 3,
           margin: float = 0.02) -> list[ClassReadiness]:
    mem = mem or StrategyMemory()
    sel = StrategySelector(mem)
    out: list[ClassReadiness] = []
    for tc in mem.task_classes():
        stats = mem.stats_for(tc)
        baseline = _baseline_strategy(mem, tc)
        chosen = sel.select(tc, min_attempts=min_attempts, margin=margin)
        pick = chosen.strategy if chosen else None
        ranked = sel.rank(tc)
        gap = (round(ranked[0].expected_value - ranked[1].expected_value, 4)
               if chosen and len(ranked) > 1 else None)
        out.append(ClassReadiness(
            task_class=tc, n_strategies=len(stats), baseline=baseline,
            selector_pick=pick, diverges=bool(pick and pick != baseline), ev_gap=gap,
        ))
    return out


def report(min_attempts: int = 3, margin: float = 0.02) -> None:
    rows = assess(min_attempts=min_attempts, margin=margin)
    selectable = [r for r in rows if r.selector_pick]
    diverging = [r for r in selectable if r.diverges]

    print("\n  Decision-economics readiness (O2)")
    print("  " + "═" * 70)
    if not rows:
        print("  Strategy memory is empty.")
        print("  → run: python3 -m decision.strategy_memory --ingest")
        print("         python3 -m decision.experience --explore 15")
        return

    print(f"  {'task_class':<22}{'#strat':>7}{'baseline':<22}{'selector':<20}")
    print("  " + "─" * 70)
    for r in rows:
        pick = r.selector_pick or "abstain"
        flag = "  ⚑" if r.diverges else ""
        print(f"  {r.task_class:<22}{r.n_strategies:>7}  {r.baseline[:20]:<20}{pick[:18]:<18}{flag}")
    print("  " + "─" * 70)

    # ── The three honest readiness lines ─────────────────────────────
    print(f"\n  1. Coverage   : {len(selectable)}/{len(rows)} classes selectable "
          f"(≥2 strategies, winner clears min_attempts={min_attempts}+margin={margin})")
    print(f"  2. Divergence : {len(diverging)}/{max(len(selectable),1)} selectable classes "
          f"where the EV winner ≠ baseline (⚑ above) — the value-add surface")
    print( "  3. Accuracy   : PENDING — held-out selector-vs-baseline success needs "
           "graded\n"
           "                  outcomes (O5). Coverage>0 AND divergence>0 is the gate "
           "to compute it.")

    # ── Verdict ──────────────────────────────────────────────────────
    if not selectable:
        verdict = ("BLOCKED on exploration — every class abstains. Run "
                   "`decision.experience --explore N` to populate alternatives.")
    elif not diverging:
        verdict = ("READY but NO-OP — selector agrees with baseline everywhere; "
                   "it would change no routes. Needs more diverse exploration.")
    else:
        verdict = (f"READY to measure — {len(diverging)} class(es) where the selector "
                   f"diverges from baseline. Compute held-out accuracy next.")
    print(f"\n  Verdict: {verdict}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Decision-economics readiness report (O2)")
    ap.add_argument("--min-attempts", type=int, default=3)
    ap.add_argument("--margin", type=float, default=0.02)
    args = ap.parse_args()
    report(min_attempts=args.min_attempts, margin=args.margin)


if __name__ == "__main__":
    main()
