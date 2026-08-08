# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, or otherwise) working in this
repository. Canonical — `CLAUDE.md` imports this file rather than duplicating it.

## Commands

```bash
# Full backend test suite (no Docker needed)
make test                                          # == PYTHONPATH=. python3 -m pytest tests/ -q

# One test file / one test function
PYTHONPATH=. python3 -m pytest tests/test_workspace_tool.py -q
PYTHONPATH=. python3 -m pytest tests/test_workspace_tool.py::test_read_file -q

# Python lint (ruff.toml is the single source of truth; ui/ is excluded — it has its own)
ruff check .

# Full stack (API + UI + Ollama) via Docker
make dev            # foreground   |   make start: background   |   make stop

# Backend only, no Docker (see docs/GUIDE.md for the two-terminal flow)
ai-start             # Ollama + FastAPI on :8000
ai-ui                # React dashboard on :3000 (separate terminal)

# UI (from ui/)
npm run dev          # vite dev server
npm run build         # production build -> ui/build (api.py serves this as a bundled SPA when present)
npm test              # vitest run
npm run lint:ui        # design-system lint (colors-in-tabs, icon registry, nav one-voice, a11y) — not just eslint

# Routing accuracy benchmark / memory-recall release gate
make benchmark          # -> workbench/evaluation/ablation_eval.py
make benchmark-memory   # -> workbench/evaluation/memory_recall_bench.py (deterministic, no Ollama)
```

Node version is pinned in `ui/.nvmrc` (20). CI runs Python 3.11. `ui/package-lock.json`
is gitignored repo-wide (no lockfile to install from) — `npm ci` will fail on a fresh
checkout; use `npm install`.

## Architecture — the parts that span multiple files

**One process, one entrypoint.** `api.py` is the only FastAPI app; it mounts ~19 route
modules from `routes/` via `include_router`, and when `ui/build/` exists it serves that
as a static SPA on the same port — that's how the desktop/AppImage builds ship as a
single process with no Node/Vite at runtime.

**The request path is routed, not a single LLM call.** A query goes through, in order:
`QuerySignal` (keyword + geometric heuristics, ~1ms, no LLM) → either a direct route to a
specialist agent, or to `CoreBrain` (an LLM reasoning fallback) if the signal is
ambiguous → `orchestration/coordinator.py`, a compiled LangGraph `StateGraph` → a
`risk_gate` decision on `reflect_level` (none/light/full) → the specialist agent
(`agents/registry.py`'s `AGENT_MAP`, 10 agents) → `infrastructure/skill_graph.py` (21
nodes) further disambiguates within that agent → FAISS memory retrieval (`memory_core/`)
→ a critic gate / reflection pass (`cognition/reflection.py`) → `step_verifier` emits
pass/fail onto the event bus. Any one of these stages touching a bug usually means
reading at least two of these files together, not one.

**Two coexisting execution idioms — don't assume `core/` is "the" path.** `core/`
(`contract.py`, `runtime.py`) is a Context/Result spine with onion middleware, built as a
lean-runtime layer alongside the LangGraph coordinator above. As of the last refactor
review (`docs/records/REFACTOR_ANALYSIS_2026-07.md`), the decision to either adopt it as
middleware or delete it was explicitly **deferred, not resolved** — `orchestration/coordinator.py`
is the actual execution path today; `core/` is not dead code, but it's also not (yet) load-bearing
for the main request flow.

**Hard invariants (violating these causes silent data corruption, not a crash) —**
see `docs/records/FAILURES.md` for the full list with reasoning:
- Only `training.apply_learning_update()` writes `agent_weights`. Never call
  `decision_weights.adjust()` / `update_ema()` directly outside it.
- Never retrain the learned router on eval/seed data, and never use similarity-based
  session joins as training labels — both silently corrupt the router's calibration.
- Never bypass the memory filter gate (`memory_core/filter.py`) or prune memories with
  `use_count > 0`.

**Tool loop is opt-in and self-gating.** `AMAGRA_AGENT_TOOLS=1` enables the in-agent tool
loop (`tools/tool_loop.py`); `tools/catalog.py` is the single name→callable registry, and
each tool only appears in `available_tools()` when its own `available()` check passes —
so the model is never offered a tool that will 403. Any tool failure falls back to a
plain `llm.invoke`, so a broken tool never costs the user a response. Follow this pattern
for new tools rather than hardcoding availability elsewhere.

**Dev tooling lives outside the runtime root.** `workbench/` (`evaluation/`, `scripts/`,
`brand/`) holds everything unreachable from `api:app` — routing benchmarks, one-off
migration scripts, diagram generators. It was split out 2026-07-14 after tracing the
import graph found 44 unreachable modules sitting in the root looking like application
code. Two files stayed behind because the trace found them actually load-bearing:
`infrastructure/math_metrics.py` and `memory_core/memory_gate.py` (both originally under
`evaluation/`, both still imported by runtime code). If you're tempted to add a new
one-off script or benchmark, it goes in `workbench/`, not the root.

**No hardcoded personal paths in production code.** Every module resolves its own
location from `__file__` (`_ROOT = Path(__file__).parent.parent`-style) — this repo is
public and multi-machine. Several files carry a `# ~/agentic-ai/<name>.py` comment as
the first line (a path-label breadcrumb, not functional code); that's the one tolerated
occurrence of the string. A hardcoded path used to actually resolve a location at
runtime is a bug.

**Version is single-sourced.** `infrastructure/version.py`'s `__version__` is the only
place the backend version is defined; bump it and `ui/src/config/constants.js`'s
`VERSION` together on release (`docs/ops/RELEASING.md`).

**Docs vs. issues.** `docs/` holds records (what happened, what's true, what's open) —
not a task queue. Actionable bugs/features live in GitHub Issues. Start orientation at
`docs/PROJECT_MAP.md` (doesn't duplicate here) and `docs/records/OPEN_PROBLEMS.md` for
what's structurally unsettled.

**Test isolation.** `tests/conftest.py` points `AMAGRA_DATA_DIR` at a per-session temp
directory for the whole test run, so the suite never writes into real `logs/`/`memory/` —
if a test needs to assert against "the" database, use the fixture-provided path, not a
hardcoded one.
