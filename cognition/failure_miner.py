# ~/agentic-ai/failure_miner.py
# ─────────────────────────────────────────────────────────────
# Nightly failure analysis.
# Reads brain_decisions.db and feedback.db, clusters failure
# patterns by agent/action, and produces an actionable report.
#
# Usage:
#   python3 failure_miner.py               # pretty print
#   python3 failure_miner.py --json        # JSON output
#   python3 failure_miner.py --save        # save to logs/failure_report.json
# ─────────────────────────────────────────────────────────────

import sys, os, json, sqlite3
from collections import defaultdict
from datetime import datetime, timezone

_ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BRAIN_DB    = os.path.join(_ROOT, "logs", "decisions.db")   # brain_decisions table lives here
_FEEDBACK_DB = os.path.join(_ROOT, "logs", "feedback.db")
_REPORT_PATH = os.path.join(_ROOT, "logs", "failure_report.json")

# ── Thresholds ────────────────────────────────────────────────
HIGH_REGRET       = 0.25   # decision regret above this = routing inefficiency
HIGH_CONFLICT_PCT = 0.40   # agent has >40% conflict rate = routing uncertainty
NEG_FEEDBACK_MIN  = 2      # need ≥2 negative ratings to flag an agent


# ── Data loading ──────────────────────────────────────────────

def _load_decisions(limit: int = 500) -> list[dict]:
    if not os.path.exists(_BRAIN_DB):
        return []
    conn = sqlite3.connect(_BRAIN_DB, timeout=10)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, task, action, complexity, brain_agent, "
            "       router_agent, final_agent, conflict, reflect, reflect_type, "
            "       duration_ms, COALESCE(regret,0.0) "
            "FROM brain_decisions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id":           r[0],
            "timestamp":    r[1],
            "task":         r[2],
            "action":       r[3],
            "complexity":   r[4],
            "brain_agent":  r[5],
            "router_agent": r[6],
            "final_agent":  r[7],
            "conflict":     bool(r[8]),
            "reflect":      bool(r[9]),
            "reflect_type": r[10],
            "duration_ms":  r[11],
            "regret":       float(r[12]),
        }
        for r in rows
    ]


def _load_feedback() -> list[dict]:
    if not os.path.exists(_FEEDBACK_DB):
        return []
    conn = sqlite3.connect(_FEEDBACK_DB, timeout=10)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, query, agent, rating, note "
            "FROM feedback ORDER BY id DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "timestamp": r[1], "query": r[2],
         "agent": r[3], "rating": r[4], "note": r[5]}
        for r in rows
    ]


# ── Analysis ──────────────────────────────────────────────────

def mine(limit: int = 500) -> dict:
    """
    Cluster failure signals and return a structured report.
    Reads from brain_decisions.db and feedback.db.
    """
    decisions = _load_decisions(limit)
    feedback  = _load_feedback()
    total     = len(decisions)

    if total == 0:
        # Same schema as the populated report so consumers never branch on shape
        return {
            "generated":        datetime.now(timezone.utc).isoformat(),
            "total_decisions":  0,
            "analysis_window":  limit,
            "summary": {
                "total_conflicts":   0,
                "conflict_rate":     0.0,
                "total_reflected":   0,
                "reflection_rate":   0.0,
                "high_regret_count": 0,
                "avg_regret":        0.0,
                "avg_latency_ms":    0,
                "feedback_total":    len(feedback),
                "feedback_negative": sum(1 for f in feedback if f["rating"] == -1),
            },
            "regret_by_agent":    {},
            "conflict_by_agent":  {},
            "regret_by_action":   {},
            "feedback_by_agent":  {},
            "top_failures":       [],
        }

    # ── 1. High-regret decisions ──────────────────────────────
    high_regret = [d for d in decisions if d["regret"] >= HIGH_REGRET]

    regret_by_agent = defaultdict(list)
    for d in high_regret:
        regret_by_agent[d["final_agent"]].append(d["regret"])

    regret_clusters = {
        agent: {
            "count":      len(vals),
            "avg_regret": round(sum(vals) / len(vals), 3),
            "pct_of_total": round(len(vals) / total * 100, 1),
        }
        for agent, vals in sorted(
            regret_by_agent.items(), key=lambda x: -len(x[1])
        )
    }

    # ── 2. Conflict analysis per agent ────────────────────────
    conflicts_by_agent = defaultdict(lambda: {"conflicts": 0, "total": 0})
    for d in decisions:
        a = d["final_agent"]
        conflicts_by_agent[a]["total"] += 1
        if d["conflict"]:
            conflicts_by_agent[a]["conflicts"] += 1

    conflict_clusters = {
        agent: {
            "conflict_rate": round(v["conflicts"] / max(v["total"], 1), 3),
            "conflicts":     v["conflicts"],
            "total":         v["total"],
        }
        for agent, v in conflicts_by_agent.items()
        if v["total"] >= 3
    }
    conflict_clusters = dict(
        sorted(conflict_clusters.items(), key=lambda x: -x[1]["conflict_rate"])
    )

    # ── 3. Action-level failure breakdown ─────────────────────
    action_regret = defaultdict(list)
    for d in high_regret:
        action_regret[d["action"]].append(d["regret"])

    action_clusters = {
        action: {
            "count":      len(vals),
            "avg_regret": round(sum(vals) / len(vals), 3),
        }
        for action, vals in sorted(
            action_regret.items(), key=lambda x: -len(x[1])
        )
    }

    # ── 4. User feedback signals ──────────────────────────────
    neg_by_agent = defaultdict(int)
    pos_by_agent = defaultdict(int)
    for f in feedback:
        if f["rating"] == -1:
            neg_by_agent[f["agent"]] += 1
        elif f["rating"] == 1:
            pos_by_agent[f["agent"]] += 1

    feedback_clusters = {}
    for agent in set(list(neg_by_agent.keys()) + list(pos_by_agent.keys())):
        neg = neg_by_agent[agent]
        pos = pos_by_agent[agent]
        total_fb = neg + pos
        feedback_clusters[agent] = {
            "positive":     pos,
            "negative":     neg,
            "total":        total_fb,
            "approval_rate": round(pos / max(total_fb, 1), 2),
        }
    feedback_clusters = dict(
        sorted(feedback_clusters.items(), key=lambda x: x[1]["negative"], reverse=True)
    )

    # ── 5. Top failure tasks ──────────────────────────────────
    worst = sorted(high_regret, key=lambda d: -d["regret"])[:10]
    top_failures = [
        {
            "id":      d["id"],
            "agent":   d["final_agent"],
            "action":  d["action"],
            "regret":  d["regret"],
            "task":    d["task"][:80] if d["task"] else "",
        }
        for d in worst
    ]

    # ── 6. Summary stats ─────────────────────────────────────
    total_conflicts  = sum(1 for d in decisions if d["conflict"])
    total_reflected  = sum(1 for d in decisions if d["reflect"])
    avg_regret       = round(sum(d["regret"] for d in decisions) / max(total, 1), 3)
    avg_latency_ms   = round(sum(d["duration_ms"] for d in decisions) / max(total, 1))

    return {
        "generated":        datetime.now(timezone.utc).isoformat(),
        "total_decisions":  total,
        "analysis_window":  limit,
        "summary": {
            "total_conflicts":   total_conflicts,
            "conflict_rate":     round(total_conflicts / total, 3),
            "total_reflected":   total_reflected,
            "reflection_rate":   round(total_reflected / total, 3),
            "high_regret_count": len(high_regret),
            "avg_regret":        avg_regret,
            "avg_latency_ms":    avg_latency_ms,
            "feedback_total":    len(feedback),
            "feedback_negative": sum(1 for f in feedback if f["rating"] == -1),
        },
        "regret_by_agent":    regret_clusters,
        "conflict_by_agent":  conflict_clusters,
        "regret_by_action":   action_clusters,
        "feedback_by_agent":  feedback_clusters,
        "top_failures":       top_failures,
    }


