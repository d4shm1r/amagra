"""
Decision Trace Dataset Builder — P0

Reconstructs a full decision trace for every brain_decision by joining:
  brain_decisions  — routing decision, conflict, reflect, regret
  sessions         — actual response text, confidence, duration
  retrieval_audits — which memories were accessed
  feedback         — user ratings (sparse; empty = no ratings yet)
  query_normalizer — signal fields re-computed retroactively (not stored in DB)

Signal fields were added in Version-1 UI but were never written to decisions.db,
so we retroactively compute them with normalize(). This means eval-era decisions
get the same signal representation as live sessions — consistent labeling.

Sessions ↔ decisions have no FK. Join strategy:
  1. SequenceMatcher ratio ≥ 0.85 on first 100 chars of task vs user_input.
  2. If no session matches → mark is_eval=True (came from auto_train.py).

Output:
  logs/trace_dataset.jsonl  — one JSON line per trace
  logs/trace_dataset_stats.json — coverage report

Also used by specialization.py and the /data/* API endpoints.
"""

import sqlite3
import json
import os
import sys
import difflib
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DECISIONS   = os.path.join(_BASE, "logs",   "decisions.db")
_SESSIONS    = os.path.join(_BASE, "logs",   "sessions.db")
_FEEDBACK    = os.path.join(_BASE, "logs",   "feedback.db")
_MEMORY_DB   = os.path.join(_BASE, "memory", "agent_memory.db")
_OUT_JSONL   = os.path.join(_BASE, "logs",   "trace_dataset.jsonl")
_OUT_STATS   = os.path.join(_BASE, "logs",   "trace_dataset_stats.json")


# ── Loaders ───────────────────────────────────────────────────

def _load_sessions() -> list:
    try:
        c = sqlite3.connect(_SESSIONS)
        # decision_id column may not exist on older schemas
        try:
            rows = c.execute(
                "SELECT id, timestamp, user_input, response, agent, duration_ms, confidence, "
                "COALESCE(decision_id, NULL) FROM sessions ORDER BY id"
            ).fetchall()
            c.close()
            return [
                {"id": r[0], "timestamp": r[1], "user_input": r[2],
                 "response": r[3], "agent": r[4], "duration_ms": r[5],
                 "confidence": float(r[6] or 0.67), "decision_id": r[7]}
                for r in rows
            ]
        except Exception:
            rows = c.execute(
                "SELECT id, timestamp, user_input, response, agent, duration_ms, confidence "
                "FROM sessions ORDER BY id"
            ).fetchall()
            c.close()
            return [
                {"id": r[0], "timestamp": r[1], "user_input": r[2],
                 "response": r[3], "agent": r[4], "duration_ms": r[5],
                 "confidence": float(r[6] or 0.67), "decision_id": None}
                for r in rows
            ]
    except Exception:
        return []


def _load_feedback() -> dict:
    """Returns {query_key: {rating, note}} keyed by first 80 chars lowercased."""
    try:
        c = sqlite3.connect(_FEEDBACK)
        rows = c.execute("SELECT query, agent, rating, note FROM feedback").fetchall()
        c.close()
        out = {}
        for r in rows:
            key = (r[0] or "").lower().strip()[:80]
            out[key] = {"agent": r[1], "rating": r[2], "note": r[3] or ""}
        return out
    except Exception:
        return {}


def _load_retrieval_audits() -> dict:
    """Returns {query_key: {retrieved, count}} keyed by first 80 chars lowercased."""
    try:
        c = sqlite3.connect(_MEMORY_DB)
        rows = c.execute(
            "SELECT query, retrieved, count FROM retrieval_audits ORDER BY id"
        ).fetchall()
        c.close()
        out: dict = {}
        for r in rows:
            key = (r[0] or "").lower().strip()[:80]
            try:
                retrieved = json.loads(r[1]) if r[1] else []
            except Exception:
                retrieved = []
            # Keep the audit with the most entries for duplicate keys
            if key not in out or len(retrieved) > len(out[key]["retrieved"]):
                out[key] = {"retrieved": retrieved, "count": r[2] or len(retrieved)}
        return out
    except Exception:
        return {}


# ── Join helpers ──────────────────────────────────────────────

