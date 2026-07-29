# Project Map — Amagra

**Updated:** 2026-07-03 · **Version:** v1.6.3
**Mission:** the local-first cognitive runtime developers build agents on top of.

This is the orientation map. Each area links to the canonical document — this file does **not** duplicate their content.

## Documentation layout

Docs are grouped by what kind of question they answer:

| Directory | Question | Contents |
|---|---|---|
| `docs/` (top level) | *Where do I start?* | This map · [GUIDE.md](GUIDE.md) (day-to-day usage) · [ARCHITECTURE.md](ARCHITECTURE.md) (evaluator-facing claims → files) · [REFERENCE.md](REFERENCE.md) (every number) · [ROADMAP.md](ROADMAP.md) (what's next) |
| [`docs/design/`](design/) | *What are the contracts?* | [PLATFORM_ENTITY_MODEL.md](design/PLATFORM_ENTITY_MODEL.md) · [PLUGIN_ARCHITECTURE.md](design/PLUGIN_ARCHITECTURE.md) · [PROMPT_ARTIFACT_CONTRACT.md](design/PROMPT_ARTIFACT_CONTRACT.md) · [IDENTITY.md](design/IDENTITY.md) · [OCAC_STABILITY_BRIDGE.md](design/OCAC_STABILITY_BRIDGE.md) · [TCST_AGENT_MODEL.md](design/TCST_AGENT_MODEL.md) · [DESIGN_PRINCIPLES.md](design/DESIGN_PRINCIPLES.md) (the UX filter) |
| [`docs/records/`](records/) | *What happened, and what's true?* | [HISTORY.md](records/HISTORY.md) (phase-by-phase build log) · [FINDINGS.md](records/FINDINGS.md) (routing eval write-up) · [FAILURES.md](records/FAILURES.md) (invariants you must not break) · [ISSUES.md](records/ISSUES.md) (known bugs & limitations) · [OPEN_PROBLEMS.md](records/OPEN_PROBLEMS.md) (epistemic-layered register of what's *not* settled) · [METRICS_ROADMAP.md](records/METRICS_ROADMAP.md) · [IMPROVEMENTS.md](records/IMPROVEMENTS.md) |
| [`docs/product/`](product/) | *Why does this exist, for whom?* | [VISION.md](product/VISION.md) · [POSITIONING.md](product/POSITIONING.md) · [COMPARISON.md](product/COMPARISON.md) (honest head-to-head) · [LAUNCH_DEBUGGER.md](product/LAUNCH_DEBUGGER.md) · [_someday.md](product/_someday.md) (frozen ideas) |
| [`docs/ops/`](ops/) | *How do I run it in the world?* | [DEPLOY.md](ops/DEPLOY.md) (marketing site + Docker) · [PROVIDERS.md](ops/PROVIDERS.md) (cloud model keys) |
| `docs/brand/` | assets | logo, wordmarks, social-preview card |
| `docs/screenshots/` | assets | README screenshots |

The live queue of bugs and features is **GitHub Issues**; docs are records, not queues.
A curated subset of these docs is served by the API at `GET /docs/index` + `GET /docs/{name}` (`routes/docs_api.py`).

## Code layout (one line each)

| Directory | What lives there |
|---|---|
| `agents/` | The specialist agents + `registry.py` (canonical agent list) |
| `orchestration/` | LangGraph coordinator, signal router, dispatch reducer |
| `cognition/` | Reflection triage, risk gate, verifier, failure miner, stratifier |
| `core/` | Runtime spine (Context/Result contract, onion middleware), core brain, auth |
| `decision/` | Decision logging + learned weights |
| `memory_core/` | Memory backends (SQLite → FAISS), filter, context builder |
| `models/` | State models: cognitive state, identity contract, world model |
| `infrastructure/` | Event bus, metrics engine, transparency classifier, DB plumbing |
| `providers/` | Ollama / Anthropic / OpenAI / Gemini adapters |
| `routes/` | FastAPI route modules (`api.py` at the root mounts them) |
| `evaluation/` | Routing benchmarks, adversarial eval, rater harness |
| `tools/` | Agent tools: workspace files, sandbox, web search |
| `training/` | Auto-retrain helpers for the learned router |
| `ui/` | React dashboard (Vite) — see `ui/src/README.md` for the folder contract, `ui/src/config/navConfig.js` for the launcher |
| `desktop/` | Electron shell + `install-desktop-entry.sh` (Linux launcher entry) |
| `packaging/` | AppImage build (`build-appimage.sh`) |
| `scripts/` | Live utilities only: `migrate.py`, `migrate_to_single_db.py`, `ModelOverview.py` |
| `tests/` | Pytest suite (986 passing) |

