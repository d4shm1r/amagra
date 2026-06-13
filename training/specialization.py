"""
Agent Specialization Index — P1

Derived entirely from the trace dataset (trace_builder.py).
Computes per-agent stats and assigns a structural verdict.

Verdicts:
  core        — high volume, low conflict, acceptable quality. Essential to the system.
  narrow      — low volume but specialized. Survives if the domain is real.
  struggling  — high conflict + high regret. Routing is unreliable for this agent.
  redundant   — domain heavily overlaps with a higher-quality agent. Merge candidate.

This output drives:
  - pre-restructure architecture decisions (which agents survive as-is)
  - routing re-weighting (which agents deserve higher prior weight)
  - memory audit (struggling agents may have corrupted memory)

Run standalone or use compute() from other modules.
"""

import sys, os
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from cognition.trace_builder import build_traces, load_cached_traces


# ── Thresholds ────────────────────────────────────────────────
_VOLUME_CORE    = 40      # decisions needed to be "core"
_VOLUME_NARROW  = 10      # below this → sparse data, treat as narrow
_CONFLICT_HIGH  = 0.40    # conflict rate above this → struggling signal
_REGRET_HIGH    = 0.15    # avg regret above this → struggling signal
_QUALITY_LOW    = 0.68    # avg quality proxy below this → struggling
_OVERLAP_THRESH = 0.40    # domain overlap fraction above this → redundancy candidate


def compute(traces: list = None) -> dict:
    """
    Compute agent specialization index from trace dataset.

    Returns dict keyed by agent_id with stats + verdict.
    Pass traces=None to auto-load from cached JSONL, or rebuild=True to recompute.
    """
    if traces is None:
        traces = load_cached_traces()
    if not traces:
        traces = build_traces()

    # ── Per-agent aggregation ─────────────────────────────────
    agents: dict = defaultdict(lambda: {
        "decisions":       0,
        "real_sessions":   0,
        "conflicts":       0,
        "reflections":     0,
        "regret_sum":      0.0,
        "quality_sum":     0.0,
        "memory_sum":      0,
        "domains":         defaultdict(int),
        "actions":         defaultdict(int),
        "conflict_partners": defaultdict(int),  # which agents router preferred instead
    })

    for t in traces:
        a = t["routing"]["final_agent"]
        s = agents[a]
        s["decisions"]    += 1
        s["real_sessions"] += 0 if t["labels"]["is_eval"] else 1
        s["conflicts"]    += 1 if t["labels"]["has_conflict"] else 0
        s["reflections"]  += 1 if t["labels"]["has_reflection"] else 0
        s["regret_sum"]   += t["outcome"]["regret"]
        s["quality_sum"]  += t["outcome"]["quality_proxy"]
        s["memory_sum"]   += t["memory"]["count"]
        s["domains"][t["signal"]["domain"]] += 1
        s["actions"][t["routing"]["action"]] += 1
        # When conflict: record what the router wanted instead
        if t["labels"]["has_conflict"]:
            router_pref = t["routing"]["router_agent"]
            if router_pref and router_pref != "none":
                s["conflict_partners"][router_pref] += 1

    # ── Per-agent derived metrics ─────────────────────────────
    result = {}
    for agent_id, s in agents.items():
        n = s["decisions"]
        conflict_rate   = round(s["conflicts"]   / n, 3)
        reflect_rate    = round(s["reflections"] / n, 3)
        avg_regret      = round(s["regret_sum"]  / n, 4)
        avg_quality     = round(s["quality_sum"] / n, 3)
        avg_memory      = round(s["memory_sum"]  / n, 2)

        # Top domains (sorted by frequency, top 3)
        top_domains = sorted(s["domains"].items(), key=lambda x: -x[1])
        domain_dist = {d: round(c / n, 3) for d, c in top_domains}
        top_domain  = top_domains[0][0] if top_domains else "unknown"
        top_domain_pct = round(top_domains[0][1] / n, 3) if top_domains else 0.0

        # Top actions
        top_actions = sorted(s["actions"].items(), key=lambda x: -x[1])
        action_dist = {a: round(c / n, 3) for a, c in top_actions}

        # Conflict partners — who the router prefers when brain disagrees
        conflict_partners = dict(sorted(s["conflict_partners"].items(), key=lambda x: -x[1])[:3])

        result[agent_id] = {
            "total_decisions":  n,
            "real_sessions":    s["real_sessions"],
            "conflict_rate":    conflict_rate,
            "reflect_rate":     reflect_rate,
            "avg_regret":       avg_regret,
            "avg_quality_proxy": avg_quality,
            "avg_memories_per_q": avg_memory,
            "top_domain":       top_domain,
            "top_domain_pct":   top_domain_pct,
            "domain_distribution": domain_dist,
            "action_distribution": action_dist,
            "conflict_partners": conflict_partners,
            # verdict computed below
            "verdict":          None,
            "verdict_reason":   "",
        }

    # ── Verdicts ──────────────────────────────────────────────
    # Pass 1: flag struggling + narrow
    for a, r in result.items():
        n  = r["total_decisions"]
        cr = r["conflict_rate"]
        rg = r["avg_regret"]
        qp = r["avg_quality_proxy"]

        if n < _VOLUME_NARROW:
            r["verdict"]        = "narrow"
            r["verdict_reason"] = f"sparse data ({n} decisions) — insufficient signal"
            continue

        struggling_signals = (
            (cr  >= _CONFLICT_HIGH, f"conflict_rate={cr:.2f}"),
            (rg  >= _REGRET_HIGH,   f"avg_regret={rg:.4f}"),
            (qp  <= _QUALITY_LOW,   f"avg_quality={qp:.3f}"),
        )
        fired = [msg for cond, msg in struggling_signals if cond]
        if len(fired) >= 2:
            r["verdict"]        = "struggling"
            r["verdict_reason"] = "; ".join(fired)
            continue

        if n >= _VOLUME_CORE:
            r["verdict"]        = "core"
            r["verdict_reason"] = f"{n} decisions, conflict={cr:.2f}, quality={qp:.3f}"
        else:
            r["verdict"]        = "narrow"
            r["verdict_reason"] = f"{n} decisions — below core threshold ({_VOLUME_CORE})"

    # Pass 2: redundancy — look for domain overlap between agents
    # An agent is "redundant" if its primary domain is majority-covered by a higher-quality agent
    for a, r in result.items():
        if r["verdict"] in ("struggling", "narrow"):
            continue  # already flagged
        top_d   = r["top_domain"]
        top_pct = r["top_domain_pct"]
        if top_pct < _OVERLAP_THRESH:
            continue  # no dominant domain → not a simple redundancy case

        # Find other agents also handling top_d at significant rate
        competitors = []
        for other, other_r in result.items():
            if other == a:
                continue
            other_pct = other_r["domain_distribution"].get(top_d, 0.0)
            if other_pct >= 0.15:  # other agent handles ≥15% of its queries in this domain
                competitors.append((other, other_pct, other_r["avg_quality_proxy"]))

        for comp, comp_pct, comp_q in competitors:
            # Only flag redundancy if the competitor has substantially better quality
            if comp_q > r["avg_quality_proxy"] + 0.08 and comp_pct > top_pct * 0.5:
                r["verdict"]        = "redundant"
                r["verdict_reason"] = (
                    f"domain '{top_d}' ({top_pct:.0%}) also covered by "
                    f"{comp} at higher quality ({comp_q:.3f} vs {r['avg_quality_proxy']:.3f})"
                )
                break

    return result


