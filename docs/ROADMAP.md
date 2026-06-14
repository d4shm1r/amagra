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
| Brand & UI | Sky-blue `#0EA5E9` design tokens in `theme.js`; 4-surface nav (Chat · Memory · Inspect · Settings); RoutingStrip animation; JetBrains Mono. |
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

### v1.1 — Tool-Using Agents

Agents that do things, not just say things. Closes the gap vs Continue/Cursor/Claude Code.

| Item | Status | Impact | Difficulty | ROI |
|------|--------|--------|-----------|-----|
| Sandboxed code execution | | 10 | 8 | ★★★★ |
| Live web search (Brave/SearXNG/Tavily) | | 9 | 4 | ★★★★★ |
| Jailed file/folder tool (`Path.resolve().is_relative_to(root)`) | | 8 | 5 | ★★★★ |
| Stop / regenerate / edit-message affordances | | 7 | 3 | ★★★★★ |
| Thread management: rename, fork, archive | | 6 | 2 | ★★★★ |
| Memory import/export (JSON/Markdown) | ✅ shipped | 8 | 3 | ★★★★★ |

**Memory import/export (shipped):** `GET /memory/export.json` (lossless — base64 float32 embeddings, re-imports with no model call), `GET /memory/export.md` (human-readable, grouped by agent), `POST /memory/import` (dedups via the near-duplicate gate, then rebuilds the FAISS index). CSV export predates this.

**Code execution:** Each agent optionally runs the code it writes in an isolated sandbox (Docker subcontainer, timeout/resource limits). Output inline below the code block. No copy-paste required.

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

## Monetization

Open-core where the moat is the paid surface. Never cripple the free tier — it is the distribution engine.

| Tier | Price | What's included |
|------|-------|-----------------|
| **Self-host Free** | $0, MIT | Everything, single-user, full source, unlimited locally |
| **Pro** | $39/mo | Managed hosting · encrypted memory sync · hosted UCI dashboard · weekly intelligence digest |
| **Team** | $249/mo | Shared team memory (the killer feature) · workspaces · RBAC · admin console |
| **Cognitive Ops** | $499–999/mo | Risk observatory · decision audit trail · verification reports · decision replay |
| **Enterprise** | $2k–10k/mo | SSO/SAML · CoA audit trail · SOC2 · air-gapped installer · signed SLA |

### Cognitive Marketplace

The highest-margin revenue stream. Skill packs, verification packs, planner packs, and world models are high-margin (configuration + tuned prompts, not infrastructure), composable, self-distributing (self-hosted users discover and upgrade), and platform-signaling (a marketplace means this is runtime infrastructure).

**Skill Packs ($99–499 one-time):**

| Pack | Price | What it adds |
|------|-------|-------------|
| DevOps | $149 | Kubernetes, Terraform, incident runbooks, SRE patterns |
| Security | $199 | OWASP, CVE triage, pentest patterns, hardening guides |
| Legal | $299 | Contract review, clause extraction, GDPR, jurisdiction logic |
| Finance | $299 | Financial statements, FCA/SEC, ratio calculation |
| Data Science | $149 | Pandas, Spark, feature engineering, model evaluation |

**Verification Packs ($49–199 one-time):** Python, Kubernetes, Security, SQL — custom step verifier criteria sets.

**Planner Packs ($99–299 one-time):** Software Sprint, Incident Response, Research Project, DevOps Migration.

**World Models ($199+):** Pre-seeded schemas with domain-specific entity vocabulary (Software, Legal, Healthcare, Financial).

---

## Revenue Projection

| Month | MRR | Driver |
|-------|-----|--------|
| 1 | $0 | Launch build |
| 2 | $39 | First managed-hosting customer |
| 3 | $200 | ~5 Pro (organic GitHub) |
| 6 | $1,200 | 20 Pro + 2 Team + marketplace |
| 8 | $2,800 | 30 Pro + 4 Team + 1 Cognitive Ops |
| 12 | $10k–15k | 50 Pro + 8 Team + 3 CogOps + 1 Enterprise |
| 18 | $20k–40k | Teams building domain agents on the runtime |

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
