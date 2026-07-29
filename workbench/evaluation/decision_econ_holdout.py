"""
decision_econ_holdout.py — the held-out selector-vs-baseline evaluator (O2 DoD #4).

`decision_econ_readiness.py` answers *"is there enough data to measure?"* and holds
the accuracy row at PENDING. This module is the measurement it was waiting for: given
strategy records, does the EV selector's per-class pick actually **beat the baseline
on data it did not train on**?

It is an **off-policy** evaluation, and honest about the limits that imposes:

  * **Temporal split.** Records for each task_class are ordered by time; the earliest
    `1 − holdout_frac` train the policies, the rest score them. A learning system must
    be judged on its future, not a random shuffle of its past.
  * **Matched-strategy scoring.** We can only observe an outcome for a strategy that
    was actually run. So a class is *scored* only when the holdout contains records for
    both the selector's pick and the baseline's pick; otherwise it is `insufficient`,
    never guessed. This is the classic off-policy constraint, surfaced not hidden.
  * **Proxy outcomes.** Success is the recorded proxy/critic-gate signal, not graded
    correctness. Every number here is therefore **internal-only** in the OPEN_PROBLEMS
    sense — indicative, not validated. It closes O2's *machinery*; a validated `[M]`
    still needs κ-checked labels (O1) + real graded traffic (O5).

What "beats baseline" means: on the scored classes, the mean realized success rate of
the selector's picks minus the baseline's picks (with the latency delta reported
alongside, since decision *economics* trades quality against cost).

Usage
─────
  python3 -m workbench.evaluation.decision_econ_holdout
  python3 -m workbench.evaluation.decision_econ_holdout --holdout-frac 0.3 --min-attempts 3
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from decision.strategy_memory import StrategyMemory, StrategyRecord
from decision.strategy_selector import StrategySelector


@dataclass
class Record:
    task_class: str
    strategy: str
    success: bool | None
    latency_ms: int
    ts: float


@dataclass
class ClassOutcome:
    task_class: str
    selector_pick: str | None      # None = selector abstained → defers to baseline
    baseline_pick: str | None
    status: str                    # scored | abstained | insufficient
    selector_success: float | None = None
    baseline_success: float | None = None
    selector_latency: float | None = None
    baseline_latency: float | None = None
    holdout_n: int = 0

    @property
    def success_delta(self) -> float | None:
        if self.selector_success is None or self.baseline_success is None:
            return None
        return round(self.selector_success - self.baseline_success, 3)


@dataclass
class HoldoutReport:
    outcomes: list[ClassOutcome] = field(default_factory=list)
    holdout_frac: float = 0.3
    min_attempts: int = 3
    margin: float = 0.02

    @property
    def scored(self) -> list[ClassOutcome]:
        return [o for o in self.outcomes if o.status == "scored"]

    def mean_success_delta(self) -> float | None:
        deltas = [o.success_delta for o in self.scored if o.success_delta is not None]
        return round(sum(deltas) / len(deltas), 3) if deltas else None

    def mean_latency_delta(self) -> float | None:
        pairs = [(o.selector_latency, o.baseline_latency) for o in self.scored
                 if o.selector_latency is not None and o.baseline_latency is not None]
        if not pairs:
            return None
        return round(sum(s - b for s, b in pairs) / len(pairs), 1)

    def verdict(self) -> str:
        if not self.scored:
            return ("INSUFFICIENT — no class had holdout coverage for both the selector "
                    "and baseline picks. Needs more exploration/traffic, not code.")
        d = self.mean_success_delta()
        if d is None:
            return "INSUFFICIENT — scored classes lacked graded holdout outcomes."
        lat = self.mean_latency_delta()
        lat_note = f" (mean latency Δ {lat:+.0f} ms)" if lat is not None else ""
        if d > 0.02:
            return f"BEATS baseline by +{d:.3f} mean success on {len(self.scored)} class(es){lat_note} — internal-only."
        if d < -0.02:
            return f"LOSES to baseline by {d:.3f} mean success on {len(self.scored)} class(es){lat_note} — internal-only."
        return (f"TIES baseline (Δ{d:+.3f}) on {len(self.scored)} class(es){lat_note}. "
                f"If latency Δ < 0 the selector wins on cost at equal quality — internal-only.")


# ── data loading ─────────────────────────────────────────────────────

def load_records(db_path: str | None = None) -> list[Record]:
    """Read raw strategy rows from the strategy DB (read-only). Returns [] when the
    DB is absent/empty — the harness then reports INSUFFICIENT rather than erroring."""
    path = db_path or StrategyMemory().path
    if not os.path.exists(path):
        return []
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT task_class, strategy, success, latency_ms, ts FROM strategy_records"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    out = []
    for tc, strat, succ, lat, ts in rows:
        out.append(Record(
            task_class=tc, strategy=strat,
            success=(None if succ is None else bool(succ)),
            latency_ms=int(lat or 0), ts=float(ts or 0.0),
        ))
    return out


def temporal_split(records: list[Record], holdout_frac: float
                   ) -> tuple[list[Record], list[Record]]:
    """Per task_class, order by ts and take the latest `holdout_frac` as holdout.
    Splitting within each class (not globally) keeps every class represented in both
    halves when it has the volume for it."""
    by_class: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        by_class[r.task_class].append(r)
    train, holdout = [], []
    for tc, recs in by_class.items():
        recs.sort(key=lambda r: r.ts)
        cut = max(1, int(round(len(recs) * (1.0 - holdout_frac))))
        train.extend(recs[:cut])
        holdout.extend(recs[cut:])
    return train, holdout


def _empirical(records: list[Record]) -> dict[tuple[str, str], tuple[float, float, int]]:
    """(task_class, strategy) → (success_rate, avg_latency_ms, n). success_rate is over
    graded rows only; a strategy with only ungraded holdout rows yields success_rate=None
    via a sentinel of -1.0 that callers treat as 'unobserved success'."""
    agg: dict[tuple[str, str], list[Record]] = defaultdict(list)
    for r in records:
        agg[(r.task_class, r.strategy)].append(r)
    out = {}
    for key, recs in agg.items():
        graded = [r for r in recs if r.success is not None]
        sr = (sum(1 for r in graded if r.success) / len(graded)) if graded else -1.0
        avg_lat = sum(r.latency_ms for r in recs) / len(recs)
        out[key] = (sr, avg_lat, len(recs))
    return out


# ── the evaluation ───────────────────────────────────────────────────

def evaluate(records: list[Record], *, holdout_frac: float = 0.3,
             min_attempts: int = 3, margin: float = 0.02) -> HoldoutReport:
    report = HoldoutReport(holdout_frac=holdout_frac, min_attempts=min_attempts, margin=margin)
    train, holdout = temporal_split(records, holdout_frac)
    if not train or not holdout:
        return report

    # Build a train-only StrategyMemory so the selector/baseline learn on the past only.
    import tempfile
    train_mem = StrategyMemory(path=os.path.join(tempfile.mkdtemp(), "train.db"))
    for i, r in enumerate(train):
        train_mem.record(StrategyRecord(
            task_class=r.task_class, strategy=r.strategy, success=r.success,
            latency_ms=r.latency_ms, run_id=f"train-{i}", ts=r.ts,
        ))
    selector = StrategySelector(train_mem)
    holdout_emp = _empirical(holdout)

    for tc in train_mem.task_classes():
        stats = train_mem.stats_for(tc)
        baseline_pick = max(stats, key=lambda s: s.attempts).strategy if stats else None
        chosen = selector.select(tc, min_attempts=min_attempts, margin=margin)
        selector_pick = chosen.strategy if chosen else None

        if selector_pick is None:
            report.outcomes.append(ClassOutcome(
                task_class=tc, selector_pick=None, baseline_pick=baseline_pick,
                status="abstained"))
            continue

        sel_obs = holdout_emp.get((tc, selector_pick))
        base_obs = holdout_emp.get((tc, baseline_pick))
        # Scored only when BOTH picks were actually run in the holdout AND both graded.
        if not sel_obs or not base_obs or sel_obs[0] < 0 or base_obs[0] < 0:
            report.outcomes.append(ClassOutcome(
                task_class=tc, selector_pick=selector_pick, baseline_pick=baseline_pick,
                status="insufficient",
                holdout_n=(sel_obs[2] if sel_obs else 0) + (base_obs[2] if base_obs else 0)))
            continue

        report.outcomes.append(ClassOutcome(
            task_class=tc, selector_pick=selector_pick, baseline_pick=baseline_pick,
            status="scored",
            selector_success=round(sel_obs[0], 3), baseline_success=round(base_obs[0], 3),
            selector_latency=round(sel_obs[1], 1), baseline_latency=round(base_obs[1], 1),
            holdout_n=sel_obs[2] + base_obs[2]))
    return report


# ── CLI ──────────────────────────────────────────────────────────────

def run(holdout_frac: float = 0.3, min_attempts: int = 3, margin: float = 0.02,
        db_path: str | None = None) -> None:
    records = load_records(db_path)
    rep = evaluate(records, holdout_frac=holdout_frac, min_attempts=min_attempts, margin=margin)

    print("\n  Decision-economics held-out evaluation (O2 DoD #4)")
    print("  " + "═" * 74)
    if not records:
        print("  Strategy memory is empty — nothing to evaluate.")
        print("  → populate it first: python3 -m decision.strategy_memory --ingest")
        print("                       python3 -m decision.experience --explore 15")
        return

    n_by_status = defaultdict(int)
    for o in rep.outcomes:
        n_by_status[o.status] += 1

    print(f"  records={len(records)}  holdout_frac={holdout_frac}  "
          f"min_attempts={min_attempts}  margin={margin}")
    print("  " + "─" * 74)
    print(f"  {'task_class':<22}{'status':<13}{'selector':<20}{'Δsucc':>7}{'Δlat_ms':>9}")
    print("  " + "─" * 74)
    for o in rep.outcomes:
        d = f"{o.success_delta:+.3f}" if o.success_delta is not None else "—"
        dl = (f"{o.selector_latency - o.baseline_latency:+.0f}"
              if o.selector_latency is not None and o.baseline_latency is not None else "—")
        pick = (o.selector_pick or "abstain")[:18]
        print(f"  {o.task_class:<22}{o.status:<13}{pick:<20}{d:>7}{dl:>9}")
    print("  " + "─" * 74)
    print(f"  scored={n_by_status['scored']}  abstained={n_by_status['abstained']}  "
          f"insufficient={n_by_status['insufficient']}")
    print(f"\n  Verdict: {rep.verdict()}")
    print("  (All figures internal-only / proxy-graded — see module docstring + OPEN_PROBLEMS O2.)\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Held-out selector-vs-baseline evaluator (O2 DoD #4)")
    ap.add_argument("--holdout-frac", type=float, default=0.3)
    ap.add_argument("--min-attempts", type=int, default=3)
    ap.add_argument("--margin", type=float, default=0.02)
    args = ap.parse_args()
    run(holdout_frac=args.holdout_frac, min_attempts=args.min_attempts, margin=args.margin)


if __name__ == "__main__":
    main()
