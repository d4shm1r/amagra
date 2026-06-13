"""
Decision Graph Constructor — Phase 26

Converts flat trace records into a directed graph where routing, memory,
reflection, and outcome are explicit nodes connected by typed edges.

This is the primary research artifact of the system.

Why a graph and not flat JSONL:
  - Flat traces answer "what happened" — the graph answers "why"
  - Causal queries require traversal (e.g., "what memories influenced failure #172?")
  - Agent redundancy analysis requires cross-trace comparison of shared memory nodes
  - Counterfactual evaluation requires reasoning about rejected edges, not just selected ones
  - Dataset versioning requires a stable structural fingerprint

Node types:
  query       — one per decision trace; the entry point
  agent       — one per agent_id (shared across all traces); selected or rejected
  memory      — one per unique memory record accessed
  reflection  — one per reflection event (may not exist for every trace)
  outcome     — one per trace; the terminal node

Edge types:
  SELECTED    — query → agent (brain's choice)
  REJECTED    — query → agent (router's preference when conflict=True)
  RETRIEVED   — query → memory (memory accessed during this query)
  REFLECTED   — outcome → reflection (reflection triggered post-response)
  PRODUCED    — agent → outcome (agent generated this outcome)
  INFLUENCED  — memory → outcome (memory contributed to the response)

Graph schema:
  {
    "version":     str,     # dataset version hash
    "created_at":  str,
    "trace_count": int,
    "nodes": {
      "<node_id>": {
        "type": "query|agent|memory|reflection|outcome",
        ... type-specific fields
      }
    },
    "edges": [
      {"source": str, "target": str, "type": str, "weight": float, "trace_id": int, ...}
    ],
    "stats": { ... }
  }
"""

import hashlib, json, os, sys
from datetime import datetime, timezone

import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_BASE     = os.path.dirname(os.path.abspath(__file__))
_GRAPH_OUT = os.path.join(_BASE, "logs", "decision_graph.json")


# ── Node / Edge constructors ──────────────────────────────────

def _query_node(trace: dict) -> tuple:
    nid = f"query:{trace['id']}"
    node = {
        "type":       "query",
        "trace_id":   trace["id"],
        "query":      trace["query"],
        "timestamp":  trace["timestamp"],
        "signal":     trace["signal"],
        "action":     trace["routing"]["action"],
        "complexity": trace["routing"]["complexity"],
    }
    return nid, node


def _agent_node(agent_id: str) -> tuple:
    nid = f"agent:{agent_id}"
    node = {"type": "agent", "agent_id": agent_id}
    return nid, node


def _memory_node(mem: dict) -> tuple:
    nid = f"memory:{mem['id']}"
    node = {
        "type":     "memory",
        "mem_id":   mem["id"],
        "mem_type": mem.get("type", "unknown"),
        "agent":    mem.get("agent", "unknown"),
        "score":    mem.get("score", 0.0),
    }
    return nid, node


def _reflection_node(trace: dict) -> tuple:
    nid = f"reflection:{trace['id']}"
    node = {
        "type":         "reflection",
        "trace_id":     trace["id"],
        "triggered":    trace["reflection"]["triggered"],
        "reflect_type": trace["reflection"]["type"],
        "level":        trace["reflection"]["level"],
    }
    return nid, node


def _outcome_node(trace: dict) -> tuple:
    nid = f"outcome:{trace['id']}"
    node = {
        "type":             "outcome",
        "trace_id":         trace["id"],
        "quality_proxy":    trace["outcome"]["quality_proxy"],
        "regret":           trace["outcome"]["regret"],
        "confidence":       trace["outcome"]["confidence"],
        "duration_ms":      trace["outcome"]["duration_ms"],
        "response_snippet": trace["outcome"]["response_snippet"][:120],
        "feedback":         trace["feedback"]["rating"],
        "join_method":      trace["labels"]["join_method"],
        "join_confidence":  trace["labels"]["join_confidence"],
    }
    return nid, node


def _edge(source: str, target: str, edge_type: str,
          trace_id: int, weight: float = 1.0, **meta) -> dict:
    return {"source": source, "target": target, "type": edge_type,
            "trace_id": trace_id, "weight": weight, **meta}


# ── Dataset versioning ────────────────────────────────────────

