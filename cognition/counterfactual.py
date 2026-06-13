"""
Counterfactual Routing Scaffolding — P4

For a given decision, re-runs the query through an alternative agent and
compares the result against the original. Used to validate routing decisions
and build evidence for specialization restructuring.

What this is:
  Mechanical comparison — run agent A vs agent B on the same query.
  Compute a naive quality proxy difference.

What this is NOT:
  Statistically valid. Requires 400+ real sessions for stable conclusions.
  Until then, treat each result as an isolated data point, not a trend.

Usage:
  from cognition.counterfactual import simulate_alternative, compare_agents

  # Compare a specific historical decision
  result = simulate_alternative(decision_id=42, alt_agent="python_dev")

  # Compare two agents on an arbitrary query
  result = compare_agents("How do I set a static IP?", "it_networking", "knowledge_learning")

Output schema:
  {
    "query":          str,
    "original_agent": str,
    "alt_agent":      str,
    "original_response_snippet": str,
    "alt_response_snippet":      str,
    "original_quality_proxy":    float,
    "alt_quality_proxy":         float,
    "delta_quality":             float,   # alt - original (positive = alt is better)
    "verdict":        "original_better" | "alt_better" | "equivalent",
    "note":           str,
    "is_real_run":    bool,               # False = dry_run (proxy only, no LLM call)
  }
"""

import sys, os, time
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_DECISIONS_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "decisions.db")

# Quality gap threshold for a verdict to be non-trivial
_VERDICT_THRESHOLD = 0.05


def _load_decision(decision_id: int) -> dict | None:
    """Fetch a single brain_decision by id."""
    import sqlite3
    try:
        c = sqlite3.connect(_DECISIONS_DB)
        row = c.execute(
            "SELECT id, task, action, complexity, brain_agent, router_agent, "
            "final_agent, conflict, reflect, regret "
            "FROM brain_decisions WHERE id = ?",
            (decision_id,)
        ).fetchone()
        c.close()
        if not row:
            return None
        return {
            "id":          row[0], "task":         row[1], "action":      row[2],
            "complexity":  row[3], "brain_agent":  row[4], "router_agent": row[5],
            "final_agent": row[6], "conflict":     row[7], "reflect":     row[8],
            "regret":      row[9],
        }
    except Exception:
        return None


def _proxy_quality(response: str, agent: str, query: str) -> float:
    """
    Naive quality proxy for a response — no LLM, no reflection.

    Heuristics (ordered by reliability):
    1. Non-empty and above minimum length
    2. Contains query-relevant keywords (simple overlap)
    3. Code block present when action is code/build/debug
    4. Response coherence proxy (unique words / total words ratio)

    This is intentionally crude — it's for scaffolding, not evaluation.
    Real quality measurement requires grounded_evaluate() from reflection.py.
    """
    if not response or len(response.strip()) < 20:
        return 0.20

    words = response.lower().split()
    n = len(words)
    if n < 30:
        return 0.35

    # Keyword overlap with query
    q_words = set(query.lower().split())
    resp_words = set(words)
    overlap = len(q_words & resp_words) / max(len(q_words), 1)

    # Lexical diversity (unique words / total)
    diversity = len(set(words)) / max(n, 1)

    # Code block bonus
    code_bonus = 0.08 if ("```" in response or "    " in response) else 0.0

    # Length bonus (longer = more complete, up to a point)
    length_bonus = min(0.10, n / 500)

    quality = 0.55 + (overlap * 0.15) + (diversity * 0.10) + code_bonus + length_bonus
    return round(min(0.95, quality), 3)