def summary_table(specialization: dict) -> str:
    """Return a human-readable table of the specialization index."""
    lines = [
        f"{'Agent':<25} {'N':>5} {'Conflict':>9} {'Regret':>7} "
        f"{'Quality':>8} {'Verdict':<12} Notes"
    ]
    lines.append("-" * 90)
    verdicts = {"core": 0, "struggling": 0, "narrow": 0, "redundant": 0}
    for a, r in sorted(specialization.items(), key=lambda x: -x[1]["total_decisions"]):
        v = r["verdict"] or "?"
        verdicts[v] = verdicts.get(v, 0) + 1
        lines.append(
            f"{a:<25} {r['total_decisions']:>5} "
            f"{r['conflict_rate']:>8.1%} {r['avg_regret']:>7.4f} "
            f"{r['avg_quality_proxy']:>8.3f} {v:<12} "
            f"{r['verdict_reason'][:60]}"
        )
    lines.append("-" * 90)
    lines.append(f"Verdicts: {verdicts}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Computing agent specialization index...")
    spec = compute()
    print(summary_table(spec))
    print()
    # Print domain coverage detail
    print("Domain coverage per agent:")
    for a, r in sorted(spec.items(), key=lambda x: -x[1]["total_decisions"]):
        top3 = list(r["domain_distribution"].items())[:3]
        top3_str = ", ".join(f"{d}={v:.0%}" for d, v in top3)
        print(f"  {a:<25} {top3_str}")
