# Amagra — Technical Reference

A locally-running cognitive AI platform built on phi4-mini (3.8B) and LangGraph. Natural language queries are classified by a deterministic signal engine, routed to a specialist agent, executed with persistent semantic memory, and governed by a Cognitive OS that tracks world state, health scores, and execution plans. Everything runs on an RTX 2050 — no cloud dependency.

**Version:** v1.1.1  
**Stack:** phi4-mini · Ollama · LangGraph · FastAPI · React · FAISS · SQLite · nomic-embed-text · Stripe · SendGrid

---

## What It Does

1. **Classifies the query** — `QuerySignal` extracts domain, answer shape, and verbosity from raw text in ~1ms using keyword heuristics and geometric scoring. No LLM call required for routing.
2. **Resolves ambiguity** — `skill_graph.py` maps the signal through 21 skill nodes with a disambiguation layer. LLM-based fallback fires only on genuinely ambiguous queries.
3. **Plans complex requests** — compound queries are decomposed into a `Plan` (DAG of `PlanStep` objects with `depends_on`, `agent`, `uncertainty`, `success_criteria`). Parallel groups execute concurrently.
4. **Executes with memory** — each agent retrieves semantically relevant past knowledge from a FAISS vector index, generates a response, and writes it back.
5. **Verifies and reflects** — a step verifier scores each plan step (pass/retry/replan/abort). Response quality triggers tiered reflection (full / light / none). Routing weights self-update after every run.
6. **Maintains world state** — `WorldModel` tracks completed tasks, active goals, and long-term context. `MetricsEngine` computes four UCI dimensions continuously. `EventBus` records every state transition.

---

## Ten Specialist Agents

Canonical registry: `agents/registry.py` (`AGENT_MAP`). A boot assertion in `coordinator.py` fails fast if any routing code references an id not declared here.

| Agent | Domain |
|-------|--------|
| `python_dev` | Python, FastAPI, async, pytest, TDD, coverage |
| `dotnet_dev` | C#, .NET, Blazor, ASP.NET Core, Entity Framework |
| `it_networking` | DNS, SSH, firewalls, networking, cloud infra |
| `ai_ml` | PyTorch, LangChain, embeddings, model evaluation |
| `web_dev` | HTML/CSS/JS, React, frontend tooling |
| `devops` | Docker, CI/CD, deploy, build toolchains |
| `data_analyst` | pandas, SQL, visualization, analysis |
| `writer` | Documentation, audience-framed prose |
| `knowledge_learning` | General explanation, concepts, research |
| `terse` | Short lookups and quick commands |

Code agents (dual-trajectory eligible): `python_dev`, `dotnet_dev`.

---

## System Architecture

```
User input
  ↓
normalize(query) → QuerySignal          [domain, shape, verbosity — <1ms, no LLM]
  ↓
skill_graph.disambiguate()              [21-node skill graph, confidence-weighted]
  ↓
core_brain.think()                      [routing decision + regret + reflect flag]
  ↓
dual_trajectory_invoke()                [code/debug only: generate A+B, critic picks]
  ↓
specialist agent                        [executes with memory context + tools]
  ↓
_run_with_reflection()                  [tiered reflection loop if flagged]
  ↓
apply_learning_update()                 [single weight update — only mutation path]
  ↓
log_decision()                          [observability]
  ↓
response
```

**Core invariant:** `apply_learning_update()` is the only function that modifies agent weights. Nothing else writes to `agent_weights` directly.

---

## Signal-First Routing (QuerySignal)

Every query is normalized before any agent selection. No LLM call.

```python
QuerySignal(
  domain:       "networking" | "python" | "blazor" | "ai_ml" | "general"
  domain_conf:  float          # 0.0–1.0; full float precision; >0.3 is routing-worthy
  answer_shape: "factual" | "code" | "debug" | "procedural" | "comparison" | "explanation"
  verbosity:    "terse" | "normal" | "detailed"
  action:       "build" | "debug" | "research" | "explain" | "lookup" | ...
)
```

**Confidence formula** (C1-smooth, no hard ceiling):
```
c(hits) = 1 − exp(−0.40 × hits)
  hits=1 → 0.33   hits=3 → 0.70   hits=5 → 0.86   hits=10 → 0.98
```

**Routing priority in `core_brain.think()`:**
1. `answer_shape == "factual"` → terse (no verbosity check)
2. `verbosity == "terse"` → terse
3. `domain_conf > 0.3` → domain agent via `DOMAIN_TO_AGENT`
4. Learned router override: if `lr_conf > 0.85` and `signal_conf < 0.50`, LR wins
5. Ambiguous → LLM clarify fallback

