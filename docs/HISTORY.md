# Amagra — Build History

Phase-by-phase record of what was built and why. Four eras: 37 build phases, then the internal releases that led to the v1.0.0 public debut. Preserved as the in-app build log.

---

## Era 1: Foundation (Phase 1–10)

**Period:** Early 2026  
**Goal:** Get the loop — user asks → agent answers → system learns — running end-to-end.  
**Stack:** LangGraph · Llama3 8B · Ubuntu · CPU-only

### Phase 1–7 — Core Bootstrap ✅

- First working agent (`knowledge_learning`) answering questions
- LangGraph state graph: message → agent → response cycle
- SQLite memory database: store and retrieve past answers by embedding similarity
- `nomic-embed-text` for semantic search
- FastAPI backend exposing `/ask`, `/decisions`, `/health`
- React frontend — first dashboard, chat tab
- Basic keyword routing: `router.py` picks agent by domain keywords
- `user_profile.py` — identity, personality, teaching style injected into every agent

### Phase 8 — Personalization + Cleanup ✅

- `user_profile.py` complete — all 6 agents inject profile via `_effective_prompt()`
- Project cleanup: `scripts/`, `archive/`, `docs/` organized
- `.gitignore`, `requirements.txt` created

### Phase 9 — Performance + Machine Upgrade ✅

**Problem:** Llama3 8B was too slow on CPU (~2 min per response).

- RTX 2050 GPU activated with persistent CUDA config
- Switched to **phi4-mini (3.8B)** — fits in 4GB VRAM, ~3× faster
- `OLLAMA_MAX_LOADED_MODELS=1` to prevent VRAM conflicts
- Shell aliases: `ai-start`, `ai-ui`, `ai-stop`, `ai-logs`
- Python venv: `~/.venvs/langgraph-env/`

### Phase 10 — Reflection + Core Brain ✅

**Problem:** Agents answered and moved on. No quality check, no self-correction.

**Reflection Loop (`reflection.py`):**
- `grounded_evaluate()` — code execution + heuristics
- LLM critique: "Is this response complete and correct?"
- LLM refinement: rewrite based on critique (up to 3 iterations)

**Core Brain (`core_brain.py`):**
- `BrainDecision` dataclass: intent, action, complexity, agent_strategy, reflect, confidence, regret
- Fast path: keyword scoring, <1ms, no LLM for clear queries
- Slow path: LLM fallback for ambiguous queries

**Snapshot at End of Era 1:**

| Metric | Value |
|--------|-------|
| Memories | ~61 |
| Brain decisions logged | ~36 |
| Routing conflicts | ~2 (5.6%) |
| GPU | RTX 2050, 4GB VRAM |
| LLM | phi4-mini 3.8B |
| Routing | Keyword scorer |

---

## Era 2: Learning + Signal Routing (Phase 11–20)

**Period:** May–June 2026  
**Goal:** Make the system learn from experience. Reach 97% routing accuracy.

### Phase 11 — Adaptive Decision Tuning ✅

- `decision_weights.py` — SQLite-backed per-agent weights in `[0.1, 3.0]`, default 1.0
- Calibration EMA of (confidence, reflection_score) divergence
- `to_confidence()` — applies calibration correction when sample_count ≥ 5

### Phase 12 — Regret + Stable Learning ✅

- `BrainDecision.regret` — `max(alt_confidence) − chosen_confidence`
- `drift_status()` — three health detectors: calibration_drift · regret_explosion · weight_volatility
- Hard freeze at instability > 0.80, half-speed at > 0.60

### Phase 13 — Single Learning Kernel ✅

- `apply_learning_update()` in `learning.py` — **only function that modifies agent weights**
- Full pipeline per decision: calibration EMA → signal L → instability I → adaptive alpha → bounded delta ±0.02 → non-chosen agent decay

### Phase 14 — Control Plane UI ✅

- `DecisionTimeline.jsx` — decision log with filter/search
- `AgentHealthPanel` — weight bar, confidence, cal error, avg regret, trend arrows
- `DriftMonitorPanel` — instability bar, STABLE / DEGRADING / UNSTABLE badge
- `BrainInspector` — full decision breakdown with Replay button
- Endpoints: `GET /decisions`, `GET /replay/{id}`, `GET /learning/drift`