_SESSION_BY_DECISION_ID: dict = {}   # decision_id → session (built on first use)
_SESSION_BY_HASH: dict = {}          # text_hash    → session


def _init_session_indexes(sessions: list) -> None:
    """Pre-build lookup indexes for fast, deterministic session matching."""
    global _SESSION_BY_DECISION_ID, _SESSION_BY_HASH
    _SESSION_BY_DECISION_ID = {}
    _SESSION_BY_HASH = {}
    for s in sessions:
        if s.get("decision_id"):
            _SESSION_BY_DECISION_ID[int(s["decision_id"])] = s
        # Deterministic text hash (first 100 chars, stripped, lowercased)
        h = s["user_input"].lower().strip()[:100]
        _SESSION_BY_HASH[h] = s


def _match_session(task: str, decision_id: int, sessions: list) -> tuple:
    """
    Match a decision to a session using a 3-level hierarchy.

    Returns (session | None, join_method, join_confidence).

    Level 1 — FK (session_id stored in brain_decisions):
      Exact, deterministic. join_confidence = 1.0.

    Level 2 — Text hash equality (first 100 chars lowercased):
      Near-exact. join_confidence = 0.97.

    Level 3 — SequenceMatcher similarity ≥ 0.85:
      Probabilistic. join_confidence = similarity_ratio (0.85–1.0).
      Label leakage risk: flagged in join_audit. Do NOT use for training
      labels without manual verification.

    Returns (None, "none", 0.0) when no match is found (eval decisions).
    """
    # Level 1: FK link
    if decision_id and decision_id in _SESSION_BY_DECISION_ID:
        return _SESSION_BY_DECISION_ID[decision_id], "fk", 1.0

    # Level 2: text hash
    h = task.lower().strip()[:100]
    if h in _SESSION_BY_HASH:
        return _SESSION_BY_HASH[h], "text_hash", 0.97

    # Level 3: similarity (probabilistic — mark with confidence < 1.0)
    best, best_r = None, 0.0
    for s in sessions:
        r = difflib.SequenceMatcher(None, h, s["user_input"].lower().strip()[:100]).ratio()
        if r > best_r:
            best_r, best = r, s
    if best_r >= 0.85:
        return best, "text_similarity", round(best_r, 3)

    return None, "none", 0.0


def _quality_proxy(regret: float, conflict: bool, reflect: bool,
                   feedback_rating: Optional[int]) -> float:
    """
    Derive a [0, 1] quality proxy from available signals.

    Signal priority (strongest first):
      1. User feedback (±0.15/−0.30)
      2. Reflection (was a grounded eval run?)
      3. Regret (high regret = suboptimal routing)
      4. Conflict (brain/router disagreed)
    """
    base            = 0.82 if reflect else 0.72
    regret_penalty  = min(0.25, float(regret or 0) * 0.4)
    conflict_penalty = 0.08 if conflict else 0.0
    fb_bonus        = 0.0
    if feedback_rating == 1:
        fb_bonus = 0.15
    elif feedback_rating == -1:
        fb_bonus = -0.30
    return round(max(0.0, min(1.0, base - regret_penalty - conflict_penalty + fb_bonus)), 3)


# ── Core builder ─────────────────────────────────────────────