**Routing accuracy:**

| Mode | Accuracy |
|------|----------|
| Action-first baseline (50 prompts) | 70% |
| Signal-first (50 prompts) | 92% |
| Signal-first + all fixes (100 prompts) | 97% |
| QuerySignal only, no LLM (ablation) | 99% |

---

## Learning Kernel

All weight changes flow exclusively through `learning.apply_learning_update()`.

**Per-decision update pipeline:**
```
1. calibration   EMA(confidence, performance), alpha=0.1
2. signal        L = performance − 0.5 × regret
3. instability   I = 0.4×regret + 0.4×|cal_bias| + 0.2×wt_variance
4. alpha         BASE_ALPHA / (1 + exp(8 × (I − 0.5)))   ← C1-smooth sigmoid
5. delta         clamp(alpha × (L − weight), −0.02, +0.02)
6. decay         non-chosen agents drift 0.001 toward 1.0
```

**Performance signal sources:**
- Reflected tasks: `reflection_score` from `grounded_evaluate()`
- Non-reflected: proxy 0.75 (no conflict) / 0.55 (conflict)
- User 👍: performance = 0.90
- User 👎: performance = 0.25

---

## Memory System

**Retrieval score formula:**
```
score = cosine_similarity(q, m) × quality × type_weight × freshness
freshness = exp(−Δt × ln2 / 30)    # half-life 30 days; floor 0.05
```

**Type weights:**

| Type | Weight | Rationale |
|------|--------|-----------|
| reflection | 1.4 | Grounded quality signal, most actionable |
| failure | 1.3 | Negative examples are high value |
| procedural | 1.2 | Reusable patterns |
| code | 1.2 | Reusable implementations |
| lesson | 1.1 | Structured explanations |
| episodic | 1.0 | Conversation history baseline |
| chat | 1.0 | Raw history baseline |
| seed | 0.8 | Auto-train seeded memories rank below real ones |

**Quality update** (log-odds, C1-smooth):
```python
l = ln(q / (1 − q))
l_new = l + 4.0 × delta
q_new = sigmoid(l_new)
```
Memories near q=0.9 resist small noise; memories near q=0.5 update linearly.

**Backend:** FAISSBackend (auto-promotes from SQLiteBackend at 800 entries). 628+ vectors, search P50 = 0.38ms. LRU embedding cache: 52× speedup, ~40% hit rate in real sessions.

**Dedup:** cosine similarity ≥ 0.93 threshold suppresses near-duplicate writes.

**Pruning gate:** `quality < 0.55 AND use_count == 0`

---

## Reflection Triage

| Condition | Level |
|-----------|-------|
| lookup / factual → terse | none |
| explain, compare, plan | none |
| build/debug + code agent + conf ≥ 0.55 | light |
| build/debug + code agent + conf < 0.55 | full |
| debug (any code agent) | full |
| research | light |
| compound task | full |
| confidence < 0.40 | full |
| instability gate | light |

Light = grounded eval only (~0 extra LLM calls). Full = grounded eval + LLM critique + refine (up to 3 iterations, ~30–55s).

---

## Dual-Trajectory Evaluation (GRAM-light)

For `python_dev` and `dotnet_dev` on **code/debug tasks only:**
1. **Candidate A** — full agent call (memory + tools + LLM)
2. **Candidate B** — lightweight LLM with CoT-augmented system prompt (no memory/tools)
3. **Critic** — single short LLM call picks winner

Zero overhead for non-code tasks.

---

## Cognitive OS Layer

Persistent session substrate that runs above the agent router:

| Component | Purpose |
|-----------|---------|
| `EventBus` | Append-only event log — every query, routing decision, plan step, reflection, error |
| `WorldModel` | Tracks `active_goals`, `completed_tasks`, `domain_coverage`, `risk_factors` across sessions |
| `MetricsEngine` | Computes UCI score from four dimensions continuously |
| `CognitiveState` | Per-session coordinator wiring EventBus + WorldModel + MetricsEngine |
| `SkillGraph` | 21-node skill graph with fuzzy keyword matching and confidence-weighted disambiguation |
| `ContextStratifier` | Detects contaminated or low-signal context before it enters the agent prompt |

**UCI health score:**
```
h_UCI = 0.30 × Reliability + 0.30 × Intelligence + 0.25 × Adaptation + 0.15 × Productivity
```
- **Reliability** — error rate, retries, step failure frequency
- **Intelligence** — routing confidence, reflection depth, memory hit rate
- **Adaptation** — weight drift, memory quality trend, agent diversity
- **Productivity** — goal completion rate, avg response latency (target ≤ 8s)

