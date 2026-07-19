# Refactor Analysis — July 2026 (post the three big refactorings)

> Fourth-pass analysis: what the UI kit conversion, the lean-runtime `core/`
> spine, and the delta-algebra dispatch work did **not** reach. Goal stated by
> the owner: *simplicity at maximum* — more consistency, more efficiency,
> less perceived loading time.

## 0. Measured reality first (so we refactor the right thing)

| Suspect | Measured | Verdict |
|---|---|---|
| Backend import (`import api`, warm) | **0.74 s** — 50% is langgraph/langchain pulled eagerly via `routes.tasks → orchestration.coordinator` and `agents → models.llm` | Minor; fixable with lazy imports |
| Polled API endpoints (16 endpoints, live server) | **1–11 ms each** | Not the bottleneck |
| UI eager bundle | **549 KB raw / 178 KB gzip** (React + Chat + Home); Monaco correctly isolated in the lazy PromptEditor chunk (3.7 MB) | Healthy; one flab source (§4) |
| First chat response | Embedding model is warmed at startup; **the generation model (phi4-mini via Ollama) is not** — first real query eats the 3–8 s cold model load | **This is the perceived "loading time"** |

Conclusion: the app is not slow because of bundle size or endpoint cost.
The felt slowness is (a) generation-model cold load on first query, and
(b) the sheer weight of the per-request side-effect chain (§1). The rest of
this document is about *complexity*, which is the thing the owner is actually
sensing.

---

## 1. The #1 target: `/ask` vs `/ask/stream` — two divergent chat pipelines

`routes/core.py` (1,281 lines, 23 endpoints) contains the app's core flow
twice, and the two copies have drifted into a real defect:

- **`/ask`** (~345 lines, `routes/core.py:256-598`) does routing, invocation,
  and then ~12 inline persistence side-quests: run_tracer, COS begin/end,
  context_snapshot, tenant ContextVar, thread load/save, telemetry insert,
  traces insert (with inline `CREATE TABLE`/`ALTER TABLE` migration!), run_log
  append, session insert, auto-retrain hook, decision↔session linking,
  weights delta, contradiction insert. Each opens its own short-lived SQLite
  connection — **on the order of 15 connections across ~9 database files per
  request** — and each is wrapped in `except Exception: pass` (52 swallowed
  exceptions in this one file).
- **`/ask/stream`** (`routes/core.py:1143-1282`) re-implements routing +
  document context a *third* time (the Anthropic branch inside `/ask` is the
  second), and performs **none** of the persistence.
- **The UI only calls `/ask/stream`** (`ui/src/tabs/ChatTab.jsx:331`) and even
  sends `thread_id` — which the handler **ignores**. Net effect today:
  *chats from the primary UI are never saved to threads/sessions, never hit
  telemetry, never feed the learning loop.* The Threads panel reads a table
  that streaming never writes. The entire observability/learning stack the
  project is built around is blind to its main entry point.

**Refactor:** extract one `run_ask()` pipeline — `route → invoke → persist`—
with a single `persist_run(record)` post-step, and have both endpoints (and the
Anthropic branch) call it; streaming only changes the transport, not the
pipeline. This is *exactly* the shape the `core/` onion middleware was built
for (§2). This one change removes ~400 duplicated lines, fixes the lost-chats
defect, and collapses three routing call sites into one.

### 1.1 The behavioral contract (what "unified" means)

Transport is the **only** intended difference between the two endpoints.
Everything else is an invariant of "a chat request happened", and the table is
the spec the integration tests should assert:

| Invariant                     | `/ask` today | `/ask/stream` today | Contract |
|-------------------------------|:---:|:---:|:---:|
| Route selected (one call site)| ✓ | ✓ (re-implemented) | ✓ |
| Document context applied      | ✓ | ✓ (re-implemented) | ✓ |
| Model invoked (gated)         | ✓ | ✓ | ✓ |
| Thread loaded + turn persisted| ✓ | ✗ (ignores `thread_id`) | ✓ |
| Session row written           | ✓ | ✗ | ✓ |
| Telemetry + traces written    | ✓ | ✗ | ✓ |
| Run log appended              | ✓ | ✗ | ✓ |
| Run tracer start/finish       | ✓ | partial (fallback path only) | ✓ |
| COS begin/end request         | ✓ | ✗ | ✓ |
| Tenant scoping (S2)           | ✓ | ✗ | ✓ |
| Streaming transport           | ✗ | ✓ | optional |

