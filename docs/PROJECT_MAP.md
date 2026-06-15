# Project Map — Amagra

**Updated:** 2026-06-15 · **Version:** v1.1.0
**Mission:** the local-first cognitive runtime developers build agents on top of.

This is the orientation map. Each area links to the canonical document — this file does **not** duplicate their content.

| If you want… | Read |
|---|---|
| Evaluator-facing architecture (claims → files) | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What it is, how it works, every number | [REFERENCE.md](REFERENCE.md) |
| How to use it day to day | [GUIDE.md](GUIDE.md) |
| What was built, phase by phase | [HISTORY.md](HISTORY.md) |
| What's next | [ROADMAP.md](ROADMAP.md) |
| Known bugs & limitations | [ISSUES.md](ISSUES.md) |
| Invariants you must not break | [FAILURES.md](FAILURES.md) |
| Routing eval write-up | [FINDINGS.md](FINDINGS.md) |
| Pre-public-release checklist | [PUBLISH_CHECKLIST.md](PUBLISH_CHECKLIST.md) |

---

## Current snapshot

| | |
|---|---|
| Version | v1.1.0 (tool-using agents) |
| Specialist agents | 10 (`agents/registry.py` is canonical) |
| Skill graph | 21 nodes |
| Routing accuracy | 97% full · 99% signal-only (curated eval) |
| Memory | SQLite → auto-promote to FAISS at 800 entries · 628+ vectors · P50 0.38ms · 52× LRU cache |
| UCI health | h_UCI ≈ 80.8 |
| API surface | 100+ endpoints (132 routes) |
| Tests | 719 passing |
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
| v1.0.1 | Lean runtime, onboarding, Vite | ✅ Shipped |
| v1.0.2 | Luxe dashboard + community profile | ✅ Shipped |
| v1.0.3 | Single-file DB + memory portability | ✅ Shipped |
| **v1.0.4** | **Tool-using foundations** (file/sandbox/web tools, thread mgmt, chat affordances) | ✅ Shipped |
| **v1.1.0** | **Tool-using agents** (live web search, in-agent tool loop, Simple/Advanced UI) | ✅ Shipped |
| v1.2 → v2.0 | Providers · workspaces · team memory · agent registry | ⬜ Planned |

See [ROADMAP.md](ROADMAP.md) for the full forward plan and [HISTORY.md](HISTORY.md) for the per-phase record.

---

## Known gaps

| Item | Notes |
|------|-------|
| Plan Graph pre-query | Empty state until first compound query runs. |
| gate_accept_rate ~69% | Critic threshold calibrated for stronger models than phi4-mini. |
| Feedback coverage 0% | All quality signals are proxies until real 👍/👎 ratings accumulate. |

Full bug/limitation list: [ISSUES.md](ISSUES.md).
