# Amagra — Roadmap

> **North star:** the only AI runtime where the system remembers everything, verifies itself, and can prove why it did what it did — on hardware you control. Memory, verification, and provenance are the product; everything else is an adapter.

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
| Auth deny-by-default | `_PUBLIC_PATHS` allowlist gates all ~40 routes when `REQUIRE_AUTH=1`. `ADMIN_TOKEN` required for admin surface. |
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

### v1.1 — Tool-Using Agents *(in progress)*

Agents that do things, not just say things. Closes the gap vs Continue/Cursor/Claude Code. Memory portability and thread management already shipped (delivered early on the v1.0.x line); tool execution — jailed files, sandbox, web search — is next.

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

**Remaining for the v1.1.0 milestone:** the *in-agent tool loop* — letting agents autonomously call these tools (file / sandbox / web) mid-reasoning (JSON action → execute → append result, max 3 iters) and logging tool calls. The capabilities now exist as tools + endpoints; this is the integration that lets the model drive them.

---

### v1.2 — Multi-Provider & Workspaces

Break the single-model ceiling and give each project its own isolated space.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Provider abstraction — Claude / GPT / Gemini / vLLM / LM Studio | 9 | 6 | ★★★★ |
| Hybrid inference — escalate compound/low-confidence queries to cloud | 8 | 5 | ★★★★ |
| Custom agent builder — name, system prompt, keywords via admin UI | 8 | 4 | ★★★★ |
| Workspaces — multiple isolated projects per user | 8 | 5 | ★★★★ |
| RBAC — owner / admin / member roles | 8 | 5 | ★★★★ |

**Provider swap happens below the coordinator** — routing, memory, and telemetry are unaffected. Local stays default; cloud escalates only for hard tasks.

---

### v1.3 — Team Memory & Enterprise Governance

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

### v1.4 — Unified Workspace UI

The dashboard today is 5 top-level surfaces (Chat · Library · Memory · Inspect · Settings) fronting ~26 view components. This consolidates them into 6 coherent views with observability as the hero screen — a reorganization, not a deletion.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| 6 primary views — Workspace · Runs · Cognition · Memory · Research · Settings | 7 | 6 | ★★★★ |
| Runs: list → detail with Trace · Inspector · Decision · Policy sub-tabs | 6 | 4 | ★★★★ |
| Cognition: UCI · Risk · Events · Plan Graph in one dashboard grid | 6 | 4 | ★★★★ |
| Monaco code pane — read + DiffEditor + Apply via `POST /workspace/apply` | 7 | 6 | ★★★ |
| Extract inline style tokens to `theme.js` (dedupe ~26 style objects) | 5 | 3 | ★★★★ |

**Why a standalone milestone:** the view consolidation is orthogonal to the v1.1–v1.3 capability work — it reorganizes what already exists rather than adding runtime features, so it ships on its own track.

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

### Long-term Bets

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Multi-agent pipeline UI — drag-and-drop agent graph | 8 | 8 | ★★★ |
| Decision replay as shareable artifact — permalink to any decision | 8 | 4 | ★★★★★ |
| OpenAI-compatible API surface — drop-in replacement | 9 | 5 | ★★★★★ |
| Edge deployment — Raspberry Pi / NAS | 7 | 7 | ★★★ |

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
Skill Graph          → 18-node capability disambiguation
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