The parity test that keeps this from regressing: issue the same message
through both endpoints against a fresh data dir and diff the resulting rows in
sessions/threads/telemetry/run-log — they must be identical modulo timestamps
and the transport field.

## 2. The `core/` spine was built but production bypasses it

The lean-runtime refactor created `core/runtime.py` + `core/contract.py`
(Context/Result, onion middleware, lazy registry, run log) with full test
coverage — but adoption stopped at `core/run_log.py` in `routes/core.py` and
`agents/runner.py`. The coordinator still hand-wires 10 agent imports and
reaches directly into `cognition.*`, `memory_core.*`, `decision.*` inline.

Decide explicitly, then act:
- **Adopt it**: move the §1 persistence chain into middleware layers
  (`trace`, `telemetry`, `session`, `cos`) around a single invoke. The
  observability chain becomes one list of layers instead of 12 inline blocks.
- **Or delete it**: an unadopted spine is pure carrying cost (~1.3 k LOC +
  tests). Half-adopted is the worst state — it's a second idiom.

Recommendation: adopt — §1 gives it its first real job.

## 3. Telemetry write amplification & the 21-database layout

`infrastructure/db.py` registry is a success (only stragglers remain), but the
*physical* layout is still 21 SQLite files, opened/closed per event. Also:

- `routes/core.py:471` hardcodes `logs/decisions.db` with `os.path.join`,
  bypassing the registry — under `AMAGRA_DATA_DIR` (packaged app) or
  `AMAGRA_DB` (single-file mode) the decision↔session link silently no-ops.
- Schema creation is scattered: ~20 modules own inline `CREATE TABLE`, and
  `/ask` runs migration DDL **per request** (`routes/core.py:395-402`).
- ~58 `except Exception: pass` blocks in `routes/` alone hide every
  telemetry failure.

**Refactor:** one `telemetry.record(kind, **fields)` writer module that owns
connections (kept open, WAL already enabled), owns schemas/migrations at
startup, and logs failures once instead of swallowing them. Then flip
`AMAGRA_DB` single-file mode to the default (the registry was explicitly
designed so this is a one-env-var flip). 21 files → 1–3 files; per-request
connects → reused handles.

## 4. UI: the eager bundle carries an 850-line changelog