### Phase 15 — Documentation ✅

- `Summarizer.MD` — system constitution
- `docs/tracker.md`, `ModelOverview.md`, `dashboard-guide.md`, `known-issues.md`

### Phase 16 — Signal-First Routing ✅

**Problem:** Keyword router was a flat heuristic. Routing accuracy ~70%.

**QuerySignal Architecture:**
- `query_normalizer.py` — `QuerySignal(domain, domain_conf, answer_shape, verbosity, action)`
- `detect_domain()` with word-boundary guard for ≤4-char keywords (fixes "nat" in "paginated")
- `detect_answer_shape()` — factual · code · debug · procedural · comparison · explanation
- `detect_verbosity()` — terse (≤6 tokens) · normal · detailed (≥25 tokens)
- `DOMAIN_TO_AGENT` lookup — pure table, no heuristics

**Routing Accuracy Progression:**

| Eval | Prompts | Accuracy |
|------|---------|----------|
| Baseline (action-first) | 50 | 70% |
| Signal-first | 50 | 92% |
| Signal-first + all fixes | 100 | **97%** |

### Phase 17 — UI Decomposition + Stress Testing ✅

- `App.js` 534 → 120 lines (shell only)
- Extracted: `ChatTab.jsx`, `OverviewTab.jsx`, `TracesTab.jsx`, `LogTab.jsx`
- `constants.js` — AGENTS (7) · BUILD_PHASES (11) · PROGRESS_STEPS

Bugs fixed: MindMap force-agent regression · CORS block on 500 errors · raw JSON error messages

### Phase 18 — Memory Pruning + Dual-Trajectory + Ablation ✅

**Memory Quality Pruning:**
- `memory_stats()`, `prune(dry_run)` — removes `quality < 0.55 AND use_count = 0`
- API: `GET /memory/stats` · `POST /memory/prune`

**Dual-Trajectory Evaluation (GRAM-light):**
- Candidate A: full agent call
- Candidate B: lightweight LLM with CoT system prompt
- Critic: single short LLM call picks winner
- Gate: `is_code_task()` — zero overhead for non-code

**Ablation Eval:**
- `ablation_eval.py` — pure QuerySignal routing, no LLM, runs in <2s
- **99/100 (99%)** signal-only accuracy — outperforms full pipeline

### Phase 19 — Reflection Triage ✅

**Problem:** Reflection fired 58% of the time, costing ~25–30s per cycle.

- `_reflect_level()` returns `"none" | "light" | "full"`
- Light reflection = grounded eval only; Full = grounded eval + LLM critique + rewrite
- Full-reflection rate: 58% → ~15–20%

### Phase 20 — User Feedback ✅

- `POST /feedback` — stores rating, fires `apply_learning_update(performance=0.90/0.25)`
- `ChatTab.jsx` — 👍/👎 per agent message; selected button highlights

**Snapshot at End of Era 2:**

| Metric | Value |
|--------|-------|
| Memories | 672 (21 prunable) |
| Brain decisions logged | 283 |
| Routing accuracy | 97% full · 99% signal-only |
| Reflection rate | 58% → ~15–20% |
| Learning | Stable single-mutation-path kernel |

---

## Era 3: Causal Intelligence + Cognitive OS (Phase 21–37)

**Period:** June 2026 — current  
**Goal:** Move from reactive learning to causal understanding. Build the Cognitive OS layer.

### Phase 21 — Episodic Memory ✅

- `_write_episodic()` — writes `mem_type="episodic"` after every response with outcome, performance, regret
- Fast path uses past episodes: successful episode → +0.04 confidence boost; failed → escalates reflect level

### Phase 22 — Failure Miner ✅

- `failure_miner.py` — clusters high-regret decisions, conflict rates, regret by action type
- `GET /analysis/failures` endpoint
- Finding: terse conflict rate 86.7% (keyword router almost never routes to terse)
- Fix applied: `hybrid_router()` added `answer_shape == "factual"` → terse path

### Phase 23 — Contradiction Detection ✅