def _version_hash(traces: list) -> str:
    """Stable fingerprint of the dataset — changes when traces change."""
    ids = sorted(t["id"] for t in traces)
    payload = json.dumps({"ids": ids, "schema": "v1.0"}, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Graph builder ─────────────────────────────────────────────

def build_graph(traces: list = None) -> dict:
    """
    Build the decision graph from trace records.

    Each trace contributes:
      - 1 query node
      - 1 or 2 agent nodes (selected + possibly rejected)
      - N memory nodes (one per unique accessed memory)
      - 0 or 1 reflection node
      - 1 outcome node

    Agent and memory nodes are shared across traces (same agent_id → same node,
    same memory_id → same node). This lets the graph expose cross-trace patterns:
    "which memories are retrieved in high-regret decisions?"
    """
    if traces is None:
        from cognition.trace_builder import load_cached_traces, build_traces
        traces = load_cached_traces()
        if not traces:
            traces = build_traces()

    nodes: dict = {}
    edges: list = []

    # Track per-agent and per-memory accumulated stats for nodes
    _agent_stats: dict = {}      # agent_id → {selected, rejected, total_quality}
    _memory_stats: dict = {}     # mem_id   → {retrieved_count, avg_score}

    for t in traces:
        tid = t["id"]

        # ── Add query node ────────────────────────────────────
        q_id, q_node = _query_node(t)
        nodes[q_id] = q_node

        # ── Add agent nodes + SELECTED / REJECTED edges ───────
        sel_agent = t["routing"]["final_agent"]
        sel_id    = f"agent:{sel_agent}"
        if sel_id not in nodes:
            _, a_node = _agent_node(sel_agent)
            nodes[sel_id] = a_node
        edges.append(_edge(q_id, sel_id, "SELECTED", tid))

        # Accumulate agent stats
        if sel_agent not in _agent_stats:
            _agent_stats[sel_agent] = {"selected": 0, "rejected": 0, "quality_sum": 0.0}
        _agent_stats[sel_agent]["selected"] += 1
        _agent_stats[sel_agent]["quality_sum"] += t["outcome"]["quality_proxy"]

        # Rejected agent (when conflict)
        for alt in t["routing"].get("alternative_agents", []):
            alt_id = f"agent:{alt}"
            if alt_id not in nodes:
                _, a_node = _agent_node(alt)
                nodes[alt_id] = a_node
            edges.append(_edge(q_id, alt_id, "REJECTED", tid,
                                conflict_resolved_to=sel_agent))
            if alt not in _agent_stats:
                _agent_stats[alt] = {"selected": 0, "rejected": 0, "quality_sum": 0.0}
            _agent_stats[alt]["rejected"] += 1

        # ── Outcome node ──────────────────────────────────────
        out_id, out_node = _outcome_node(t)
        nodes[out_id] = out_node

        # PRODUCED edge: agent → outcome
        edges.append(_edge(sel_id, out_id, "PRODUCED", tid,
                           quality=t["outcome"]["quality_proxy"]))

        # ── Memory nodes + RETRIEVED / INFLUENCED edges ───────
        for mem in t["memory"]["accessed"]:
            mem_id_str = f"memory:{mem['id']}"
            if mem_id_str not in nodes:
                _, m_node = _memory_node(mem)
                nodes[mem_id_str] = m_node
            else:
                # Update score to running max (keep highest relevance score seen)
                if mem["score"] > nodes[mem_id_str].get("score", 0):
                    nodes[mem_id_str]["score"] = mem["score"]

            # RETRIEVED edge: query → memory
            edges.append(_edge(q_id, mem_id_str, "RETRIEVED", tid,
                               weight=mem["score"]))
            # INFLUENCED edge: memory → outcome
            edges.append(_edge(mem_id_str, out_id, "INFLUENCED", tid,
                               weight=mem["score"]))

            # Accumulate memory stats
            mid = mem["id"]
            if mid not in _memory_stats:
                _memory_stats[mid] = {"count": 0, "score_sum": 0.0}
            _memory_stats[mid]["count"] += 1
            _memory_stats[mid]["score_sum"] += mem["score"]

        # ── Reflection node + REFLECTED edge ──────────────────
        if t["reflection"]["triggered"]:
            ref_id, ref_node = _reflection_node(t)
            nodes[ref_id] = ref_node
            # REFLECTED: outcome → reflection (reflection is triggered by the outcome)
            edges.append(_edge(out_id, ref_id, "REFLECTED", tid))

    # Annotate agent nodes with accumulated stats
    for agent_id, stats in _agent_stats.items():
        nid = f"agent:{agent_id}"
        if nid in nodes:
            n_sel = stats["selected"]
            nodes[nid]["selected_count"] = n_sel
            nodes[nid]["rejected_count"] = stats["rejected"]
            nodes[nid]["avg_quality"]    = round(stats["quality_sum"] / max(n_sel, 1), 3)

    # Annotate memory nodes with retrieval frequency
    for mem_id, stats in _memory_stats.items():
        nid = f"memory:{mem_id}"
        if nid in nodes:
            nodes[nid]["retrieval_count"] = stats["count"]
            nodes[nid]["avg_score"]       = round(stats["score_sum"] / stats["count"], 3)

    # ── Graph stats ───────────────────────────────────────────
    node_types = {}
    for n in nodes.values():
        t = n["type"]
        node_types[t] = node_types.get(t, 0) + 1
    edge_types = {}
    for e in edges:
        et = e["type"]
        edge_types[et] = edge_types.get(et, 0) + 1

    return {
        "version":     _version_hash(traces),
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "trace_count": len(traces),
        "nodes":       nodes,
        "edges":       edges,
        "stats": {
            "node_count":   len(nodes),
            "edge_count":   len(edges),
            "by_node_type": node_types,
            "by_edge_type": edge_types,
            "avg_degree":   round(len(edges) / max(len(nodes), 1), 2),
        },
    }


# ── Causal query functions ────────────────────────────────────

def causal_path(graph: dict, decision_id: int) -> dict:
    """
    Trace the full causal path for a single decision.

    Returns:
      query        — the input and signal
      selected     — the agent that was chosen + why
      rejected     — alternatives that were not chosen
      memories     — what the agent retrieved
      outcome      — quality proxy, regret, response snippet
      reflection   — whether reflection was triggered
      causal_flags — highlighted issues (high regret, conflict, struggling memory)
    """
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    q_id  = f"query:{decision_id}"
    out_id = f"outcome:{decision_id}"
    ref_id = f"reflection:{decision_id}"

    if q_id not in nodes:
        return {"error": f"Decision {decision_id} not found in graph"}

    q_node   = nodes[q_id]
    out_node = nodes.get(out_id, {})
    ref_node = nodes.get(ref_id)

    # Edges involving this trace
    trace_edges = [e for e in edges if e["trace_id"] == decision_id]

    selected = [e["target"] for e in trace_edges if e["type"] == "SELECTED"]
    rejected = [e["target"] for e in trace_edges if e["type"] == "REJECTED"]
    memories = [
        {**nodes.get(e["target"], {}), "score": e["weight"]}
        for e in trace_edges if e["type"] == "RETRIEVED"
    ]

    selected_node = nodes.get(selected[0]) if selected else None

    # Causal flags — what went wrong?
    flags = []
    regret = out_node.get("regret", 0.0)
    quality = out_node.get("quality_proxy", 0.0)
    if rejected:
        flags.append({
            "type": "routing_conflict",
            "detail": f"Brain chose {selected[0].replace('agent:','')} but router preferred "
                      f"{', '.join(a.replace('agent:','') for a in rejected)}"
        })
    if regret > 0.05:
        flags.append({"type": "high_regret",
                      "detail": f"regret={regret:.4f} — routing was likely suboptimal"})
    if quality < 0.68:
        flags.append({"type": "low_quality",
                      "detail": f"quality_proxy={quality:.3f} — below threshold"})

    # Memory quality flag — were low-quality memories retrieved?
    low_q_mem = [m for m in memories if m.get("score", 1.0) < 0.40]
    if low_q_mem:
        flags.append({"type": "low_relevance_memory",
                      "detail": f"{len(low_q_mem)} memories retrieved with score < 0.40"})

    return {
        "decision_id": decision_id,
        "query":       q_node.get("query", ""),
        "signal":      q_node.get("signal", {}),
        "action":      q_node.get("action", ""),
        "complexity":  q_node.get("complexity", ""),
        "timestamp":   q_node.get("timestamp", ""),
        "selected_agent": selected_node.get("agent_id") if selected_node else None,
        "rejected_agents": [a.replace("agent:", "") for a in rejected],
        "memories_retrieved": len(memories),
        "top_memories": memories[:4],
        "outcome": {
            "quality_proxy":    out_node.get("quality_proxy"),
            "regret":           out_node.get("regret"),
            "confidence":       out_node.get("confidence"),
            "duration_ms":      out_node.get("duration_ms"),
            "response_snippet": out_node.get("response_snippet", ""),
            "feedback":         out_node.get("feedback"),
        },
        "reflection": {
            "triggered":    ref_node is not None and ref_node.get("triggered", False),
            "reflect_type": ref_node.get("reflect_type") if ref_node else None,
        },
        "causal_flags": flags,
    }


def agent_subgraph(graph: dict, agent_id: str) -> dict:
    """
    Extract all decisions where agent_id was selected or rejected.
    Returns summary stats + first 20 decision IDs.
    """
    edges = graph.get("edges", [])
    nodes = graph.get("nodes", {})
    a_nid = f"agent:{agent_id}"

    selected_in  = [e["trace_id"] for e in edges if e["type"] == "SELECTED" and e["target"] == a_nid]
    rejected_in  = [e["trace_id"] for e in edges if e["type"] == "REJECTED" and e["target"] == a_nid]
    produced     = [e for e in edges if e["type"] == "PRODUCED" and e["source"] == a_nid]

    qualities = [e.get("quality", 0) for e in produced]
    avg_quality = round(sum(qualities) / len(qualities), 3) if qualities else 0.0

    # Memories most frequently retrieved when this agent is selected
    mem_counts: dict = {}
    for sel_tid in selected_in:
        for e in edges:
            if e["trace_id"] == sel_tid and e["type"] == "RETRIEVED":
                mem_id = e["target"]
                mem_counts[mem_id] = mem_counts.get(mem_id, 0) + 1
    top_memories = sorted(mem_counts.items(), key=lambda x: -x[1])[:5]

    return {
        "agent_id":       agent_id,
        "selected_count": len(selected_in),
        "rejected_count": len(rejected_in),
        "avg_quality":    avg_quality,
        "selected_trace_ids": selected_in[:20],
        "rejected_trace_ids": rejected_in[:20],
        "top_memories": [
            {**nodes.get(m_id, {}), "times_retrieved": cnt}
            for m_id, cnt in top_memories
        ],
    }


def memory_influence(graph: dict, memory_id: int) -> dict:
    """
    Find all decisions that retrieved a specific memory and their outcomes.
    """
    m_nid  = f"memory:{memory_id}"
    nodes  = graph.get("nodes", {})
    edges  = graph.get("edges", [])

    if m_nid not in nodes:
        return {"error": f"Memory {memory_id} not in graph"}

    mem_node = nodes[m_nid]
    retrievals = [e for e in edges if e["type"] == "RETRIEVED" and e["target"] == m_nid]
    trace_ids  = [e["trace_id"] for e in retrievals]

    outcomes = []
    for tid in trace_ids:
        out = nodes.get(f"outcome:{tid}", {})
        outcomes.append({
            "trace_id":      tid,
            "quality_proxy": out.get("quality_proxy"),
            "regret":        out.get("regret"),
            "feedback":      out.get("feedback"),
        })

    avg_quality = (
        sum(o["quality_proxy"] for o in outcomes if o["quality_proxy"] is not None)
        / max(len(outcomes), 1)
    )

    return {
        "memory_id":       memory_id,
        "memory_type":     mem_node.get("mem_type"),
        "agent":           mem_node.get("agent"),
        "retrieval_count": mem_node.get("retrieval_count", len(retrievals)),
        "avg_score":       mem_node.get("avg_score"),
        "avg_outcome_quality": round(avg_quality, 3),
        "trace_outcomes":  outcomes[:20],
    }


# ── I/O ───────────────────────────────────────────────────────

def save_graph(graph: dict, path: str = _GRAPH_OUT) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(graph, f)
    return path


def load_graph(path: str = _GRAPH_OUT) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Decision graph builder and causal query tool")
    p.add_argument("--build",       action="store_true", help="Build and save graph")
    p.add_argument("--causal",      type=int,            help="Show causal path for decision ID")
    p.add_argument("--agent",       type=str,            help="Agent subgraph summary")
    p.add_argument("--memory",      type=int,            help="Memory influence analysis")
    args = p.parse_args()

    if args.build or (not args.causal and not args.agent and not args.memory):
        print("Building decision graph...")
        from cognition.trace_builder import load_cached_traces
        traces = load_cached_traces()
        g = build_graph(traces)
        path = save_graph(g)
        s = g["stats"]
        print(f"Version: {g['version']}")
        print(f"Traces:  {g['trace_count']}")
        print(f"Nodes:   {s['node_count']}  ({s['by_node_type']})")
        print(f"Edges:   {s['edge_count']}  ({s['by_edge_type']})")
        print(f"Avg deg: {s['avg_degree']}")
        print(f"Saved:   {path}")
    else:
        g = load_graph()
        if not g:
            print("No graph found — run with --build first")
        elif args.causal:
            print(json.dumps(causal_path(g, args.causal), indent=2))
        elif args.agent:
            print(json.dumps(agent_subgraph(g, args.agent), indent=2))
        elif args.memory:
            print(json.dumps(memory_influence(g, args.memory), indent=2))