Runtime state (`memory/*.db`, `tasks.db`, `logs/`) is generated, never committed.

---

## Current snapshot

| | |
|---|---|
| Version | v1.6.3 (desktop app + unified launcher nav) |
| Specialist agents | 10 (`agents/registry.py` is canonical) |
| Skill graph | 21 nodes |
| Routing accuracy | ~99% curated · held-out (n=91): ~31% keyword-only → ~53% with semantic fallback (on by default) — internal metrics, not validated (single-rater), see [FINDINGS.md](records/FINDINGS.md) §3a |
| Memory | SQLite → auto-promote to FAISS at 800 entries · 52× LRU cache (vector count is runtime state — 97 at the 2026-07-03 snapshot) |
| UCI health | h_UCI ≈ 90.8 (2026-07-03 snapshot; internal heuristic, not a quality measure — not surfaced publicly) |
| API surface | 100+ endpoints (153 routes) |
| Tests | 986 passing |
| Auth | API-key, deny-by-default when `REQUIRE_AUTH=1` |

---

## Architecture (one screen)

```
User query
    │
    ▼
QuerySignal (keyword heuristics, ~1ms, no LLM)
    │
    ├─► Direct route (high-confidence domain match)
    │
    └─► CoreBrain (LLM reasoning — ambiguous only)
            │
            └─► Coordinator (LangGraph)
                    │
                    ├─► Risk gate (reflect_level: none / light / full)
                    │
                    └─► Specialist agent
                            ├─► skill_graph disambiguation (21 nodes)
                            ├─► FAISS memory retrieval (<1ms warm)
                            ├─► critic gate (score ≥ 0.70 or regenerate)
                            └─► step verifier (pass / fail → event_bus)
```

**Agents (10):** `python_dev` · `dotnet_dev` · `it_networking` · `ai_ml` · `web_dev` · `devops` · `data_analyst` · `writer` · `knowledge_learning` · `terse`

**Cognitive OS:** `event_bus` · `world_model` · `metrics_engine` · `cognitive_state` · `risk_gate` · `skill_graph` · `step_verifier`

Endpoint and UI-tab inventories live in [REFERENCE.md](REFERENCE.md); they are not mirrored here to avoid drift.

---

## Phase status

| Phase | Name | Status |
|-------|------|--------|
| Internal builds (v0.1 → v0.10) | Foundation → Cognitive OS → RAG file context | ✅ Complete (in-app build log) |
| **v1.0.0** | First public release | ✅ Shipped |
| v1.0.1 – v1.0.4 | Lean runtime · luxe dashboard · single-file DB · tool foundations | ✅ Shipped |
| **v1.1.x** | **Tool-using agents** (live web search, in-agent tool loop) + eval rigor & security hardening | ✅ Shipped |
| **v1.2.0** | **BYO model & desktop mode** (in-app model/provider settings) | ✅ Shipped |
| **v1.3.x** | **Cross-model prompt debugger** (`POST /debug/prompt`, Run Across Models panel) | ✅ Shipped |
| **v1.4.x** | **Unified workspace UI + brand refinement** (6-view consolidation, OCAC stability metrics) | ✅ Shipped |
| **v1.5.0** | **Hybrid inference** (auto local→cloud escalation policy, cost telemetry; opt-in `AMAGRA_HYBRID`) | ✅ Shipped |
| **v1.6.0** | **Prompts as first-class, versioned artifacts** (prompt files, versions, decision links, diff) | ✅ Shipped |
| v1.6.1 – v1.6.2 | Calm tab redesign · design tokens · Cognition IA restraint | ✅ Shipped |
| **v1.6.3** | **AMAGRA desktop app** (Electron) · wordmark branding · unified ☰ launcher nav | ✅ Shipped |
| v1.7 → v2.0 | Workspaces & RBAC · team memory & governance · agent registry & SDK | ⬜ Planned |

See [ROADMAP.md](ROADMAP.md) for the full forward plan and [HISTORY.md](records/HISTORY.md) for the per-phase record.

---

## Known gaps

| Item | Notes |
|------|-------|
| Plan Graph pre-query | Empty state until first compound query runs. |
| Feedback-negative 36% | 1,096 real 👍/👎 ratings exist (64% positive) — Adaptation is the weakest UCI layer; negative feedback isn't yet mined into fixes. |
| No external benchmarks in the health picture | HumanEval/adversarial/recall harnesses exist in `evaluation/` but run ad hoc — no dated ledger, no unseen-workload suite. |

Full bug/limitation list: [ISSUES.md](records/ISSUES.md).