def save_report(report: dict) -> str:
    os.makedirs(os.path.dirname(_REPORT_PATH), exist_ok=True)
    with open(_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    return _REPORT_PATH


def print_report(report: dict) -> None:
    if "error" in report:
        print(f"[failure_miner] {report['error']}")
        return

    s = report["summary"]
    print(f"\n{'='*60}")
    print(f"  Failure Analysis — {report['generated'][:19]}")
    print(f"  {report['total_decisions']} decisions analyzed")
    print(f"{'='*60}")
    print(f"\n  Conflict rate:    {s['conflict_rate']*100:.1f}%  ({s['total_conflicts']} decisions)")
    print(f"  Reflection rate:  {s['reflection_rate']*100:.1f}%  ({s['total_reflected']} decisions)")
    print(f"  High-regret rate: {s['high_regret_count']}/{report['total_decisions']}  (≥{HIGH_REGRET})")
    print(f"  Avg regret:       {s['avg_regret']:.3f}")
    print(f"  Avg latency:      {s['avg_latency_ms']}ms")
    print(f"  User feedback:    {s['feedback_total']} total, {s['feedback_negative']} negative")

    if report["regret_by_agent"]:
        print(f"\n  High-Regret Agents:")
        for agent, v in report["regret_by_agent"].items():
            print(f"    {agent:<22} {v['count']:>3} cases  avg_regret={v['avg_regret']:.3f}  ({v['pct_of_total']}% of all)")

    if report["conflict_by_agent"]:
        print(f"\n  Conflict Rates by Agent:")
        for agent, v in report["conflict_by_agent"].items():
            bar = "█" * int(v["conflict_rate"] * 20)
            print(f"    {agent:<22} {v['conflict_rate']*100:>5.1f}%  {bar}  ({v['conflicts']}/{v['total']})")

    if report["regret_by_action"]:
        print(f"\n  Regret by Action Type:")
        for action, v in report["regret_by_action"].items():
            print(f"    {action:<12} {v['count']:>3} cases  avg_regret={v['avg_regret']:.3f}")

    if report["feedback_by_agent"]:
        print(f"\n  User Feedback by Agent:")
        for agent, v in report["feedback_by_agent"].items():
            print(f"    {agent:<22} 👍{v['positive']} 👎{v['negative']}  approval={v['approval_rate']:.0%}")

    if report["top_failures"]:
        print(f"\n  Top Failure Cases (by regret):")
        for f in report["top_failures"][:5]:
            print(f"    [{f['id']:>4}] {f['agent']:<22} regret={f['regret']:.3f}  {f['task']!r}")

    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Failure miner for the agentic AI system")
    parser.add_argument("--json",  action="store_true", help="Output raw JSON")
    parser.add_argument("--save",  action="store_true", help="Save report to logs/failure_report.json")
    parser.add_argument("--limit", type=int, default=500, help="Max decisions to analyze")
    args = parser.parse_args()

    report = mine(limit=args.limit)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    if args.save:
        path = save_report(report)
        print(f"  Report saved → {path}")
