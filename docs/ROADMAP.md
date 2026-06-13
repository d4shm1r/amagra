# Amagra — Roadmap

> **North star:** the only AI runtime where the system remembers everything, verifies itself, and can prove why it did what it did — on hardware you control. Memory, verification, and provenance are the product; everything else is an adapter.

---

## Version History

### v0.9.1 — Security Hardening

| Item | Detail |
|------|--------|
| Auth deny-by-default | Replaced `_PROTECTED_PREFIXES` whitelist with `_PUBLIC_PATHS` allowlist. All ~40 routes gated when `REQUIRE_AUTH=1`. |
| Admin proxy fix | Removed `host == 127.0.0.1` bypass that broke behind nginx/Caddy. `ADMIN_TOKEN` env var required; 503 when unset. |
| CORS locked | `ALLOWED_ORIGINS` env var, defaults to `localhost:3000,localhost:8000`. No wildcard. |
| Rate limiting | Sliding window per key: free 10/min · developer 60/min · team 300/min · enterprise unlimited. `X-RateLimit-*` headers. |
| CI/CD | GitHub Actions: ruff lint + pytest + Docker build on push and PR. |
| Streaming shipped | `ChatTab.jsx` wired to `POST /ask/stream`; tokens render as they arrive. |

### v0.9.2 — Async, Concurrency & UI Consolidation

| Item | Detail |
|------|--------|
| Async `/ask` | `coordinator.invoke` wrapped in `asyncio.run_in_executor`; event loop no longer blocks during LLM calls. |
| WAL mode | `PRAGMA journal_mode=WAL` on all SQLite DBs at startup. Eliminates "database is locked". |
| Tenant scoping | `ContextVar[int]` propagates `owner_key_id` through the full call chain. Memory search and save are tenant-isolated. |
| UI consolidation | 29-tab sidebar → 4 surfaces: Chat · Memory · Inspect · Settings. `SubNav` horizontal strip. |

### v0.9.3 — Memory Surface, Multi-provider & Brand

| Item | Detail |
|------|--------|
| Memory surfaced inline | Top 2 memories auto-show as "◈ Remembered · [snippet]" below each response. |
| Emoji → unicode | Emoji removed from constants/UI; replaced with coherent unicode: ◈ λ ⊹ ∑ ¶ ∴ ⊃ § ⊓ ⬡ ⚙ ▸. |
| Multi-provider | `AskRequest` gains `provider` field; `AnthropicProvider.generate()` available alongside Ollama. `AskResponse` gains `model_used`. |

### v0.9.4 — Brand Identity & Luxury UI

| Item | Detail |
|------|--------|
| Brand color | VS Code Blue `#007ACC` → Amagra sky-blue `#0EA5E9` across all design tokens. |
| Design tokens | `theme.js` is the single source for colors, fonts, spacing, radius. |
| Routing animation | `RoutingStrip` in stream: "◈ analyzing…" → "◈ [domain] → [agent]". Collapses on first token. |
| Feedback closure | After 👍/👎: "◈ Got it — routing adjusted" fades out over 3.5s. |
| Typography | `JetBrains Mono` top of monospace stack. Body darkened to `#191919`. |

### v0.10.1 — RAG File Context ✅

| Item | Detail |
|------|--------|
| File upload | `POST /documents/upload` — PDF, Markdown, code, plain text up to 10 MB. |
| Inline chunker | Paragraph-boundary splitter with 800c/100c overlap. No langchain dependency. |
| Context injection | `context_files` field on `AskRequest`; top-k chunks prepended to both `/ask` and `/ask/stream`. |
| UI | File chips with upload/ready/error states; ⊕ attach button in ChatTab. |

---

## Current State

**v0.10 remaining items:**

| Item | Status |
|------|--------|
| Tests to ~60% coverage | In progress (544 passing across 39 files, routes/ + core/ + cognition/ + payment path) |
| In-product onboarding | Pending |
| DB consolidation (Alembic, single file) | Deferred — WAL + tenant isolation bought the concurrency win; Alembic adds risk |
| Vite migration (retire CRA) | Pending |
| Launch (Show HN, Docker Hub, Homebrew) | Pending |

---

## Future Roadmap

### v0.10 — Content, Tests & Launch

**Remaining high-priority items:**

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Tests: routes/ + core/ + payment path to ~60% | 8 | 5 | ★★★★ |
| In-product onboarding: first-run flow, model pull detection | 8 | 4 | ★★★★ |
| Vite migration — retire CRA (dead/unmaintained) | 6 | 3 | ★★★★ |
| Launch: Show HN + r/LocalLLaMA + Docker Hub + Homebrew | 9 | 3 | ★★★★★ |

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

### v0.11 — Tool-Using Agents

Agents that do things, not just say things. Closes the gap vs Continue/Cursor/Claude Code.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Sandboxed code execution | 10 | 8 | ★★★★ |
| Live web search (Brave/SearXNG/Tavily) | 9 | 4 | ★★★★★ |
| Shell/terminal tool for DevOps agent | 8 | 5 | ★★★★ |
| Stop / regenerate / edit-message affordances | 7 | 3 | ★★★★★ |
| Thread management: rename, fork, archive | 6 | 2 | ★★★★ |
| Memory import/export (JSON/Markdown) | 8 | 3 | ★★★★★ |

**Code execution:** Each agent optionally runs the code it writes in an isolated sandbox (Docker subcontainer, timeout/resource limits). Output inline below the code block. No copy-paste required.

---

### v1.0 — Team Memory & Workspaces

The moment two users share a memory is the moment you have a moat no chat UI can copy.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| Team memory — shared FAISS index, per-workspace | 10 | 7 | ★★★★★ |
| Workspaces — multiple isolated projects per user | 8 | 5 | ★★★★ |
| RBAC — owner / admin / member roles | 8 | 5 | ★★★★ |
| Admin console — user management, key provisioning | 7 | 5 | ★★★★ |
| Encrypted memory sync/backup — cross-machine for Pro | 8 | 6 | ★★★★ |
| Weekly "your AI got smarter" digest email | 7 | 2 | ★★★★★ |
| Agent SDK — community agents publishable and installable | 9 | 7 | ★★★★ |

**Team memory:** every useful exchange any team member has is available to all agents. Org knowledge that compounds — switching cost no competitor can clone. Natural seat expansion: more users → smarter shared brain → more lock-in.

---

### v1.x — Enterprise Governance

The governance angle is the category-defining move: "Every AI decision in your org — logged, explainable, replayable, on-prem." EU AI Act and corporate AI policies are creating budget for exactly this.

| Item | Impact | Difficulty | ROI |
|------|--------|-----------|-----|
| SSO/SAML integration | 9 | 6 | ★★★★ |
| Audit log export (CSV, JSON, PDF) | 9 | 4 | ★★★★★ |
| Data retention policies — configurable TTL per workspace | 8 | 4 | ★★★★ |
| Compliance reporting — decision trail as AI accountability artifact | 9 | 6 | ★★★★ |
| Air-gapped installer | 8 | 5 | ★★★★ |

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
| DB consolidation (Alembic) | WAL + tenant isolation bought the immediate win; schedule after data-export step |
| AlphaProof-style R&D | phi4-mini cannot resolve research-level math |
| Full Lean 4 integration | Cost far exceeds revenue unlock at this scale |
