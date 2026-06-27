# Amagra — Roadmap

> **North star:** the only AI runtime where the system remembers everything, verifies itself, and can prove why it did what it did — on hardware you control. Memory, verification, and provenance are the product; everything else is an adapter.

---

## Near-Term Execution Plan *(as of 2026-06-26)*

The milestone sections below are capability-ordered; this is the **dated** view — what to do next, soonest first. The single highest-ROI item still pending is the public launch (#9).

| When | Focus | Concrete steps | Tracking |
|------|-------|----------------|----------|
| **Tomorrow / this weekend** (Jun 27–28) | Land today's follow-ups + launch assets | Wire the coordinator onto `get_router()` (Router seam Phase 2 — the seam shipped today in #62 but nothing calls it yet); delete the stale `scripts/memory_context.py` duplicate; record the 30-second routing GIF + comparison table for the launch post | #64, #65, #19 |
| **Next week** (Jun 29 – Jul 3) | **Public launch** | Show HN ("self-hosted AI that shows you *why* it answered"), r/LocalLLaMA, Docker Hub image, Homebrew formula; onboarding finish — 5-min clone→first-answer, startup diagnostics, auto thread titles | **#9** |
| **Following week** (Jul 6–10) | Adoption leverage (v1.5.3) | OpenAI-compatible `/v1` drop-in (`OPENAI_BASE_URL=…/v1`); harden non-English detection against a labeled set; transparency for the opaque components | #18, #47, #48 |
| **Two weeks out** (Jul 13–17) | Workspace groundwork | Per-workspace memory **namespace seam** (extend the `ContextVar[int]` tenant scope, no migration); decision-replay polish (timeline + permalink); Monaco code pane (last open v1.4 item — now part of the Prompt-as-Artifact foundation) | v1.5.3 |
| **Month+** (late Jul → Aug) | v1.6 Workspaces & RBAC | Workspaces + RBAC + custom agent builder; **Prompt-as-Artifact foundation** ([`PROMPT_ARTIFACT_CONTRACT.md`](docs/PROMPT_ARTIFACT_CONTRACT.md) — Track D); Deep Pipeline v2 (LLM sub-question split); persist Consensus runs as durable decisions | #16, v1.6 |

> **Rule of thumb:** nothing after the launch row starts until launch ships — distribution is the bottleneck, not features.

---

## v1.0.0 — First Public Release

The public debut. Everything below shipped in 1.0.0 — the development phases that led here (v0.1 → v0.10 internal builds) are preserved as the in-app build log, but **1.0.0 is the first version released to the public.**

### Runtime & routing

| Item | Detail |
|------|--------|
| Signal-first routing | `QuerySignal` classifies most queries in ~1 ms without an LLM call; escalates to `CoreBrain` reasoning only when genuinely ambiguous. |
| 10 domain agents | Python, .NET, Web, DevOps, Data, AI/ML, IT Networking, Writer, Knowledge, Terse — each domain-tuned with per-agent memory. |
| Skill graph | 21-node phrase-weighted disambiguation layer resolves edge-case routing overlaps. |
| Critic gate + step verifier | Per-response scoring (≥ 0.70 or regenerate) and per-step pass/fail feeding the coordinator. |

### Memory & observability

| Item | Detail |
|------|--------|
| Persistent semantic memory | SQLite → auto-promote to FAISS at 800 entries → cosine search → outcome-weighted scoring → 52× LRU cache (< 1 ms warm). |
| Memory surfaced inline | Top 2 memories auto-show as "◈ Remembered · [snippet]" below each response. |
| RAG file context | `POST /documents/upload` (PDF, Markdown, code, text up to 10 MB); chunks embedded into the memory layer; top-k injected into `/ask` and `/ask/stream`. |
| Cognitive OS | `event_bus`, `world_model`, `cognitive_state`, `metrics_engine`, `skill_graph`, `suggestion_engine` — all browsable in real time. |
| Conversation threading | Each thread carries the last 4 turns; rolling context window; routing telemetry via `GET /telemetry/routing`. |

### Platform & hardening

| Item | Detail |
|------|--------|
| Auth deny-by-default | `_PUBLIC_PATHS` allowlist gates all non-public routes when `REQUIRE_AUTH=1`. `ADMIN_TOKEN` required for admin surface. |
| CORS + rate limiting | `ALLOWED_ORIGINS` (no wildcard); sliding-window per-key limits with `X-RateLimit-*` headers. |
| Async + WAL | `/ask` runs in an executor; `PRAGMA journal_mode=WAL` on all SQLite DBs; tenant scoping via `ContextVar[int]`. |
| Streaming | `POST /ask/stream` SSE; tokens render as they arrive (live from Claude when `ANTHROPIC_API_KEY` is set). |
| Multi-provider path | `AskRequest.provider`; `AnthropicProvider.generate()` alongside Ollama; `AskResponse.model_used`. |
| Commercialization | API-key auth, free tier (`POST /register/free`), Stripe Checkout + webhook key provisioning, SendGrid delivery. |
| Brand & UI | "Gilded Calm" warm-white + gold (`#C48808`) design tokens in `theme.js`, shared with `landing.html`; 5-surface nav (Chat · Library · Memory · Inspect · Settings) fronting the observability views; RoutingStrip animation; JetBrains Mono. |
| CI/CD | GitHub Actions: ruff lint + pytest + Docker build on push and PR. |

---

## Post-1.0 Roadmap

### v1.0.1 — Launch Polish & Hardening *(shipped — launch pending)*

Deferred pre-launch engineering, now landed post-debut. The one open item is the public launch itself.

| Item | Status | Impact | Difficulty | ROI |
|------|--------|--------|-----------|-----|
| Lean runtime core — `Context`/`Result` spine, onion middleware, lazy registry, run log | ✅ shipped | 8 | 6 | ★★★★ |
| Delta-algebra routing seam — frozen dispatch reducer, router score/decide split | ✅ shipped | 7 | 5 | ★★★★ |
| In-product onboarding: first-run flow, model pull detection | ✅ shipped | 8 | 4 | ★★★★ |
| Vite migration — retire CRA (dead/unmaintained) | ✅ shipped | 6 | 3 | ★★★★ |
| DB path registry — `infrastructure/db.py` (seam toward single `amagra.db`) | ✅ shipped | 6 | 6 | ★★★ |
| Tests: routes/ + core/ + dispatch + runtime (544 → 624 passing) | ✅ shipped | 8 | 5 | ★★★★ |
| Launch: Show HN + r/LocalLLaMA + Docker Hub + Homebrew | ⏳ pending | 9 | 3 | ★★★★★ |

**Onboarding detail:**
- On first launch: detect whether Ollama is running; if not, one-step command with copy button
- Detect whether required models are pulled; show model pull progress UI in-app
- Pre-fill first prompt with a guided question
- Thread titles: auto-generate from first exchange instead of "Untitled"

**Launch prep:**
- 30-second GIF of routing animation for README and Show HN post
- Comparison table vs Open WebUI / LibreChat / AnythingLLM
- Docker Hub official-style image with reproducible build
- Homebrew formula, good-first-issue labels

---

### v1.1 — Tool-Using Agents *(✅ shipped v1.1.1, 2026-06-15)*

Agents that do things, not just say things. Closes the gap vs Continue/Cursor/Claude Code. All capabilities shipped: memory portability, thread management, jailed file tool, sandboxed execution, live web search, and a provider-agnostic in-agent tool loop (`tools/tool_loop.py` — model emits fenced JSON `{tool,args}` → execute → observe, bounded rounds; `GET /tools/list`, `POST /tools/run`). **v1.1.1** wired that loop into the default specialist-agent path via `tools/agent_runtime.py` (`respond_with_optional_tools`), config-gated behind `AMAGRA_AGENT_TOOLS=1` until phi4-mini's tool-JSON reliability is validated — off by default, falls back to a plain invoke.

| Item | Status | Impact | Difficulty | ROI |
|------|--------|--------|-----------|-----|
| Sandboxed code execution | ✅ shipped | 10 | 8 | ★★★★ |
| Live web search (Brave/SearXNG/Tavily) | ✅ shipped | 9 | 4 | ★★★★★ |
| Jailed file/folder tool (`Path.resolve().is_relative_to(root)`) | ✅ shipped | 8 | 5 | ★★★★ |
| Stop / regenerate / edit-message affordances | ✅ shipped | 7 | 3 | ★★★★★ |
| Thread management: rename, fork, archive | ✅ shipped | 6 | 2 | ★★★★ |
| Memory import/export (JSON/Markdown) | ✅ shipped | 8 | 3 | ★★★★★ |

**Memory import/export (shipped):** `GET /memory/export.json` (lossless — base64 float32 embeddings, re-imports with no model call), `GET /memory/export.md` (human-readable, grouped by agent), `POST /memory/import` (dedups via the near-duplicate gate, then rebuilds the FAISS index). CSV export predates this.

**Thread management (shipped):** `PATCH /threads/{id}` (rename), `POST /threads/{id}/fork?upto=N` (copy a thread + its turns into a new one, optionally truncated), `POST /threads/{id}/archive?archived=bool` (archive/unarchive). `GET /threads` gained `include_archived` and hides archived threads by default. Backed by an idempotent `archived` column migration on `threads`.

**Jailed file/folder tool (shipped):** `tools/workspace.py` — read / list / search confined to a root (`$AMAGRA_WORKSPACE`). Every path goes through one chokepoint, `(root / p).resolve().is_relative_to(root)`, which defeats `../` traversal, absolute-path injection, and symlink escape. Exposed read-only at `GET /workspace/read|list|search|root` (403 on escape, 404 on missing). Writing + execution stay out of scope — those belong to the sandbox capability.

**Sandboxed code execution (shipped):** `tools/sandbox.py` runs short Python snippets under `python3 -I -S` with POSIX `setrlimit` (CPU seconds, address space, output size, no core dumps), a scrubbed environment (no inherited server secrets), a throwaway cwd, and a wall-clock timeout that kills the whole process group. Exposed at `POST /sandbox/run`, **opt-in** behind `AMAGRA_SANDBOX=1` (returns 403 otherwise). Known limitation: network is not isolated — this is a resource jail, not a defense against a determined adversary; gate it before exposing. A future hardening pass could move execution into a Docker subcontainer or namespaces.

**Stop / regenerate / edit (shipped):** the chat composer can stop an in-flight stream (AbortController), regenerate the last reply (↻ — re-runs the last prompt, truncating the stored turn), and edit any prior user message (✎ — drops that turn and everything after via `POST /threads/{id}/truncate?keep=N`, then resends).

**Live web search (shipped):** `tools/web.py` behind a provider abstraction — default **SearXNG** (self-hosted, no API key; set `SEARXNG_URL`), with **Brave** (`BRAVE_API_KEY`) and **Tavily** (`TAVILY_API_KEY`) as opt-in keyed alternatives. `GET /search/web?q=` (503 until a backend is configured) and `GET /search/status`. Every provider returns the same `{title, url, snippet}` shape.

**In-agent tool loop (shipped):** `tools/tool_loop.py` + `tools/catalog.py` — a provider-agnostic loop (LLM injected) where the model emits a fenced JSON action (`{"tool","args"}`), the catalog executes it (file / sandbox / web, with config gates so unusable tools aren't offered), the observation is fed back, bounded to N rounds. Exposed at `POST /tools/run` and `GET /tools/list`; each call emits a `tool.call` event. **Remaining polish:** auto-invoking this loop inside the *default* specialist-agent chat flow (today it's a dedicated endpoint) — the local phi4-mini's reliability at emitting structured tool JSON is the open question there, so it's deliberately opt-in for now.

---

### v1.1.2 — Eval Rigor & Security Hardening *(✅ shipped 2026-06-16)*

A maintenance release — no new user-facing capability, but routing claims and the threat surface are now defensible. Prompted by an external multi-model review.

| Item | Status |
|------|--------|
| Router collapse — remove the discarded keyword router from the hot path; `core_brain` is the sole authority (#20) | ✅ shipped |
| Routing-eval leakage guard — drop fuzzy-joined + thumbs-down traces from learned-router training (#19) | ✅ shipped |
| Sealed adversarial routing set + Fleiss' κ multi-rater harness — the honest accuracy floor, documented in FINDINGS.md | ✅ shipped |
| Security (§3 review) — constant-time admin compare, `RLIMIT_NPROC` fork-bomb guard, exposure docs, fail-closed boot test (PR #24) | ✅ shipped |
| Test suite 766 → 790 | ✅ shipped |

---

### v1.2 — Multi-Provider & Workspaces *(◑ partially shipped v1.2.0)*

Break the single-model ceiling and give each project its own isolated space.

| Item | Impact | Difficulty | ROI | Status |
|------|--------|-----------|-----|--------|
| Provider abstraction — Claude / GPT / Gemini / vLLM / LM Studio | 9 | 6 | ★★★★ | ✅ shipped (Ollama/Anthropic/OpenAI; in-app model settings + desktop mode) |
| Hybrid inference — escalate compound/low-confidence queries to cloud | 8 | 5 | ★★★★ | ⬜ planned |
| Custom agent builder — name, system prompt, keywords via admin UI | 8 | 4 | ★★★★ | ⬜ planned |
| Workspaces — multiple isolated projects per user | 8 | 5 | ★★★★ | ⬜ planned |
| RBAC — owner / admin / member roles | 8 | 5 | ★★★★ | ⬜ planned |

**Provider swap happens below the coordinator** — routing, memory, and telemetry are unaffected. Local stays default; cloud escalates only for hard tasks.

---

### v1.3 — Cross-Model Prompt Debugger *(✅ shipped v1.3.0–1.3.1)*

The differentiated wedge (issue #9) — compare any prompt across your local model and cloud models side by side, in one local app.

| Item | Status |
|------|--------|
| `POST /debug/prompt` — run one prompt across N models concurrently, each output + latency + length, failures isolated | ✅ shipped |
| Run Across Models UI panel | ✅ shipped |
| Cross-model divergence highlight (#38) | ✅ shipped (v1.3.1) |
| Static, client-side prompt analysis — health score, missing-context detection, one-click auto-repair | ✅ shipped |

---

### v1.4 — Unified Workspace UI *(✅ shipped v1.4.0–1.4.6)*

The dashboard's top-level surfaces consolidated into 6 coherent views with observability as the hero screen — a reorganization, not a deletion — followed by a brand/UI refinement pass.

| Item | Status |
|------|--------|
| 6 primary views — Workspace · Runs · Cognition · Memory · Research · Settings | ✅ shipped (v1.4.0) |
| Single sidebar nav, consistent serif `PageHeader` across all views | ✅ shipped (v1.4.1) |
| Runs: list → detail aligned to the standard page layout | ✅ shipped (v1.4.3) |
| Cognition: UCI · Risk · Events · Plan Graph in one dashboard grid | ✅ shipped (v1.4.1) |
| Brand pass — lux-card sweep, gold-gradient titles, AMAGRA wordmark favicon | ✅ shipped (v1.4.2–1.4.4) |
| Risk Gate factor disclosure + OCAC stability metrics on the dashboard | ✅ shipped (v1.4.5–1.4.6) |
| Monaco code pane — read + DiffEditor + Apply via `POST /workspace/apply` | ⬜ planned |

**Why a standalone milestone:** the view consolidation was orthogonal to the capability work — it reorganized what already exists rather than adding runtime features, so it shipped on its own track.

---

### v1.5 — Hybrid Inference *(✅ shipped v1.5.0, 2026-06-23)*

Provider/model switching already shipped (v1.2.0 Model Choice) and cross-model comparison landed in v1.3.0 (Debugger). What remains is the **automatic policy**: keep local as the default, but escalate compound or low-confidence queries to a cloud model (Claude/GPT-4o) *without the user choosing* — and account for the cost so escalation stays budgeted and visible.

| Item | Impact | Difficulty | ROI | Status |
|------|--------|-----------|-----|--------|
| `LLMProvider` protocol — formalize Ollama + Anthropic + OpenAI-compat adapters | 8 | 6 | ★★★★ | ✅ shipped (`providers/` — base/registry + 3 adapters) |
| `GenResult` — text + tokens + `cost_usd` + latency on the generation path | 7 | 3 | ★★★★ | ✅ shipped (additive `generate_detailed()`; exact usage from Anthropic) |
| Routing confidence signal — `decide_with_confidence()` exposes how decisive the route was | 7 | 2 | ★★★★ | ✅ shipped |
| Declarative escalation policy — `default=local-fast`, `compound→cloud`, `confidence_below:0.6→cloud` | 8 | 5 | ★★★★ | ✅ shipped (`providers/policy.py` `EscalationPolicy` + `load_policy`, off by default behind `AMAGRA_HYBRID=1`) |
| `select_provider(decision, tier)` — tier gate, budget check, fallback chain | 8 | 4 | ★★★★ | ✅ shipped (`providers/policy.py`; cheap no-network readiness gate, falls back to local with a reason) |
| Agent hot path through `select_provider` (flag-gated, local stays default) | 7 | 2 | ★★★★ | ✅ shipped (coordinator enhancement gate; legacy compound/moderate preserved, hybrid adds low-confidence escalation) |
| `cost_usd` → traces table → UCI Productivity cost axis | 6 | 4 | ★★★★ | ✅ shipped (`runs` cost columns + `record_cost`/`cost_summary`, `GET /runs/cost`, Cognition "Inference Cost" cell) |

**Escalation happens below the coordinator** — routing, memory, and telemetry are unaffected. Local stays the default; cloud escalates only for hard or ambiguous tasks, behind a flag, with cost surfaced on the Cognition dashboard.

---

### v1.5.2 — Release Hygiene & Adoption Floor *(◑ shipped v1.5.2, 2026-06-24 — launch + onboarding still open)*

The "make it adoptable" floor (revenueGPT Phase A) plus release mechanics. All non-breaking — clears the runway before the v1.6 workspace schema change.

| Item | Impact | Difficulty | ROI | Status |
|------|--------|-----------|-----|--------|
| Version bump 1.5.1 → 1.5.2 (`api.py`, `ui/package.json`, `ui/src/constants.js`) | — | 1 | — | ✅ shipped (tag v1.5.2) |
| Land Platform Entity Model RFC (`docs/PLATFORM_ENTITY_MODEL.md`, PR #54) — the v1.6 architecture | 7 | 1 | ★★★★ | ✅ shipped (PR #54) |
| Land `feat/payments-launch-readiness` — Stripe checkout + launch endpoints (already built) | 8 | 3 | ★★★★ | ✅ shipped (PR #33) |
| Onboarding finish — 5-min clone→first-answer, startup diagnostics, auto thread titles | 8 | 4 | ★★★★★ | ⬜ next-week target |
| **Public launch** — Show HN / r/LocalLLaMA / Docker Hub / Homebrew (the one ★★★★★ still pending) | 9 | 3 | ★★★★★ | ⏳ next-week target (#9) |

---

### v1.5.3 — Leverage & Workspace Groundwork *(proposed)*

Additive features that compound adoption and lay seams for v1.6 **without** the schema break. The bridge into the workspace milestone.

| Item | Impact | Difficulty | ROI | Status |
|------|--------|-----------|-----|--------|
| OpenAI-compatible `/v1` API — `OPENAI_BASE_URL=localhost:8000/v1` drop-in (revenueGPT #2, pulled earlier) | 9 | 5 | ★★★★★ | ⬜ |
| Decision-replay polish — visual timeline, memory-influence view, exportable + permalink (revenueGPT #3) | 8 | 4 | ★★★★★ | ⬜ |
| Per-workspace memory **namespace seam** — extend the existing `ContextVar[int]` tenant scope as a latent namespace so v1.6 adds UI/RBAC, not a migration | 7 | 4 | ★★★★ | ⬜ |
| Monaco code pane — read + DiffEditor + Apply via `POST /workspace/apply` (last open v1.4 item) — **now folded into the v1.6 Prompt-as-Artifact foundation; see [`PROMPT_ARTIFACT_CONTRACT.md`](PROMPT_ARTIFACT_CONTRACT.md)** | 6 | 4 | ★★★★ | ⬜ |

---

### v1.5.4 — Routing Seam & Recall Robustness *(✅ shipped 2026-06-26)*

A small correctness + extensibility release surfaced while hardening the runtime. No new user-facing capability; the routing layer gains its extension seam and two latent bugs are closed.

| Item | Status |
|------|--------|
| Swappable `Router` seam over `core_brain` — `orchestration/router_interface.py` (`Router` Protocol, `BrainRouter` adapter, `get_router`/`set_router`), additive, off the hot path (PR #62) | ✅ shipped |
| Context-bleed recall guard — `get_memory_context` no longer injects a different quantitative *instance* of the same template (the cow/sheep eval anchored answers on stale numbers at ~0.77 cosine) (PR #63) | ✅ shipped |
| Learned-router graceful degradation — `train()` returns a 503-mapped error on an undertrainable corpus instead of a 500; adaptive CV folds; no caching of failed trains (PR #63) | ✅ shipped |
| Eval-rigor doc framing — REFERENCE.md accuracy numbers reframed as internal dev metrics, closing #20 (PR #61) | ✅ shipped |
| Test suite → 914 passing (+ regression tests for both bugs) | ✅ shipped |

**Open follow-up:** wire the coordinator's hot path onto `get_router()` (the seam exists but nothing imports it — Router Phase 2, #64, relates to #19); remove the stale unimported `scripts/memory_context.py` duplicate (#65).

---

### v1.6 — Workspaces & RBAC

Multiple isolated projects per user, role-based access, and a custom agent builder. (Deferred past the launch-wedge pivot — the original v1.2/v1.3 slots shipped as Model Choice and the Cross-Model Debugger instead.)

**Scope (decided):** v1.6 ships **single-user workspaces** — per-user isolated projects, RBAC roles, and the agent builder. The full multi-tenant model (Organization → Project → Workspace + billing tenancy) in [`PLATFORM_ENTITY_MODEL.md`](PLATFORM_ENTITY_MODEL.md) is the **north-star target, implemented in layers**: v1.6 builds the Workspace + binding + cascade core for a single user; the Organization/tenancy tier lands with team memory in **v1.7**. Org/billing tenancy is explicitly deferred — not built dormant — to keep this milestone shippable.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Workspaces — multiple isolated projects per user, per-workspace memory namespace | 8 | 5 | ★★★★ |
| RBAC — owner / admin / member roles, enforced at the route layer | 8 | 5 | ★★★★ |
| Custom agent builder — name, system prompt, keyword triggers via admin UI | 8 | 4 | ★★★★ |
| Workspace switcher in nav — active-workspace `ContextVar` through routing + memory | 6 | 4 | ★★★★ |
| Per-workspace settings — default provider, enabled agents, routing preferences | 6 | 4 | ★★★★ |

#### v1.6 foundation — Prompt-as-Artifact (Track D)

The keystone of the "Prompt-IDE" pivot, and the spine several v1.6 items were independently groping toward. Spec: [`PROMPT_ARTIFACT_CONTRACT.md`](PROMPT_ARTIFACT_CONTRACT.md) (proposed **v4 amendment** to [`PLATFORM_ENTITY_MODEL.md`](PLATFORM_ENTITY_MODEL.md)).

**The finding:** the entity model makes the *response* first-class (`Artifact`, §5 — versioned, durable) and the *prompt* nothing at all (browser `localStorage` + a raw-string field in `model_choices`). → execution memory but no source memory. Fixing this asymmetry is what every downstream IDE feature (Explorer, inline diagnostics, AI Actions, extensions, marketplace) hangs off.

**The amendment:** add `Prompt` + `PromptVersion` as a design-plane resource and a `Run.prompt_version_id` link, making P and R symmetric. Inherits versioning, reference-not-own, templates/marketplace for free.

Tracked under epic **#67**.

| Item (dependency order) | Impact | Difficulty | ROI | Issue |
|------|--------|-----------|-----|-------|
| FS jail: add write ops (write/mkdir/move/delete) behind owner-action gate — the one foundation task | 8 | 3 | ★★★★★ | #68 |
| Repoint Prompt editor off `localStorage` → `/workspace/*` (prompts become files) | 7 | 3 | ★★★★ | #69 |
| Persist responses as artifacts with `prompt_version_id`; decisions key on it (**absorbs** "persist Consensus runs as durable decisions") | 8 | 4 | ★★★★ | #70 |
| Monaco + AST projection over existing analysis → inline diagnostics (**replaces** the loose "Monaco code pane" line above) | 6 | 4 | ★★★★ | #71 |

**Decisions locked:** substrate = real files on disk (git-diff for free), not localStorage/DB; chat is **demoted to an input shim, not deleted** (retire only after `R*.response` reaches parity — it's the current activation path); AST = index layer over existing `computeMetrics`/`structChecks`, not a rewrite. **Gated behind launch (#9).**

---

### v1.7 — Team Memory & Enterprise Governance

The moment two users share a memory is the moment you have a moat no chat UI can copy. The governance angle is category-defining: "Every AI decision in your org — logged, explainable, replayable, on-prem."

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Team memory — shared FAISS index, per-workspace | 10 | 7 | ★★★★★ |
| Admin console — user management, key provisioning | 7 | 5 | ★★★★ |
| Encrypted memory sync/backup — cross-machine for Pro | 8 | 6 | ★★★★ |
| Weekly "your AI got smarter" digest email | 7 | 2 | ★★★★★ |
| SSO/SAML integration | 9 | 6 | ★★★★ |
| Audit log export (CSV, JSON, PDF) + CoA trail | 9 | 4 | ★★★★★ |
| Data retention policies — configurable TTL per workspace | 8 | 4 | ★★★★ |
| Air-gapped installer | 8 | 5 | ★★★★ |

**Team memory:** every useful exchange any team member has is available to all agents. Org knowledge that compounds — a switching cost no competitor can clone.

---

### v2.0 — Agent Registry & Marketplace

Agents become portable artifacts; the runtime stays the product.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Agent SDK — manifest-declared community agents | 9 | 7 | ★★★★ |
| Importable agent packs — export/import as YAML or ZIP | 8 | 4 | ★★★★ |
| Curated registry — Official / Verified community / Local tiers | 8 | 6 | ★★★ |
| Standalone environment — execution graph as the interface | 8 | 8 | ★★★ |

Registered agents automatically participate in routing, telemetry, memory retrieval, critic gate, and step verification — capabilities become extensible without compromising runtime quality.

---

### Platformization — small runtime, large ecosystem

Generalize v2.0 from *agent* extensibility to a unified **contribution model** —
the "modular runtime, not modular app" thesis in [`PLUGIN_ARCHITECTURE.md`](PLUGIN_ARCHITECTURE.md).
Much of this already exists at the provider layer (`MemoryBackend` ABC + 3 backends,
`ModelProvider`/`EmbeddingProvider`, the `core/registry.py` extension host); the work
is to **unify and open what's already modular**, via strangler-fig (no rewrite):

| Step | Item | Status |
|------|------|--------|
| 1 | Declare the philosophy — `PLUGIN_ARCHITECTURE.md` + this track | ✅ |
| 2 | **`Router` protocol** + `BrainRouter` (core_brain is already the structured routing authority → thin adapter); coordinator depends on `get_router()`; retire the drifted off-hot-path `router.py` decision fns | ◑ seam shipped (#62) — wiring coordinator onto `get_router()` next (#64), router.py cleanup (#19) |
| 3 | Unify per-subsystem registries → one `contributes:` manifest; built-ins re-register as first-party plugins | ⬜ |
| 4 | First-party **SDK** — documented contracts + manifest (trusted authors) | ⬜ |
| **separate milestone** | **Isolation & third-party marketplace** — out-of-process host, *enforced* permissions, vetted registry/trust tiers | ⬜ |

**Hard boundary:** extensibility ≠ trust. The in-process host is a convenience
layer; a third-party marketplace makes it a **security boundary** (an AI
extension reaches prompts, memory, docs, API keys, tool calls — far past a VS Code
theme). The current `sandbox` is a resource jail, *not* a security boundary. Ship
the marketplace only on a real isolation model — as its own milestone, never folded
into the contribution model.

---

### Long-term Bets

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Multi-agent pipeline UI — drag-and-drop agent graph | 8 | 8 | ★★★ |
| Decision replay as shareable artifact — permalink to any decision | 8 | 4 | ★★★★★ |
| OpenAI-compatible API surface — drop-in replacement | 9 | 5 | ★★★★★ |
| Edge deployment — Raspberry Pi / NAS | 7 | 7 | ★★★ |

---

### Vision alignment — "AI operating layer"

The long-horizon framing (Amagra as the operating layer above models, agents, and devices —
*the layer survives every model generation*) lives in [`VISION.md`](VISION.md).
These are the **buildable seeds** distilled from it, mapped to where they fit. They are
candidates, not commitments — each compounds an existing strength rather than adding a new pillar.

| Seed | Builds on | Natural slot | Impact | Difficulty |
|------|-----------|--------------|--------|-----------|
| **Consensus Engine** — multi-model agreement/confidence/contradiction map → consensus answer or "models disagree, here's why" (turns divergence from a *debug* feature into a *trust* feature) | Cross-model debugger (v1.3) + critic gate | v1.5 / v1.8 | 9 | 6 |
| **Trust Layer** — tag every claim fact / estimate / assumption / opinion, traceable | Provenance + decision replay | v1.8 | 8 | 6 |
| **Executive Mode** — return *decisions* (Option A/B + trade-offs + recommendation + confidence), not just answers | World model + risk engine | v1.8 | 7 | 5 |
| **Proactive surface** — "What needs my attention today?" → one prioritized answer; risk warnings, prepared materials | Cognitive OS suggestion engine + world model | v1.9 | 8 | 7 |
| **Memory vaults + zero-knowledge** — personal / business / financial vaults, user-owned, granular permissions, "show me everything you accessed" | Tenant scope + audit trail | v1.7 (governance) | 8 | 7 |
| **Taste Engine** — learn this user's notion of quality + communication/decision patterns | Outcome-weighted memory | v2.x | 7 | 8 |
| **Cross-device memory** — desktop / mobile / browser ext / IDE all see the same project; memory follows the person | Memory import/export + namespace seam | v2.x | 9 | 8 |

**Shipped — Consensus Engine (first slice, 2026-06-25):** `POST /consensus` runs a prompt across N models (reuses the debugger fan-out), then computes a pairwise cosine **agreement matrix** over the answers (local nomic embeddings), a verdict (consensus / partial / divergent), the most-representative answer, and named dissenters — with an optional neutral-judge synthesis of a merged answer + disagreement note. Pure analysis in `core/consensus.py` (injectable embedder, fully unit-tested); route in `routes/consensus.py`; UI = Workspace → **Consensus** (`ui/src/ConsensusTab.jsx`). The full matrix ships with the verdict so it stays inspectable. *Open:* persist a consensus run as a durable decision/memory; calibrate thresholds on real outputs; this is the first stress-test of accountability spanning multiple X's.

---

## Strategic Positioning

**The category to own:** not "local chat UI" — Open WebUI owns that. The winnable category is **the accountable AI runtime**: memory + explainability + verification as infrastructure.

The architecture already justifies this:

```
Planner DAG          → dependency-aware task decomposition
Step Verifier        → per-step pass/fail/retry/abort
Risk Engine          → evidence-driven reflection gating
World Model          → persistent project context
Event Bus            → typed observability at every step
Skill Graph          → 21-node capability disambiguation
Decision Graph       → causal trace with regret weighting
Learning System      → outcome-weighted memory, confidence calibration
```

That is not an agent product. That is a **cognitive runtime**.

**What is genuinely differentiated — protect these:**
- Decision replay and routing telemetry (nobody else shows *why*)
- Outcome-weighted memory that learns from feedback
- The critic gate / step verifier loop
- Honest-metrics culture — weaponize it, no one else admits weaknesses in their README

**What is NOT a moat:** routing accuracy (frontier models do it implicitly), agent system prompts, the number of tabs.

**Moats, ranked by realism:**
1. **Data gravity:** months of accumulated personal/team memory is a switching cost no competitor can clone. Memory import/export paradoxically increases trust — do it anyway.
2. **Trust/audit trail:** complete decision provenance is hard to retrofit into chat-first competitors and aligns with where regulation is heading.
3. **Agent registry network effects:** real, but only after the SDK ships and only if the runtime is excellent.

---

## Monetization & revenue

Open-core: the free self-hosted tier is the distribution engine; paid tiers wrap the moat (managed hosting, team shared memory, governance, marketplace). **Pricing tiers, marketplace packs, and revenue projections are maintained separately, outside this repo** — this document stays feature-focused so the roadmap and the commercial plan don't drift.

---

## Growth & Distribution

Ranked by expected ROI for a self-hosted developer tool:

1. **GitHub-native (highest ROI, near-zero cost):** the repo is the funnel. CI badges, a 30-second routing GIF, a comparison table vs Open WebUI/LibreChat. Launch: Show HN ("Self-hosted AI that shows you why it answered that way"), r/LocalLLaMA, Product Hunt.

2. **Self-host catalogs:** Docker Hub, Unraid / CasaOS / Runtipi / Umbrel templates, Homebrew formula. Self-hosters discover via catalogs; being absent = invisible.

3. **Content / SEO:** honest-eval culture. "We measured our router at 99% and here's why that number is misleading" tops HN. Target: "open webui alternatives," "self-hosted AI memory," "local LLM with RAG."

4. **Community:** Discord + public roadmap (Promises already exists). The Agent SDK is the community flywheel: every community agent is free R&D and a switching cost.

5. **Partnerships:** Ollama ecosystem listing, vLLM / LM Studio compatibility content.

**Defer:** paid ads, affiliates, outbound enterprise sales — premature before product-led traction.

---

## What to Defer

| Item | Why |
|------|-----|
| GRAM / Stochastic Multi-Trajectory | Needs frontier-class model to show value |
| RCP/FMI licensing | No buyer until peer-reviewed and cited |
| AlphaProof-style R&D | phi4-mini cannot resolve research-level math |
| Full Lean 4 integration | Cost far exceeds revenue unlock at this scale |