def build_traces(limit: int = 0) -> list:
    """
    Build one trace record per brain_decision.
    Returns list of dicts; each dict is one complete trace.
    """
    from orchestration.query_normalizer import normalize

    c = sqlite3.connect(_DECISIONS)
    # session_id column may not exist on older schemas
    try:
        _cols = [r[1] for r in c.execute("PRAGMA table_info(brain_decisions)").fetchall()]
        _has_session_id = "session_id" in _cols
        _sel = (
            "SELECT id, timestamp, task, action, complexity, brain_agent, router_agent, "
            "final_agent, conflict, reflect, reflect_type, duration_ms, regret"
            + (", COALESCE(session_id, NULL)" if _has_session_id else ", NULL")
            + " FROM brain_decisions ORDER BY id"
        )
    except Exception:
        _sel = (
            "SELECT id, timestamp, task, action, complexity, brain_agent, router_agent, "
            "final_agent, conflict, reflect, reflect_type, duration_ms, regret, NULL "
            "FROM brain_decisions ORDER BY id"
        )
    if limit > 0:
        _sel += f" LIMIT {limit}"
    rows = c.execute(_sel).fetchall()
    c.close()

    sessions  = _load_sessions()
    _init_session_indexes(sessions)
    feedback  = _load_feedback()
    audits    = _load_retrieval_audits()

    traces = []
    for row in rows:
        (dec_id, ts, task, action, complexity,
         brain_agent, router_agent, final_agent,
         conflict, reflect, reflect_type, duration_ms, regret, stored_session_id) = row

        # ── Signal (retroactively computed) ───────────────────
        try:
            sig = normalize(task)
            signal = {
                "domain":    sig.domain,
                "shape":     sig.answer_shape,
                "verbosity": sig.verbosity,
                "conf":      round(float(sig.domain_conf), 3),
            }
        except Exception:
            signal = {"domain": "unknown", "shape": "unknown",
                      "verbosity": "normal", "conf": 0.0}

        # ── Memory accessed ───────────────────────────────────
        audit_key = task.lower().strip()[:80]
        audit     = audits.get(audit_key, {"retrieved": [], "count": 0})
        mem_accessed = [
            {"id": m.get("id"), "score": round(float(m.get("score", 0)), 3),
             "type": m.get("type"), "agent": m.get("agent")}
            for m in (audit["retrieved"] or [])
        ]

        # ── Session join (3-level hierarchy) ──────────────────
        session, join_method, join_conf = _match_session(
            task, stored_session_id, sessions
        )
        is_eval       = session is None
        response_snip = ""
        confidence    = 0.67
        if session:
            response_snip = (session["response"] or "")[:200]
            confidence    = session["confidence"]

        # ── Feedback lookup ───────────────────────────────────
        fb_key  = task.lower().strip()[:80]
        fb      = feedback.get(fb_key, {})
        fb_rating = fb.get("rating", None)

        # ── Quality proxy ─────────────────────────────────────
        qp = _quality_proxy(
            regret=regret or 0.0,
            conflict=bool(conflict),
            reflect=bool(reflect),
            feedback_rating=fb_rating,
        )

        # ── Alternatives (when conflict occurred) ─────────────
        alt_agents = []
        if conflict and router_agent and router_agent not in ("none", ""):
            alt_agents = [router_agent]

        traces.append({
            "id":        dec_id,
            "timestamp": ts,
            "query":     task,
            "signal":    signal,
            "routing": {
                "brain_agent":        brain_agent,
                "router_agent":       router_agent or "none",
                "final_agent":        final_agent,
                "conflict":           bool(conflict),
                "action":             action,
                "complexity":         complexity,
                "alternative_agents": alt_agents,
            },
            "reflection": {
                "triggered": bool(reflect),
                "type":      reflect_type,
                # reflect_level not persisted pre-Phase-19; None = unknown
                "level":     None,
            },
            "memory": {
                "accessed": mem_accessed,
                "count":    len(mem_accessed),
            },
            "outcome": {
                "response_snippet": response_snip,
                "confidence":       round(confidence, 3),
                "regret":           round(float(regret or 0), 4),
                "duration_ms":      duration_ms,
                "quality_proxy":    qp,
            },
            "feedback": {
                "rating": fb_rating,
                "note":   fb.get("note", ""),
            },
            "labels": {
                "correct_agent":    final_agent,
                "quality_proxy":    qp,
                "is_eval":          is_eval,
                "has_response":     not is_eval,
                "has_feedback":     fb_rating is not None,
                "has_memory":       len(mem_accessed) > 0,
                "has_conflict":     bool(conflict),
                "has_reflection":   bool(reflect),
                # Join quality — affects label reliability for training
                # "fk" (1.0) and "text_hash" (0.97) are safe for training.
                # "text_similarity" (0.85–0.96) should be verified before use as hard labels.
                "join_method":      join_method,
                "join_confidence":  join_conf,
                "label_trustworthy": join_method in ("fk", "text_hash", "none"),
            },
        })

    return traces


# ── Stats ─────────────────────────────────────────────────────

