# Project Map — Amagra

**Updated:** 2026-08-07 · **Version:** v1.8.1 (working branch: `feat/v1.9.0-decision-economics`)
**Mission:** the local-first cognitive runtime developers build agents on top of.

This is the orientation map. Each area links to the canonical document — this file does **not** duplicate their content.

## Documentation layout

Docs are grouped by what kind of question they answer. Every file that exists on
disk is listed below — an entry missing from this map is the signal something
drifted, not a reason to assume the file doesn't matter.

| Directory | Question | Contents |
|---|---|---|
| `docs/` (top level) | *Where do I start?* | This map · [GUIDE.md](GUIDE.md) (day-to-day usage) · [ARCHITECTURE.md](ARCHITECTURE.md) (evaluator-facing claims → files) · [REFERENCE.md](REFERENCE.md) (every number) · [ROADMAP.md](ROADMAP.md) (what's next) |
| [`docs/design/`](design/) | *What are the contracts?* | [PLATFORM_ENTITY_MODEL.md](design/PLATFORM_ENTITY_MODEL.md) · [PLUGIN_ARCHITECTURE.md](design/PLUGIN_ARCHITECTURE.md) · [PROMPT_ARTIFACT_CONTRACT.md](design/PROMPT_ARTIFACT_CONTRACT.md) · [IDENTITY.md](design/IDENTITY.md) · [OCAC_STABILITY_BRIDGE.md](design/OCAC_STABILITY_BRIDGE.md) · [TCST_AGENT_MODEL.md](design/TCST_AGENT_MODEL.md) · [DESIGN_PRINCIPLES.md](design/DESIGN_PRINCIPLES.md) (the UX filter) |
| [`docs/records/`](records/) | *What happened, and what's true?* | **Evergreen:** [HISTORY.md](records/HISTORY.md) (phase-by-phase build log) · [FINDINGS.md](records/FINDINGS.md) (routing eval write-up) · [FAILURES.md](records/FAILURES.md) (invariants you must not break) · [ISSUES.md](records/ISSUES.md) (known bugs & limitations) · [OPEN_PROBLEMS.md](records/OPEN_PROBLEMS.md) (epistemic-layered register of what's *not* settled — start here for "what's open") · [SCORECARD.md](records/SCORECARD.md) (capability maturity, 1–10) · [STRATEGIC_SCORECARD.md](records/STRATEGIC_SCORECARD.md) (orchestration-roadmap maturity, 0–100%) · [PUBLISH_CHECKLIST.md](records/PUBLISH_CHECKLIST.md) (closed, local-only, gitignored). **The "what's next" chain** (each derives from the previous — don't duplicate, link): [IMPROVEMENTS.md](records/IMPROVEMENTS.md) (the *why*, from the OCAC bridge) → [METRICS_ROADMAP.md](records/METRICS_ROADMAP.md) (phased execution checklist) · [V1.9.0_SCOPE.md](records/V1.9.0_SCOPE.md) (current release's scope reality-check) · [UPCOMING.md](records/UPCOMING.md) (release-sequencing plan) · [NEXT_VERSION.md](records/NEXT_VERSION.md) (rolling queued-but-not-shipped register, ties the two together). **Dated one-off analyses:** [REFACTOR_ANALYSIS_2026-07.md](records/REFACTOR_ANALYSIS_2026-07.md) (status noted inline — partially shipped, partially open, one item explicitly deferred). |
| [`docs/product/`](product/) | *Why does this exist, for whom?* | [VISION.md](product/VISION.md) · [POSITIONING.md](product/POSITIONING.md) · [COMPARISON.md](product/COMPARISON.md) (honest head-to-head) · [LAUNCH_DEBUGGER.md](product/LAUNCH_DEBUGGER.md) · [_someday.md](product/_someday.md) (frozen ideas — not current scope) |
| [`docs/ops/`](ops/) | *How do I run it in the world?* | [DEPLOY.md](ops/DEPLOY.md) (marketing site + Docker) · [PROVIDERS.md](ops/PROVIDERS.md) (cloud model keys) · [RELEASING.md](ops/RELEASING.md) (tag → build pipeline) · [DISASTER_RECOVERY.md](ops/DISASTER_RECOVERY.md) · [TROUBLESHOOTING_WINDOWS.md](ops/TROUBLESHOOTING_WINDOWS.md) |
| `docs/ideas/` | *What's speculative, pre-decision?* | [delta-algebra-spec.md](ideas/delta-algebra-spec.md) + its two check scripts (`delta_reducer_check.py`, `router_parity_check.py`) · [knowverse.md](ideas/knowverse.md) · [revenueGPT.md](ideas/revenueGPT.md). Not linked from anywhere else on purpose — promote to `design/` or `product/` if a decision is made, otherwise leave parked here. |
| `docs/brand/` | assets | logo, wordmarks, social-preview card |
| `docs/screenshots/` | assets | README screenshots |