def compare_agents(query: str, original_agent: str, alt_agent: str,
                   dry_run: bool = False) -> dict:
    """
    Compare original_agent vs alt_agent on the same query.

    dry_run=True — uses proxy quality only, no actual LLM calls.
    dry_run=False — invokes coordinator with force_agent for both agents.
    """
    if dry_run:
        # Scaffolding mode: return proxy-only result with note
        return {
            "query":                    query,
            "original_agent":           original_agent,
            "alt_agent":                alt_agent,
            "original_response_snippet": "[dry_run — no LLM call]",
            "alt_response_snippet":      "[dry_run — no LLM call]",
            "original_quality_proxy":    0.0,
            "alt_quality_proxy":         0.0,
            "delta_quality":             0.0,
            "verdict":                   "insufficient_data",
            "note":  "dry_run=True: set dry_run=False to invoke agents. "
                     "Statistical validity requires 400+ real sessions.",
            "is_real_run": False,
        }

    # Real run — invoke coordinator with force_agent override
    try:
        from orchestration.coordinator import coordinator

        def _invoke(agent_id: str) -> tuple[str, float]:
            t0 = time.time()
            result = coordinator.invoke({
                "messages":              [{"role": "user", "content": query}],
                "active_agent":          "",
                "task":                  query,
                "result":                "",
                "next_agent":            "",
                "memory":                {},
                "force_agent":           agent_id,
                "brain_decision":        {},
                "reflect":               False,
                "reflect_type":          "none",
                "reflect_level":         "none",
                "contradiction_detected": False,
                "force_reflect_level":   "none",  # skip reflection in comparison runs
            })
            elapsed = time.time() - t0
            response = result["messages"][-1].content if result.get("messages") else ""
            return response, elapsed

        orig_resp, orig_t = _invoke(original_agent)
        alt_resp,  alt_t  = _invoke(alt_agent)

        orig_q = _proxy_quality(orig_resp, original_agent, query)
        alt_q  = _proxy_quality(alt_resp,  alt_agent,      query)
        delta  = round(alt_q - orig_q, 3)

        if abs(delta) < _VERDICT_THRESHOLD:
            verdict = "equivalent"
        elif delta > 0:
            verdict = "alt_better"
        else:
            verdict = "original_better"

        return {
            "query":                     query,
            "original_agent":            original_agent,
            "alt_agent":                 alt_agent,
            "original_response_snippet": orig_resp[:300],
            "alt_response_snippet":      alt_resp[:300],
            "original_quality_proxy":    orig_q,
            "alt_quality_proxy":         alt_q,
            "delta_quality":             delta,
            "original_duration_s":       round(orig_t, 1),
            "alt_duration_s":            round(alt_t,  1),
            "verdict":                   verdict,
            "note": (
                "Proxy-based quality only. No statistical claim. "
                f"Run on {time.strftime('%Y-%m-%d %H:%M')}."
            ),
            "is_real_run": True,
        }

    except Exception as e:
        return {
            "query": query, "original_agent": original_agent, "alt_agent": alt_agent,
            "error": str(e), "verdict": "error", "is_real_run": False,
        }


def simulate_alternative(decision_id: int, alt_agent: str,
                         dry_run: bool = True) -> dict:
    """
    Simulate what would have happened if a different agent had handled
    a specific historical decision.

    dry_run=True (default) — no LLM calls, proxy-only.
    dry_run=False          — full agent invocations (slow, requires Ollama).
    """
    decision = _load_decision(decision_id)
    if not decision:
        return {"error": f"Decision {decision_id} not found", "verdict": "error"}

    result = compare_agents(
        query=decision["task"],
        original_agent=decision["final_agent"],
        alt_agent=alt_agent,
        dry_run=dry_run,
    )
    result["decision_id"]     = decision_id
    result["original_regret"] = decision["regret"]
    result["had_conflict"]    = bool(decision["conflict"])
    result["router_preferred"] = decision["router_agent"]
    return result


def top_counterfactual_candidates(n: int = 10) -> list:
    """
    Return the decisions most worth running counterfactual analysis on.

    Criteria (sorted by priority):
    1. High regret (routing was suboptimal)
    2. Conflict present (brain/router disagreed — run the router's preference)
    3. Struggling agent (it_networking, terse — high conflict agents)
    """
    import sqlite3
    try:
        c = sqlite3.connect(_DECISIONS_DB)
        rows = c.execute(
            "SELECT id, task, brain_agent, router_agent, final_agent, "
            "conflict, regret, reflect "
            "FROM brain_decisions "
            "WHERE conflict = 1 OR regret > 0.1 "
            "ORDER BY regret DESC, conflict DESC "
            "LIMIT ?",
            (n,)
        ).fetchall()
        c.close()
        return [
            {
                "decision_id":     r[0],
                "query":           r[1][:80],
                "original_agent":  r[4],
                "suggested_alt":   r[3] if r[3] and r[3] != "none" else None,
                "conflict":        bool(r[5]),
                "regret":          r[6],
                "priority":        "high" if r[6] > 0.1 else "medium",
            }
            for r in rows
        ]
    except Exception:
        return []


if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser(description="Counterfactual routing analysis")
    p.add_argument("--candidates", action="store_true", help="List top candidates")
    p.add_argument("--decision",   type=int,  help="Decision ID to simulate")
    p.add_argument("--alt-agent",  type=str,  help="Alternative agent to test")
    p.add_argument("--dry-run",    action="store_true", default=True)
    args = p.parse_args()

    if args.candidates:
        candidates = top_counterfactual_candidates()
        print(f"Top counterfactual candidates ({len(candidates)}):")
        for c in candidates:
            print(f"  #{c['decision_id']:>3}  [{c['priority']:>6}]  "
                  f"agent={c['original_agent']:<20} alt={c['suggested_alt'] or '?':<20}  "
                  f"regret={c['regret']:.4f}  conflict={c['conflict']}  "
                  f"q={c['query'][:50]!r}")
    elif args.decision and args.alt_agent:
        result = simulate_alternative(args.decision, args.alt_agent, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: --candidates  OR  --decision ID --alt-agent AGENT [--no-dry-run]")
        print()
        candidates = top_counterfactual_candidates(5)
        print(f"Top 5 candidates:")
        for c in candidates:
            print(f"  #{c['decision_id']}  {c['original_agent']} → {c['suggested_alt']}  "
                  f"regret={c['regret']:.4f}")