- `_check_contradiction()` — zero LLM, pure heuristic; cosine ≥ 0.78 + 22 negation patterns + keyword overlap check
- If detected → escalates `reflect_level` to "full"

### Phase 24 — Outcome-Weighted Memory ✅

- `memory_db.update_quality(ids, delta)` — log-odds quality delta
- 👍 rating → +0.03 quality to accessed memories; 👎 → −0.05

### Phase 25 — Decision Trace Dataset ✅

- `trace_builder.py` — 312 traces: 21 real sessions + 291 eval decisions
- `label_trustworthy` field; Level 3 (similarity-based) joins flagged
- `agent_specialization.py` — per-agent verdicts (core/narrow/struggling/redundant)
- `memory_backend.py` — abstract `MemoryBackend` + `SQLiteBackend` adapter
- `counterfactual.py` — simulate alternative routing for any past decision

### Phase 26 — Decision Graph ✅

The core research artifact. Flat trace records → directed causal graph.

- 922 nodes · 3438 edges · avg degree 3.73
- Node types: query(312) · agent(6) · memory(111) · reflection(181) · outcome(312)
- Edge types: SELECTED · REJECTED · RETRIEVED · INFLUENCED · PRODUCED · REFLECTED
- `causal_path(graph, decision_id)` — full trace with causal flags
- `DataTab.jsx` — dataset coverage, specialization, counterfactual panel, causal path explorer

### Phase 27 — Tiny Learned Router ✅

- `learned_router.py` — LogisticRegression on 23 features
- train_accuracy=90.1% · cv_accuracy=86.9% ± 0.096 (5-fold)
- Ensemble integration: agree with signal router → +0.05 confidence; disagree + `lr_conf > 0.85` → LR wins

Also: Code quality cleanup — `api.py` inline sqlite imports removed, phantom agents removed from `/agents` endpoint, `OLLAMA_MODEL` corrected.

### Phase 28 — Deep Pipeline v1 ✅

- `deep_pipeline.py` — compound task execution: decompose → fan_out → synthesize
- Coordinator routes to pipeline when `complexity == "compound"` AND ≥ 2 real-domain agents
- UI keyboard shortcuts: `Ctrl+1–5`, `Ctrl+K`, `Ctrl+B`, `Ctrl+,`, `Ctrl+/`, `Escape`
- `SettingsModal` added with live system info

### Phase 29 — C1-Smooth Learning Primitives ✅

Three hard discontinuities eliminated:

- **Domain confidence:** `min(1, hits×0.35)` → `1 − exp(−0.40×hits)` — no hard ceiling, full float precision
- **Adaptive alpha:** step function → smooth sigmoid: `alpha = BASE_ALPHA / (1 + exp(8 × (I − 0.5)))`
- **Quality update:** linear clip → log-odds Bayesian: `l_new = l + 4.0 × delta; q_new = sigmoid(l_new)`
- `tests/test_learning_invariants.py` — 14 invariant tests, all pass, no LLM/DB required

Action pattern coverage extended: `action=unknown` rate → 0%.

### Phase 30 — Docs/UI Architecture Alignment ✅

- `AGENTS` unified in `constants.js` — removed from 4 duplicate locations
- `GET /docs` + `GET /docs/{name}` — UI can fetch authoritative markdown at runtime

### Phase 31 — Feedback Loop UI ✅

- `ProgressTab.jsx` — Feedback Loop panel with per-agent 👍/👎 bar chart
- Confirmed: feedback buttons POST correctly and trigger `apply_learning_update()` immediately

### Phase 32 — UI Polish + Revenue Strategy ✅

- Menu hover CSS `!important` bug fixed (F-18)
- Sidebar nav upgrade: font 12/400 → 13/600; layout separator removed
- Tab layout consistency: removed root-level `maxWidth + margin: 0 auto` from 16 tabs; `App.js` is single layout authority (F-19)
- `docs/ROADMAP-REVENUE.md` created — 5-phase commercial roadmap

### Phase 33 — Contradiction Resolution ✅

- `memory_db.auto_resolve_conflicts(threshold=0.90)` — always keeps newer memory (higher AUTOINCREMENT id)
- `GET /memory/auto-resolve` (dry-run preview) · `POST /memory/auto-resolve` (execute)
- `ContradictionsPanel` in CognitiveOSTab with diff view and Auto-Resolve button

