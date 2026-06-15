# Amagra — Architecture

> For technical evaluators. The marketing pages keep the machinery out of sight on purpose; this document does the opposite. Every claim below points at the file that implements it.

Amagra is a **LangGraph `StateGraph`** whose defining feature is **end-to-end observability**: every routing decision, plan step, verification, reflection, and memory access is recorded and replayable. It is not a single reasoning loop — it is a routed, verified, self-correcting graph with a persistent memory and a telemetry substrate.

---

## The graph is real

The coordinator is a compiled LangGraph `StateGraph`, not a hand-rolled while-loop.

[`orchestration/coordinator.py`](../orchestration/coordinator.py)

```python
from langgraph.graph import StateGraph, START, END          # :7

def build_coordinator():                                     # :749
    graph = StateGraph(AgentState)                           # :750
    graph.add_node("coordinator", coordinator_node)          # :752
    graph.add_node("python_dev",  run_python)                # 10 specialist nodes …
    graph.add_node("pipeline",    run_pipeline)              # compound fan-out node
    graph.add_edge(START, "coordinator")                     # :765
    graph.add_conditional_edges("coordinator", route_to_agent, {...})  # :767
    for node in VALID_AGENTS + ["pipeline"]:
        graph.add_edge(node, END)                            # :785
    return graph.compile()                                   # :788
```

- **State** is a typed channel: [`models/state.py`](../models/state.py) → `class AgentState(TypedDict)`.
- **Conditional routing** (`route_to_agent`) dispatches to one of 10 specialist nodes or the compound `pipeline` node.
- The agent registry is canonical and boot-asserted: [`agents/registry.py`](../agents/registry.py).

```
START
  └─► coordinator ──route_to_agent──► { python_dev · dotnet_dev · it_networking · ai_ml ·
                                        web_dev · devops · data_analyst · writer ·
                                        knowledge_learning · terse · pipeline } ──► END
```

---

## Routing: signal-first, LLM only when ambiguous

Routing does **not** start with an LLM call.

1. [`orchestration/query_normalizer.py`](../orchestration/query_normalizer.py) — `QuerySignal` extracts domain / shape / verbosity from raw text with keyword + geometric scoring, in ~1 ms, no model call.
2. [`infrastructure/skill_graph.py`](../infrastructure/skill_graph.py) — 21-node phrase-weighted disambiguation resolves edge-case overlaps.
3. [`orchestration/core_brain.py`](../orchestration/core_brain.py) — only genuinely ambiguous queries escalate to LLM reasoning.
4. [`orchestration/learned_router.py`](../orchestration/learned_router.py) — a trained `LogisticRegression` can override on high-confidence/low-signal cases.

This is why routing is fast and auditable: the common path is deterministic and logged, not a model guess.

---

## Multi-agent, not single-loop

- Each of the 10 agents is a graph node with its own system prompt and memory scope ([`agents/`](../agents/)).
- Compound requests fan out: [`cognition/deep_pipeline.py`](../cognition/deep_pipeline.py) decomposes a query into a plan ([`orchestration/planner.py`](../orchestration/planner.py)), runs multiple agents, and synthesizes.
- Code agents (`python_dev`, `dotnet_dev`) run a dual-trajectory step — two candidates scored by a critic — in [`cognition/dual_trajectory.py`](../cognition/dual_trajectory.py).

---

## Self-correction: verify → reflect → retry

The graph checks its own work; it does not just emit the first token stream.

- **Critic gate** — responses scoring below threshold are regenerated.
- **Step verifier** — [`cognition/step_verifier.py`](../cognition/step_verifier.py) scores each plan step and returns pass / retry / replan / abort to the coordinator.
- **Tiered reflection** — [`cognition/reflection.py`](../cognition/reflection.py) runs grounded eval, then LLM critique + rewrite (up to 3 iterations) only when risk warrants it.
- **Risk gate** — [`cognition/risk_gate.py`](../cognition/risk_gate.py) sets the reflection level (none / light / full) per query.

Error handling is pervasive, not absent: **880+ `try/except` sites** across the Python sources, with retry/abort/regenerate paths in `deep_pipeline`, `step_verifier`, and `reflection`.

---

## Observability is the product

Every state transition is captured and inspectable — this is the layer the project is built around.

| Concern | Module |
|---|---|
| Typed event stream (every decision, step, retrieval) | [`infrastructure/event_bus.py`](../infrastructure/event_bus.py) |
| Session world state (goals, tasks, risks) | [`models/world_model.py`](../models/world_model.py) |
| Live health metrics (UCI: reliability/intelligence/adaptation/productivity) | [`infrastructure/metrics_engine.py`](../infrastructure/metrics_engine.py) |
| Per-request lifecycle | [`models/cognitive_state.py`](../models/cognitive_state.py) |
| Execution traces | [`cognition/run_tracer.py`](../cognition/run_tracer.py), [`cognition/trace_builder.py`](../cognition/trace_builder.py) |
| Decision log + replay | `decision/` ([`graph.py`](../decision/graph.py), [`log.py`](../decision/log.py)) + `POST /ask/replay` |
| Failure clustering | [`cognition/failure_miner.py`](../cognition/failure_miner.py) |
| Counterfactual analysis | [`cognition/counterfactual.py`](../cognition/counterfactual.py) |
| Coherence over time | [`cognition/coherence.py`](../cognition/coherence.py) |

All of it is browsable live in the UI (Event Log, Plan Graph, UCI Dashboard, Memory Browser, Decision Replay) and over the API (`/cos/*`, `/verify/*`, `/telemetry/routing`, `/plan/graph`).

---

## Persistent memory

[`memory_core/`](../memory_core/) — SQLite backend that auto-promotes to a FAISS vector index at 800 entries. Cosine retrieval, outcome-weighted quality scoring, dedup at cosine ≥ 0.93, and an LRU embedding cache (~52× warm). Memory is tenant-scoped via a `ContextVar` through the call chain.

---

## Surface & hardening

- **API**: 100+ endpoints (132 routes) under [`routes/`](../routes/) + [`api.py`](../api.py); OpenAPI at `/docs`.
- **Auth**: deny-by-default `_PUBLIC_PATHS` allowlist, `ADMIN_TOKEN` admin gate, per-tier sliding-window rate limits with `X-RateLimit-*` headers ([`api.py`](../api.py), [`core/api_keys.py`](../core/api_keys.py)).
- **Concurrency**: async `/ask` via executor; `PRAGMA journal_mode=WAL` on all SQLite DBs.
- **Tests**: **702 passing** ([`tests/`](../tests/)) — routes, core, cognition, learning invariants, payment path, tool jail + sandbox + web search.
- **CI/CD**: GitHub Actions (ruff + pytest + Docker build).

---

## Known limitation (stated honestly)

**Agents are text-only today.** There is no live tool execution — no sandboxed code run, web search, or file access yet. That is the one real architectural gap, and it's the headline of the v1.1 roadmap ([`docs/ROADMAP.md`](ROADMAP.md)). Everything above — the graph, routing, verification, observability, memory — exists and is tested today.

---

*Deeper component-by-component detail: [`docs/REFERENCE.md`](REFERENCE.md). Build history: [`docs/HISTORY.md`](HISTORY.md).*
