# ~/agentic-ai/evaluation/calibration_report.py
# ─────────────────────────────────────────────────────────────
# Reliability diagnostic for routing confidence.
#
# Answers the ONE question that gates the "learned confidence" work:
#   does `confidence` actually predict P(correct)?
#
# It reads the raw (confidence, performance) pairs persisted by
# decision.weights.update_calibration (table: calibration_samples) and prints:
#
#   1. Reliability table — empirical performance per confidence bin.
#      A calibrated estimator has empirical performance ≈ bin confidence.
#   2. ECE — expected calibration error (single scalar miscalibration number).
#   3. Monotonicity verdict — is higher confidence actually better? If NOT,
#      no threshold can work and the whole gate idea needs rethinking first.
#   4. Threshold sweep — the direct input to Move 3 (unify the escalation gate):
#      for each candidate ESCALATION_THRESHOLD, what fraction escalates and how
#      good/risky is what stays local.
#
# This is the *diagnostic*, deliberately not the controller. Measure first.
#
# Usage:
#   python -m evaluation.calibration_report
#   python -m evaluation.calibration_report --agent python_dev --bins 10
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
from dataclasses import dataclass

from decision.weights import get_calibration_samples

# Confidence is bounded to [0.30, 1.00] by decision.weights.to_confidence.
CONF_LO, CONF_HI = 0.30, 1.00
# "Correct enough" cutoff for the threshold sweep's miss-rate. reflection_score
# is performance on [0,1]; below this we treat the local answer as a miss.
GOOD_PERF = 0.60


@dataclass
class Bin:
    lo: float
    hi: float
    confs: list[float]
    perfs: list[float]

    @property
    def n(self) -> int:
        return len(self.perfs)

    @property
    def mean_conf(self) -> float:
        return sum(self.confs) / self.n if self.n else 0.0

    @property
    def mean_perf(self) -> float:
        return sum(self.perfs) / self.n if self.n else 0.0

    @property
    def gap(self) -> float:
        # positive → overconfident (predicted > actual)
        return self.mean_conf - self.mean_perf


def _bin(samples: list[dict], n_bins: int) -> list[Bin]:
    width = (CONF_HI - CONF_LO) / n_bins
    bins = [Bin(CONF_LO + i * width, CONF_LO + (i + 1) * width, [], [])
            for i in range(n_bins)]
    for s in samples:
        c = s["confidence"]
        idx = int((c - CONF_LO) / width) if width else 0
        idx = max(0, min(n_bins - 1, idx))
        bins[idx].confs.append(c)
        bins[idx].perfs.append(s["performance"])
    return bins


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def _bar(value: float, width: int = 20) -> str:
    filled = int(round(value * width))
    return "█" * filled + "·" * (width - filled)


def report(agent: str | None = None, n_bins: int = 7,
           min_count: int = 1) -> dict:
    samples = get_calibration_samples(agent=agent)
    title = f"agent={agent}" if agent else "all agents"
    print("=" * 68)
    print(f"  Confidence reliability report — {title}")
    print("=" * 68)

    if not samples:
        print("\n  No calibration samples yet.")
        print("  Pairs accrue as decisions run through training.learning")
        print("  (apply_learning_update → update_calibration). Run some traffic,")
        print("  then re-run this report.\n")
        return {"n": 0}

    n = len(samples)
    bins = _bin(samples, n_bins)

    # ── 1. Reliability table ─────────────────────────────────────
    print(f"\n  {n} samples\n")
    print("  conf bin      n   mean_conf  emp_perf   gap    empirical perf")
    print("  " + "-" * 64)
    ece = 0.0
    populated = []
    for b in bins:
        if b.n < min_count:
            continue
        populated.append(b)
        ece += (b.n / n) * abs(b.gap)
        flag = "  over" if b.gap > 0.05 else ("  under" if b.gap < -0.05 else "")
        print(f"  {b.lo:.2f}-{b.hi:.2f}  {b.n:4d}    {b.mean_conf:.3f}    "
              f"{b.mean_perf:.3f}   {b.gap:+.3f}  {_bar(b.mean_perf)}{flag}")

    # ── 2. ECE ───────────────────────────────────────────────────
    print(f"\n  ECE (expected calibration error): {ece:.4f}")
    print("    0.00 = perfectly calibrated; gap column shows the direction.")

    # ── 3. Monotonicity verdict ──────────────────────────────────
    confs = [s["confidence"] for s in samples]
    perfs = [s["performance"] for s in samples]
    r = _pearson(confs, perfs)
    bin_perfs = [b.mean_perf for b in populated]
    inversions = sum(1 for i in range(len(bin_perfs) - 1)
                     if bin_perfs[i + 1] < bin_perfs[i] - 1e-9)
    monotonic = r > 0.1 and inversions <= max(1, len(bin_perfs) // 4)
    print(f"\n  Monotonicity: pearson(conf, perf) = {r:+.3f}, "
          f"bin inversions = {inversions}/{max(0, len(bin_perfs) - 1)}")
    if monotonic:
        print("    ✓ confidence tracks performance — a threshold is meaningful.")
        print("      Next: fit a monotonic map (isotonic) + cost-derived threshold.")
    else:
        print("    ✗ confidence does NOT reliably track performance.")
        print("      A single escalation threshold cannot work yet — fix the")
        print("      confidence signal before building any controller on it.")

    # ── 4. Threshold sweep (Move 3 input) ────────────────────────
    print("\n  Escalation threshold sweep  (escalate when confidence < T):")
    print("    T     escalate%   kept_n   kept_perf   kept_miss%")
    print("    " + "-" * 50)
    best = None
    t = 0.40
    while t <= 0.90 + 1e-9:
        kept = [s["performance"] for s in samples if s["confidence"] >= t]
        esc_rate = (n - len(kept)) / n
        if kept:
            kept_perf = sum(kept) / len(kept)
            kept_miss = sum(1 for p in kept if p < GOOD_PERF) / len(kept)
        else:
            kept_perf = kept_miss = 0.0
        print(f"    {t:.2f}   {esc_rate*100:6.1f}%   {len(kept):5d}    "
              f"{kept_perf:.3f}     {kept_miss*100:5.1f}%")
        # Heuristic pick: lowest T whose kept-miss rate is under 10%.
        if best is None and kept and kept_miss < 0.10:
            best = t
        t = round(t + 0.05, 2)
    if best is not None:
        print(f"\n    → cheapest T with <10% local miss rate: {best:.2f}")
        print("      (turn this into a cost-derived constant in Move 3, don't hardcode)")
    else:
        print("\n    → no threshold keeps local miss rate under 10%;")
        print("      local model is under-performing or confidence is miscalibrated.")
    print()

    return {"n": n, "ece": round(ece, 4), "pearson": round(r, 3),
            "monotonic": monotonic, "suggested_threshold": best}


def main() -> None:
    ap = argparse.ArgumentParser(description="Routing confidence reliability report")
    ap.add_argument("--agent", default=None, help="filter to one agent")
    ap.add_argument("--bins", type=int, default=7, help="number of confidence bins")
    ap.add_argument("--min-count", type=int, default=1,
                    help="hide bins with fewer than this many samples")
    args = ap.parse_args()
    report(agent=args.agent, n_bins=args.bins, min_count=args.min_count)


if __name__ == "__main__":
    main()