### Phase 34 — Prompt Quality IDE ✅

5-panel architecture: Prompt Health · Execution Forecast · Missing Context · Suggested Agents · Prompt Upgrade.  
`detectDomain(text)` — pure JS, no API call. `generateRepair` — deterministic heuristic auto-fix, instant.

### Phase 35 — FAISS Backend + Cognitive OS ✅

- `FAISSBackend` active; `promote_if_needed()` hook at startup
- FAISS search P50 = **0.38ms** at 628 entries (target 5ms, 13× margin)
- `event_bus`, `world_model`, `metrics_engine`, `cognitive_state` + `/cos/*` API endpoints
- `context_stratifier` (contamination isolation), `skill_graph` (18 skills, disambiguation)

### Phase 36 — Open Source Launch + Auth Foundation ✅

- `core/api_keys.py` — SHA-256 key hashing, tier-based daily limits (free/developer/team/enterprise)
- `api.py` — `_auth()` middleware, `REQUIRE_AUTH` env var, `X-API-Key` header
- `Dockerfile` + `docker-compose.yml` — Ollama (GPU passthrough) + API + UI, persistent volumes
- `README.md` — quick start, architecture, auth guide, paper pointer

### Phase 37 — Cognitive Intelligence Layer ✅

- Hierarchical UCI: `h_UCI = 0.30×Reliability + 0.30×Intelligence + 0.25×Adaptation + 0.15×Productivity`
- Current h_UCI: ~80.8 (up from 74.9 after productivity metric fix)
- World-model planner, rate-limit headers (`X-RateLimit-*`), `/register/free` self-serve endpoint
- 21 skills in skill graph (up from 18)

## Era 4: Productization → v1.0.0 (v0.9.1 → first public release)

Post-phase work tracked by semver release rather than phase number. See `docs/ROADMAP.md` for the full per-release changelog.

### v0.9.1–v0.9.4 — Hardening, async & brand ✅

- Auth deny-by-default (`_PUBLIC_PATHS` allowlist), CORS lock, sliding-window rate limits, CI (ruff + pytest + Docker)
- Async `/ask` via executor, SQLite WAL mode, `ContextVar` tenant scoping
- 29-tab sidebar consolidated to 4 surfaces (Chat · Memory · Inspect · Settings)
- Multi-provider `AskRequest.provider` field + `AnthropicProvider`; inline "◈ Remembered" memory surfacing; Amagra brand + luxury UI

### v0.10.1 — RAG File Context ✅

- `POST /documents/upload` — PDF / Markdown / code / text up to 10 MB
- Inline paragraph-boundary chunker (800c / 100c overlap, no langchain)
- `context_files` on `AskRequest`; top-k chunks injected into `/ask` and `/ask/stream`
- File-chip UI with upload/ready/error states

### v1.0.0 — First Public Release ✅

The public debut. Signal-first routing, 10 domain agents, persistent FAISS memory, the Cognitive OS layer, RAG file context, auth + rate limiting, and the Gilded Calm UI — everything from the v0.1 → v0.10 internal builds, released publicly for the first time. See `docs/ROADMAP.md` for the full 1.0.0 surface.

### v1.0.1 — Lean Runtime & Onboarding ✅

Post-debut hardening — the deferred pre-launch engineering, none of which blocked 1.0.0.

- **Lean runtime core** (`core/`) — neutral `Context`/`Result` spine, onion middleware, lazy registry, append-only run log; now sits beneath the router
- **Delta-algebra routing seam** — frozen dispatch reducer (`infrastructure/dispatch.py`), router score/decide split
- **DB path registry** (`infrastructure/db.py`) — centralizes every SQLite path; the consolidation seam toward a single `amagra.db`
- **First-run onboarding** — Ollama + model-pull detection, guided first prompt; UI migrated CRA → **Vite**
- **Luxe-card UI** — the `landing.html` card system ported to the dashboard; README badge row + Star History chart
- Test suite **544 → 624** passing

Residual v1.0.1 item: the public launch (Show HN / r/LocalLLaMA / self-host catalogs) — a marketing action, not code.