def dataset_stats(traces: list) -> dict:
    """Compute coverage and distribution stats for the trace dataset."""
    n = len(traces)
    if n == 0:
        return {"total": 0}

    def pct(k):
        return round(sum(1 for t in traces if t["labels"][k]) / n, 3)

    agent_dist  = {}
    domain_dist = {}
    action_dist = {}
    for t in traces:
        a = t["routing"]["final_agent"]
        d = t["signal"]["domain"]
        x = t["routing"]["action"]
        agent_dist[a]  = agent_dist.get(a, 0) + 1
        domain_dist[d] = domain_dist.get(d, 0) + 1
        action_dist[x] = action_dist.get(x, 0) + 1

    real     = sum(1 for t in traces if not t["labels"]["is_eval"])
    avg_qp   = round(sum(t["outcome"]["quality_proxy"] for t in traces) / n, 3)
    avg_mem  = round(sum(t["memory"]["count"] for t in traces) / n, 2)
    avg_regr = round(sum(t["outcome"]["regret"] for t in traces) / n, 4)

    # Join audit — how was each real session matched?
    join_methods = {"fk": 0, "text_hash": 0, "text_similarity": 0, "none": 0}
    prob_joins   = []   # text_similarity joins (probabilistic, need review)
    for t in traces:
        m = t["labels"].get("join_method", "none")
        join_methods[m] = join_methods.get(m, 0) + 1
        if m == "text_similarity":
            prob_joins.append({
                "id":    t["id"],
                "query": t["query"][:60],
                "conf":  t["labels"]["join_confidence"],
            })

    return {
        "total":              n,
        "real_sessions":      real,
        "eval_decisions":     n - real,
        "avg_quality_proxy":  avg_qp,
        "avg_memories_per_query": avg_mem,
        "avg_regret":         avg_regr,
        "coverage": {
            "response_pct":   pct("has_response"),
            "memory_pct":     pct("has_memory"),
            "feedback_pct":   pct("has_feedback"),
            "reflection_pct": pct("has_reflection"),
            "conflict_pct":   pct("has_conflict"),
        },
        # Identifies how many labels are deterministic vs probabilistic
        "join_audit": {
            "methods":         join_methods,
            "trustworthy":     join_methods["fk"] + join_methods["text_hash"] + join_methods["none"],
            "probabilistic":   join_methods["text_similarity"],
            "probabilistic_traces": prob_joins[:10],  # first 10 for review
        },
        "agent_distribution":  agent_dist,
        "domain_distribution": domain_dist,
        "action_distribution": action_dist,
    }


# ── I/O ───────────────────────────────────────────────────────

def save_traces(traces: list, path: str = _OUT_JSONL) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")
    return path


def save_stats(stats: dict, path: str = _OUT_STATS) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(stats, f, indent=2)
    return path


def load_cached_traces() -> list:
    """Load traces from the saved JSONL file (fast path for API)."""
    if not os.path.exists(_OUT_JSONL):
        return []
    traces = []
    with open(_OUT_JSONL) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except Exception:
                    pass
    return traces


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Build decision trace dataset")
    p.add_argument("--limit",  type=int, default=0,       help="Max decisions (0=all)")
    p.add_argument("--output", default=_OUT_JSONL,        help="Output JSONL path")
    p.add_argument("--quiet",  action="store_true")
    args = p.parse_args()

    print("Building decision trace dataset...")
    traces = build_traces(limit=args.limit)
    stats  = dataset_stats(traces)

    if not args.quiet:
        print(f"\n{'='*50}")
        print(f"Total traces:      {stats['total']}")
        print(f"Real sessions:     {stats['real_sessions']}")
        print(f"Eval decisions:    {stats['eval_decisions']}")
        print(f"Avg quality proxy: {stats['avg_quality_proxy']}")
        print(f"Avg memories/q:    {stats['avg_memories_per_query']}")
        print("\nCoverage:")
        for k, v in stats["coverage"].items():
            print(f"  {k:<20} {v*100:.0f}%")
        print("\nAgent distribution:")
        for a, n in sorted(stats["agent_distribution"].items(), key=lambda x: -x[1]):
            print(f"  {a:<25} {n}")
        print("\nDomain distribution:")
        for d, n in sorted(stats["domain_distribution"].items(), key=lambda x: -x[1]):
            print(f"  {d:<20} {n}")
        print(f"{'='*50}")

    out = save_traces(traces, args.output)
    save_stats(stats)
    print(f"\nSaved: {out}")
    print(f"Stats: {_OUT_STATS}")
