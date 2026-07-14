"""
escalation_gate_eval.py
─────────────────────────────────────────────────────────────────
The system-level payoff of self-consistency: a *selective escalation gate*.

reasoning_eval.py measures self-consistency in isolation (voted vs baseline vs
ceiling). It does NOT measure the gate that makes self-consistency worth its N×
cost: use the **winning-vote agreement** (winner votes / valid votes) as a free
confidence signal, TRUST the high-agreement answers locally, and ESCALATE only the
low-agreement ones to a stronger model. The thesis is that a small local model +
selective escalation reaches near-frontier accuracy at a fraction of the frontier
COST — because only the genuinely-uncertain minority ever pays for the big model.

This measures the ACTUAL shipped gate: it reuses `cognition.self_consistency.
escalation_decision` (agreement < 0.6 → escalate), the same call the coordinator
makes at runtime. So the buckets here are exactly what production would route.

This script quantifies that from the REAL per-problem vote records already saved
by reasoning_eval.py (logs/reasoning_*.json). It needs no re-run and no model:
the trust/escalate bucket accuracies are measured directly; the only quantity it
cannot measure locally is the ceiling model's accuracy *on the escalated subset*,
so that is a parameter swept over a grid (and a live ceiling run would pin it).

HONESTY
-------
  * Trust/escalate accuracies and the escalation rate are MEASURED (real votes).
  * gated_acc(c) is a SIMULATION linear in the ceiling parameter c — it assumes
    the ceiling achieves accuracy c on the escalated (hard) subset. It is not a
    live end-to-end number until a frontier column is actually run.
  * Single internal sample (the source N), phi4-mini / GSM8K-specific. Same
    caveat discipline as reasoning_eval.py §9 / FINDINGS.

Run:
    PYTHONPATH=. python3 evaluation/escalation_gate_eval.py            # latest results file
    PYTHONPATH=. python3 evaluation/escalation_gate_eval.py --file logs/reasoning_XXe.json
    PYTHONPATH=. python3 evaluation/escalation_gate_eval.py --margin 3
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = Path(__file__).parent.parent
DEFAULT_CEILING_GRID = (0.80, 0.85, 0.90, 0.95, 1.00)


# ── pure, testable core ───────────────────────────────────────────────────────
def escalates(rec: dict, trust_agreement: float) -> bool:
    """Does the SHIPPED gate escalate this voted record? Reuses production
    `escalation_decision` on the record's vote counts so the eval and the runtime
    can never drift: agreement (votes/valid) below `trust_agreement` → escalate."""
    from cognition.self_consistency import escalation_decision
    return escalation_decision(
        {"votes": rec.get("votes", 0), "valid": rec.get("valid", 0)},
        trust_agreement=trust_agreement,
    )["escalate"]


def analyze_gate(
    voted: list[dict],
    trust_agreement: float = 0.6,
    ceiling_grid: tuple[float, ...] = DEFAULT_CEILING_GRID,
) -> dict:
    """
    Split the voted results into TRUST (agreement ≥ threshold) and ESCALATE
    (agreement < threshold) buckets via the shipped gate, measure each, and
    simulate the gated accuracy if the escalated subset were answered by a
    ceiling model of accuracy c.

    gated_acc(c) = trust_frac · trust_acc + escalate_frac · c
    escalation_rate = escalate_frac  (the share of queries that pay for the ceiling)
    """
    n = len(voted)
    if n == 0:
        raise ValueError("no voted results to analyze")

    esc = [r for r in voted if escalates(r, trust_agreement)]
    trust = [r for r in voted if not escalates(r, trust_agreement)]

    def acc(xs: list[dict]) -> float:
        return sum(bool(x.get("correct")) for x in xs) / len(xs) if xs else 0.0

    voted_acc = acc(voted)
    trust_acc, esc_acc = acc(trust), acc(esc)
    errors = [r for r in voted if not r.get("correct")]
    esc_errors = [r for r in errors if escalates(r, trust_agreement)]

    trust_frac, esc_frac = len(trust) / n, len(esc) / n
    out = {
        "n": n,
        "trust_agreement": trust_agreement,
        "voted_acc": round(voted_acc, 4),
        "trust": {"n": len(trust), "frac": round(trust_frac, 4), "acc": round(trust_acc, 4)},
        "escalate": {"n": len(esc), "frac": round(esc_frac, 4), "acc": round(esc_acc, 4)},
        # Share of ALL errors that land in the escalate bucket — the gate is only
        # useful if it catches most errors while escalating a minority of volume.
        "error_capture": round(len(esc_errors) / len(errors), 4) if errors else None,
        # Escalation only *helps* the escalated bucket when the ceiling beats the
        # local vote there; below this the gate is net-negative on that subset.
        "break_even_ceiling": round(esc_acc, 4),
        "gated": [],
    }
    for c in ceiling_grid:
        gated_acc = trust_frac * trust_acc + esc_frac * c
        out["gated"].append({
            "ceiling_acc": c,
            "gated_acc": round(gated_acc, 4),
            "escalation_rate": round(esc_frac, 4),
            "lift_over_voted": round(gated_acc - voted_acc, 4),
        })
    return out


# ── IO / CLI ──────────────────────────────────────────────────────────────────
def _latest_results() -> str:
    files = sorted(glob.glob(str(_ROOT / "logs" / "reasoning_*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        raise SystemExit("no logs/reasoning_*.json found — run reasoning_eval.py first")
    return files[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Self-consistency escalation-gate analysis (from saved vote records)")
    ap.add_argument("--file", help="a reasoning_*.json results file (default: latest)")
    ap.add_argument("--trust", type=float, default=0.6, help="agreement threshold to trust local (default 0.6, shipped)")
    args = ap.parse_args()

    path = args.file or _latest_results()
    data = json.load(open(path))
    voted = data.get("voted", [])
    if not voted or "votes" not in voted[0]:
        raise SystemExit(f"{path} has no per-problem vote counts to analyze")

    r = analyze_gate(voted, trust_agreement=args.trust)

    print("=" * 66)
    print("  Self-consistency ESCALATION GATE  (shipped: agreement = votes/valid)")
    print(f"  source: {os.path.basename(path)}   n={r['n']}   trust when agreement ≥ {r['trust_agreement']}")
    print("=" * 66)
    print(f"\n  voted (no gate) accuracy : {r['voted_acc']:.3f}")
    print(f"  TRUST    (agreement ≥ {r['trust_agreement']}): n={r['trust']['n']:3d} ({r['trust']['frac']:.0%})  acc={r['trust']['acc']:.3f}")
    print(f"  ESCALATE (agreement < {r['trust_agreement']}): n={r['escalate']['n']:3d} ({r['escalate']['frac']:.0%})  acc={r['escalate']['acc']:.3f}")
    if r["error_capture"] is not None:
        print(f"\n  error capture: {r['error_capture']:.0%} of all errors fall in the "
              f"{r['escalate']['frac']:.0%} escalated — gate catches most errors at minority cost")
    print(f"  break-even ceiling: escalation helps the escalated subset only if the "
          f"ceiling beats {r['break_even_ceiling']:.3f}")

    print("\n  Simulated gated accuracy (escalate the low-margin subset to a ceiling):")
    print("    ceiling_acc   gated_acc   escalation_rate   lift_over_voted")
    print("    " + "-" * 58)
    for g in r["gated"]:
        print(f"      {g['ceiling_acc']:.2f}         {g['gated_acc']:.3f}         "
              f"{g['escalation_rate']:.0%}              {g['lift_over_voted']:+.3f}")
    print("\n  NOTE: trust/escalate accuracies + escalation rate are MEASURED; the")
    print("  gated column is a simulation linear in ceiling_acc (a live frontier run")
    print("  pins it). phi4-mini / GSM8K, single internal sample — internal metric.")


if __name__ == "__main__":
    main()