The live queue of bugs and features is **GitHub Issues**; docs are records, not queues.
A curated subset of these docs is served by the API at `GET /docs/index` + `GET /docs/{name}`
(`routes/docs_api.py`, `_ALLOWED_DOCS`) — curated means evergreen reference material;
the dated planning docs (`NEXT_VERSION`, `UPCOMING`, `V1.9.0_SCOPE`,
`REFACTOR_ANALYSIS_2026-07`), frozen ideas (`_someday.md`, `docs/ideas/`), and the
gitignored `PUBLISH_CHECKLIST.md` are deliberately left out of that API surface —
they're for contributors reading the repo, not the in-app viewer.
`test_routes_docs_api.py::test_allowed_docs_all_exist_on_disk` keeps the map itself honest;
nothing currently checks that every *evergreen* doc has an entry, so update both when adding one.

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
| `tools/` | Agent tools: workspace files, sandbox, web search, the OCAC research-graph adapter |
| `training/` | Auto-retrain helpers for the learned router |
| `ui/` | React dashboard (Vite) — see `ui/src/README.md` for the folder contract, `ui/src/config/navConfig.js` for the launcher |
| `desktop/` | Electron shell + `install-desktop-entry.sh` (Linux launcher entry) |
| `packaging/` | AppImage build (`build-appimage.sh`) |
| `workbench/` | Dev tooling unreachable from the running app (split out 2026-07-14, PR `af4d958`): `workbench/evaluation/` (routing benchmarks, adversarial eval, rater harness — was `evaluation/`), `workbench/scripts/` (`migrate.py`, `migrate_to_single_db.py`, `ModelOverview.py` — was `scripts/`), `workbench/brand/` (diagram generators). Two files stayed behind because they're load-bearing at runtime: `infrastructure/math_metrics.py`, `memory_core/memory_gate.py`. |
| `tests/` | Pytest suite (1,275 passing, 1 skipped — measured 2026-08-07) |

Runtime state (`memory/*.db`, `tasks.db`, `logs/`) is generated, never committed.

---

## Current snapshot

| | |
|---|---|
| Version | v1.8.1 (decision-economics groundwork + reliability hardening; `v1.9.0` in progress on `feat/v1.9.0-decision-economics`, see [UPCOMING.md](records/UPCOMING.md)) |
| Specialist agents | 10 (`agents/registry.py` is canonical) |
| Skill graph | 21 nodes |
| Routing accuracy | ~99% curated · held-out (n=91): ~31% keyword-only → ~53% with semantic fallback (on by default) — internal metrics, not validated (single-rater), see [FINDINGS.md](records/FINDINGS.md) §3a |
| Memory | SQLite → auto-promote to FAISS at 800 entries · 52× LRU cache (vector count is runtime state — last recorded 628+ in [SCORECARD.md](records/SCORECARD.md), not re-measured here) |
| UCI health | Last recorded ≈ 80.8 ([SCORECARD.md](records/SCORECARD.md)/Phase 37 notes) — internal heuristic, not a quality measure, not surfaced publicly, and **not re-measured for this snapshot**; treat any UCI number as dated the moment it's written down |
| API surface | 155 routes (measured 2026-08-07 via `len(app.routes)`) |
| Tests | 1,275 passing, 1 skipped (measured 2026-08-07) |
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
| v1.6.4 | System alignment & honesty pass (measured routing accuracy, identity contract, skill-graph coupling, OCAC §6 sync) | ✅ Shipped |
| v1.7.0 – v1.7.6 | *(shipped — tagged in git, **not yet written up in [HISTORY.md](records/HISTORY.md)**; see the "Known gaps" section below)* | ✅ Shipped |
| **v1.8.0 – v1.8.1** | Decision-economics groundwork (EV selector + counterfactual recording, not yet closing O2) · reliability hardening (thread-safety, rate limits) · review loop (flag-gated, off by default) — see [UPCOMING.md](records/UPCOMING.md) | ✅ Shipped |
| **v1.9.0** | Decision-economics loop closes O2 (needs real feedback volume, [O5](records/OPEN_PROBLEMS.md#o5)) · review loop promoted default-on — see [V1.9.0_SCOPE.md](records/V1.9.0_SCOPE.md) | 🚧 In progress (`feat/v1.9.0-decision-economics`) |
| v2.0 | Workspaces & RBAC · team memory & governance · agent registry & SDK | ⬜ Planned |

See [ROADMAP.md](ROADMAP.md) for the full forward plan and [HISTORY.md](records/HISTORY.md) for the per-phase record.

---

## Known gaps

| Item | Notes |
|------|-------|
| Plan Graph pre-query | Empty state until first compound query runs. |
| Feedback-negative 36% | 1,096 real 👍/👎 ratings exist (64% positive) — Adaptation is the weakest UCI layer; negative feedback isn't yet mined into fixes. |
| No external benchmarks in the health picture | HumanEval/adversarial/recall harnesses exist in `evaluation/` but run ad hoc — no dated ledger, no unseen-workload suite. |
| HISTORY.md stops at v1.6.4 | Seven tagged releases (v1.7.0–v1.8.1) shipped since without a HISTORY.md entry; the phase-status table above summarizes v1.8.0–v1.8.1 from [UPCOMING.md](records/UPCOMING.md), but v1.7.x has no write-up anywhere. Reconstruct from `git log --merges` PR titles when someone has the time. |

Full bug/limitation list: [ISSUES.md](records/ISSUES.md).