`ui/src/config/constants.js` (1,282 lines) is ~85% `BUILD_PHASES` (lines
20-875) + `ROADMAP` + `PROMISES` — hand-maintained release-history prose.
Because eager `HomeTab`/`ChatTab` import from it, all of it ships and parses in
the critical first-paint chunk, and it duplicates `docs/ROADMAP.md` as a second
source of version truth that must be manually reconciled (it already drifted
once — see line 589's "Reconciled stale version state").

**Refactor:** split `constants.js` into `agents.js` (small, eager) and
`history.js` (lazy, imported only by the About/Home sections that render it) —
or serve the changelog as static JSON fetched on demand. Longer term, generate
it from git tags/docs instead of hand-maintaining a parallel copy.

Remaining UI debt (small): the `mode` prop is pinned to `"advanced"`
(`App.jsx:71`) but components still branch on it — delete the plumbing;
`TABS_TOMORROW.md` at repo root is a tracked temp note for a redesign that
shipped (v1.7.6) — delete it.

## 5. Import-time side effects and startup cost

- Nine modules run `_init_*()` / `CREATE TABLE` at import (`routes/deps.py`,
  `routes/register.py`, `routes/core.py`, `cognition/run_tracer.py`,
  `decision/weights.py`…). `routes/deps.py` also constructs the COS session at
  import. Move all of this into the FastAPI lifespan (one obvious startup
  path, no work just for importing a module — also makes tests faster/cleaner).
- `routes/tasks.py` imports `orchestration.coordinator` (→ langgraph, ~365 ms)
  at module level but only needs it when a task actually executes; `agents/*`
  import `models.llm` (→ langchain_ollama, ~134 ms) eagerly. Lazy-importing
  these roughly halves backend import time.
- **The real first-query fix:** extend the existing embedding warm-up
  (`api.py:118`) to also fire one dummy generation through the coordinator's
  model so Ollama loads phi4-mini at boot, not on the user's first message.

## 6. Dead weight & hygiene

| Item | Action |
|---|---|
| `orchestration/router.py` (383 LOC, self-declared legacy/diagnostic, off hot path) | Move to `archive/` or delete; `router_interface` docstring already had to debunk confusion it causes |
| `TABS_TOMORROW.md` (tracked) | Delete — work shipped |
| `backups/` (untracked, 2026-05 cull) | Delete locally |
| `tests/test_task_graph_stress.py:29` writes `tests/test_tasks.db` and leaves it (currently dirtying `git status`) | Use `tmp_path`; add `tests/*.db` to `.gitignore` |
| `tasks.db` + `memory/*.db` + `logs/*.db` live inside the repo working tree in dev | Default `AMAGRA_DATA_DIR` to a real data dir (e.g. `~/.local/share/amagra`) in dev too, so the checkout is code-only; folds into §3's single-file flip |
| `session_history` in-memory global (`routes/deps.py`) duplicating the sessions table | Delete; `/history` reads the DB |

## 7. Suggested sequencing (each PR-sized, ordered by leverage)

Each step lists its **done-when** criteria so review is objective, not vibes.

1. **Unify the ask pipeline** (§1) — fixes the lost-persistence defect, deletes
   ~400 lines, creates the seam everything else hangs off. *Do this first.*
   - *Done when:* routing/doc-context exist at exactly one call site; the §1.1
     parity test passes (both endpoints produce identical persisted state);
     a streamed chat appears in the Threads panel; net LOC in
     `routes/core.py` goes down.
2. **Generation-model warm-up** (§5) — one small block in `api.py`; directly
   attacks the felt loading time.
   - *Done when:* time-to-first-token on the first streamed query after boot
     drops from cold-load seconds to warm-path (measure before/after with the
     same prompt; target ≥80% reduction); cold load provably happens during
     lifespan startup (log line), not on the first user message.
3. **`telemetry.record()` writer + registry stragglers + startup schema init**
   (§3, §5) — one idiom for all persistence; unlocks single-file default.
   - *Done when:* zero `CREATE TABLE`/`ALTER TABLE` on the request path; one
     module owns telemetry connections; persistence failures are logged, not
     swallowed (`except: pass` count in routes/ drops from ~58 to ~0 for the
     persistence chain); `grep sqlite3.connect routes/` returns only the
     writer module; `routes/core.py:471` goes through the registry.
4. **constants.js split** (§4) + `mode` plumbing removal + file deletions (§6).
   - *Done when:* eager index chunk shrinks measurably (record the KB delta in
     the PR); `BUILD_PHASES`/`ROADMAP`/`PROMISES` load only with the tabs that
     render them; no component branches on `mode`; `TABS_TOMORROW.md` and
     `orchestration/router.py` are gone from the tree.
5. **Single-file DB default + data-dir default** (§3/§6) — after 3 proves out.
   - *Done when:* a fresh dev checkout stays clean after running the app
     (`git status` empty); existing separate-file data migrates or keeps
     working via the env-var escape hatch; test suite green.
6. **Middleware adoption or spine deletion decision** (§2) — natural follow-on
   to 1+3, when the persistence chain is already one function.
   - *Done when:* exactly one orchestration idiom remains — either the
     persistence chain runs as `core/` middleware layers, or `core/runtime.py`
     + `core/contract.py` are deleted along with their tests.

What this buys: one chat pipeline instead of three, one persistence idiom
instead of ~15 inline blocks, 21 DBs → 1–3, an eager bundle without a
changelog in it, a repo whose working tree is code rather than runtime state,
and a first query that doesn't pay a model cold-load. That is the "simplicity
at maximum" pass: not new architecture — finishing the three refactorings'
unfinished edges and deleting what they orphaned.