Current: **h_UCI ≈ 80.8**

---

## Auth and Monetization

- **API key auth** — `X-API-Key` header, SHA-256 hashed keys in `api_keys.db`
- Tiers and daily limits: `free=100` · `developer=5000` · `team=50000` · `enterprise=unlimited`
- `REQUIRE_AUTH=0` dev default; `ENV=production + REQUIRE_AUTH=0` raises `RuntimeError`
- **Stripe Checkout** — Developer tier $39/month; webhook provisions key + SendGrid email
- **`/register/free`** — self-serve free tier registration

---

## API Surface

100+ endpoints across route groups:

| Group | Key endpoints |
|-------|--------------|
| `/ask`, `/ask/stream` | Query execution, streaming SSE, document context |
| `/documents/*` | File upload, list, delete (RAG context files) |
| `/memory/*` | Stats, records, pruning, consolidation, contradiction resolve |
| `/analysis/*` | Memory backend, skill graph, UCI components, failures, specialization |
| `/cos/*` | Event bus, world model, metrics engine, plan graph |
| `/verify/*` | Step verifier log, stats |
| `/admin/*` | API key management, usage stats |
| `/feedback` | Rating submission and retrieval |

---

## UI — Tab Inventory

| Tab | Key content |
|-----|-------------|
| Chat | Query interface, streaming response, agent badge, file attachments |
| UCI Dashboard | Live h_UCI gauge, 4-dimension breakdown, routing confidence |
| Project State | World model: goals, completed tasks, domain coverage, risk factors |
| Event Log | Append-only event stream with category + text search |
| Plan Graph | SVG DAG of last executed plan — node status, uncertainty bars, elapsed_ms |
| Risk Observatory | Reflect distribution sparkline, risk score trend |
| Memory Browser | 500-record browser, type/agent/quality filters, FAISS backend badge |
| Decision Replay | Session history with ↻ Replay button; original vs replay side-by-side |
| Cognitive OS | CognitiveState inspector |
| Skills | Skill graph nodes, agent mapping, keyword coverage |
| Data | Memory backend panel, benchmark runner, promote button |
| Session | Agent overrides, forced-agent mode |
| Settings | Theme, keyboard shortcuts, REQUIRE_AUTH status |
| Version History | BUILD_PHASES timeline |
| Progress | post-1.0 polish items, feedback loop analytics |

---

## Core Files

| File | Purpose |
|------|---------|
| `query_normalizer.py` | QuerySignal — pure function, <1ms, no LLM |
| `core_brain.py` | Routing authority — intent, complexity, agent strategy, regret |
| `coordinator.py` | LangGraph orchestration — signal → brain → dual-traj → agent → learning |
| `deep_pipeline.py` | Compound task fan-out: decompose → multi-agent → synthesize |
| `dual_trajectory.py` | Code/debug: generate A+B, critic picks better response |
| `learning.py` | **Single learning kernel** — only weight mutation path |
| `decision_weights.py` | Weight store, calibration, `drift_status()` |
| `reflection.py` | Grounded eval + LLM critique + refinement loop |
| `memory_core/db.py` | Semantic memory — type weights, quality, pruning, retrieval audit |
| `memory_core/backend.py` | Abstract backend interface + SQLite/FAISS adapters |
| `routes/documents.py` | RAG file upload/list/delete |
| `routes/core.py` | `/ask`, `/ask/stream` with document context injection |
| `core/api_keys.py` | Key generation, verification, usage tracking, tier limits |
| `cognition/skill_graph.py` | 21-node skill graph with disambiguation |
| `cognition/cognitive_state.py` | COS session substrate |
| `cognition/world_model.py` | Persistent project context |
| `learned_router.py` | sklearn LogisticRegression trained on 312 traces |
| `coherence.py` | C(t) computation, time-series, reflection gain |

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Build phases completed | 37 |
| Routing accuracy | 97% (live) · 99% (ablation) |
| Skill graph nodes | 21 |
| FAISS vectors | 628+ |
| FAISS search P50 | 0.38ms |
| LRU cache speedup | 52× |
| UCI score | ~80.8 |
| API endpoints | 100+ (128 routes) |
| Test suite | 702 passing |
| Avg response latency | ~4–8s (phi4-mini on RTX 2050) |
| Full reflection rate | ~15% (down from 58% pre-triage) |

---

## Workflow

```bash
Tab 1: ai-ui      → React on localhost:3000
Tab 2: ai-start   → Ollama + Backend on port 8000
Stop:  ai-stop
Logs:  ai-logs
```

---

*See `docs/GUIDE.md` for usage patterns. See `docs/ROADMAP.md` for what's next.*