### v1.1.1 — Tools in the Default Path & Retrieval Polish ✅

**Period:** 2026-06-15

Closes the loop on v1.1: the in-agent tool loop, shipped as a dedicated endpoint
in v1.1.0, is now wired into the **default** specialist-agent reasoning path, plus
a wave of retrieval, routing, and multilingual fixes from the issue queue.

- **Tool loop in the default agent path** (#8, #5) — `tools/agent_runtime.py`
  bridges the bounded loop and the jailed workspace tool into all 10 specialist
  agents via `respond_with_optional_tools()`, a drop-in for `llm.invoke`. Gated
  behind `AMAGRA_AGENT_TOOLS=1` (off by default — phi4-mini's fenced-tool-JSON
  reliability is still unproven); any failure falls back to a plain invoke, so
  behaviour is unchanged until the flag is set. `run_tool_loop` gained a
  `system_preamble` so the specialist persona leads, then the tool protocol.
- **Domain-affinity retrieval penalty** (#14) — off-domain memories are
  down-weighted (not excluded) so the requesting agent's own memories win close
  calls. Unified the per-backend ranking tail into one `rank_select()` shared by
  SQLite/FAISS/pgvector — which also repaired the episodic cap (#13) being a
  no-op on the default FAISS backend.
- **Learned-router auto-retrain** (#15) — `orchestration/auto_retrain.py` rebuilds
  the trace dataset and retrains the router every `LEARNED_ROUTER_RETRAIN_EVERY`
  real sessions (default 50), in a single-flight background thread. State on
  `GET /analysis/learned_router`.
- **Multilingual profile-leak fix** (#6) — `core/language.py` flags non-English
  input (strong/weak diacritic split + script detection); the user-profile block
  is then dropped and a "reply in the user's language" directive injected, across
  all 10 agents and the Anthropic `/ask` path.
- **Routing & detection** — min-keyword threshold so a lone keyword in a short
  query no longer over-routes (#10); a compound-query detection benchmark
  (`evaluation/compound_eval.py`) that found the false-positive rate is already
  0.00 (#11).
- Test suite **719 → 766**.

### v1.1.0 — Tool-Using Agents ✅

Completes the v1.1 "tool-using agents" milestone. The two pieces held back from
v1.0.4 — live web search and the in-agent tool loop — landed, alongside a
beginner-friendly UI and a routing-accuracy guard.

- **Live web search** — `tools/web.py` provider abstraction: default **SearXNG**
  (no key, set `SEARXNG_URL` — fits the self-hosted posture), opt-in `brave` /
  `tavily` via keys. `GET /search/web` (503 until configured) + `GET /search/status`,
  uniform `{title, url, snippet}` results.
- **In-agent tool loop** — `tools/tool_loop.py`, a provider-agnostic loop (LLM
  injected): the model emits fenced JSON `{"tool","args"}` → execute → observe,
  bounded N rounds, emitting `tool.call` events. Wired to file / sandbox / web via
  `tools/catalog.py`. `GET /tools/list` + `POST /tools/run`. Exposed as a dedicated
  endpoint for now — auto-invoking it inside the default specialist-agent flow waits
  on phi4-mini's tool-JSON reliability.
- **Simple / Advanced UI mode** — Simple trims the chrome to the essentials a
  newcomer needs (Chat, Library, Guide) and hides the Memory/Inspect surfaces, the
  technical menus, and advanced settings sub-tabs; Advanced reveals everything. New
  users start simple; existing users keep the full UI. Persists in `localStorage`,
  toggleable from the menu-bar pill, the Settings modal, and the onboarding chooser.
- **Onboarding** — reworked to lead with plain language and privacy ("runs on your
  own computer") instead of Ollama/model jargon.
- **Routing guard** — build over-classification guard, profile-leak framing fix,
  embedding warm-up.
- Test suite **690 → 719**; **132 routes**.

### v1.0.4 — Tool-Using Foundations ✅

The first wave of v1.1 "tool-using agents" capabilities, delivered on the
v1.0.x line. (Live web search + the in-agent tool loop remain for v1.1.0.)

- **Thread management** — `PATCH /threads/{id}` (rename), `POST /threads/{id}/fork`,
  `POST /threads/{id}/archive`, `POST /threads/{id}/truncate`; `GET /threads`
  gained `include_archived`.
- **Jailed file/folder tool** — `tools/workspace.py` read/list/search confined to
  `$AMAGRA_WORKSPACE` via `(root/p).resolve().is_relative_to(root)` (defeats
  traversal, absolute-path injection, symlink escape). `GET /workspace/*`.
- **Sandboxed code execution** — `tools/sandbox.py` runs `python3 -I -S` under
  `setrlimit` (CPU/memory/output), scrubbed env, throwaway cwd, process-group
  timeout kill. `POST /sandbox/run`, opt-in behind `AMAGRA_SANDBOX=1`. Network is
  not isolated (documented).
- **Chat affordances** — stop (existing), regenerate, and edit-and-resend in the
  composer, backed by thread truncation.
- **UI fix** — resolved a temporal-dead-zone ReferenceError that blanked the
  dashboard; added a top-level `ErrorBoundary`.
- Test suite **645 → 690**.

### v1.0.3 — Single-File DB Consolidation ✅

Completes the DB-consolidation seam opened in v1.0.1 so `AMAGRA_DB` actually
ships a single file.

- **Registry completion** — `registrations` and `telemetry` joined the
  `infrastructure/db.py` registry; `routes/register.py` and `routes/core.py`
  now resolve their paths through it (were hardcoded, so single-file mode
  silently skipped them). `runtime_slice.db` left out by design — it is a demo
  script's scratch DB whose `runs` table collides with the real one.
- **WAL setup from the registry** — `api.py` startup now derives the WAL list
  from `infrastructure.db.distinct_paths()` instead of a hand-maintained list,
  so it honours single-file mode and never drifts from the real layout.
- **One-shot migration** — `scripts/migrate_to_single_db.py` copies every
  separate store into one `amagra.db`, preserving `rowid` for all tables
  (critical: FAISS `IndexIDMap` is keyed on `memories.id`) and the FAISS
  sidecar. Dry-run by default; `--archive` renames the old files to
  `*.pre-consolidation` so they can't diverge; refuses to clobber a same-named
  table with a different schema.
- **Cutover wiring** (closes #3) — `start-agents.sh` and `docker-compose.yml`
  pass `AMAGRA_DB` through (with a `./data` volume for the single file), so
  single-file mode is a one-env-var opt-in; README documents the migrate→flip
  flow.
- **Memory portability** — lossless JSON export/import (`GET /memory/export.json`,
  `POST /memory/import`): embeddings are base64-encoded so a re-import reuses the
  stored vectors with no model call and dedups via the near-duplicate gate;
  Markdown export (`GET /memory/export.md`) grouped by agent. First v1.1
  "tool-using agents" item, delivered early.
- Suite **624 → 645**.

### v1.0.2 — Dashboard & Community Polish ✅

- **Luxe-card system** extended across the whole dashboard (10 tabs: Cognitive Map, Cognitive OS, Event Log, Home, Memory Browser, Plan Graph, Policy, Risk Observatory, Skills, Version History) — inline cards → `className="lux-card"`, rounded badges, shared `PageHeader`/`RefreshBtn`
- Fix: `CognitiveMapTab`'s `T as C` alias left `card`/`blue`/`green` undefined (silent muted fallback) — explicit local palette
- **Community profile** — `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`
- **Gilded Calm social-preview card** (1280×640) for GitHub link sharing

**Live Snapshot (2026-06-15):**

| Metric | Value |
|--------|-------|
| Version | v1.1.1 (tools in default path) |
| Routing accuracy | 97% full · 99% signal-only |
| Specialist agents | 10 (registry-canonical) |
| FAISS vectors | 628+ at 0.38ms P50 |
| API endpoints | 100+ (132 routes) |
| Build phases complete | 37 (+ v0.9 → v1.1.1 releases) |
| UCI score | ~80.8 |
| Auth | API key auth (REQUIRE_AUTH=0 dev, 1 prod) |
| Docker | Dockerfile + docker-compose.yml with GPU passthrough |
| Test suite | 766 passing |

---

*Update with a new section when a phase or release completes.*
