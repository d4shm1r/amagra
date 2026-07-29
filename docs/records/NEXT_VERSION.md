# Next Version — Planning & Carry-Over

**Updated:** 2026-07-23

A rolling register of what is **queued but not yet shipped**, so a release can be
cut without losing the plan. This is the "what's next" companion to the two
scope-specific docs:

- **[V1.9.0_SCOPE.md](V1.9.0_SCOPE.md)** — the v1.9.0 *learning-loop* track
  (close O2: counterfactual → strategy memory → EV selector → router). That is
  the headline feature work.
- **[OPEN_PROBLEMS.md](OPEN_PROBLEMS.md)** — the epistemic register of everything
  unsettled. Items here link back to it; this doc does not restate it.

**This file records intent; [GitHub Issues](https://github.com/d4shm1r/amagra/issues)
own status.** When an item ships, move it to the "Shipped" section with its
release tag and delete it from the queue.

---

## Shipped — v1.8.1 (production-hardening patch)

Backward-compatible reliability fixes. No API or schema change; safe patch bump.

| Issue | What shipped | Where |
|---|---|---|
| [#193](https://github.com/d4shm1r/amagra/issues/193) | Provider generation now has a request timeout — a hung/overloaded Ollama fails a request in ≤ `OLLAMA_TIMEOUT` (default 120s) with a typed `ProviderTimeoutError` instead of stalling `/ask` forever. Covers sync `generate` (HTTP client timeout) + async `agenerate` (asyncio hard ceiling) + `stream` (per-chunk read timeout). | `providers/ollama.py`, `providers/base.py` |
| [#194](https://github.com/d4shm1r/amagra/issues/194) | The in-memory per-minute rate-limit window no longer grows unbounded — stale windows are evicted at most once/60s, bounding the dict to the active working set. | `api.py` (`_check_minute_limit`) |
| [#195](https://github.com/d4shm1r/amagra/issues/195) | SQLite thread-safety audit: all 11 `check_same_thread=False` sites confirmed fresh-per-call (never shared across threads). Central `db.tune()` now applies an explicit `busy_timeout` (10s) + WAL, fixing an intermittent `database is locked` under concurrent writers. AST guard prevents module-level cached connections. | `infrastructure/db.py` + 7 modules |

New tests: `tests/test_rate_limit.py`, `tests/test_db_thread_safety.py`, timeout
cases in `tests/test_providers.py`. Suite: **1226 passing**.

**Also in this release — decision-economics machinery (feature, flag-gated, unproven).**
The v1.9.0 learning loop's *machinery* landed early; the design + honest caveats are in
[V1.9.0_SCOPE.md](V1.9.0_SCOPE.md). Off by default (`AMAGRA_DECISION_ECON=1`), so it is a
safe patch inclusion — no behavior change unless the flag is set.
- `decision/experience.py` — counterfactual → strategy-memory feed + `explore()` driver
- `decision/strategy_selector.py::recommend()` / `parse_strategy()` — router-facing EV pick
- `orchestration/coordinator.py` — **live** per-request strategy recording (was batch-only);
  `orchestration/core_brain.py` reads the selector as the last override
- `workbench/evaluation/decision_econ_readiness.py` — honesty gate (held-out accuracy = PENDING)
- **Bug fix (not flag-gated):** `core_brain.VALID_AGENTS` registry drift — `web_dev`/`devops`/
  `data_analyst`/`writer` were invisible to the LLM-classifier, learned-router, and EV paths;
  now registry-sourced + guarded by `test_valid_agents_matches_registry_no_drift`.

The **remaining** decision-economics work (live exploration run → green readiness gate →
held-out proof that closes O2) is queued below and detailed in V1.9.0_SCOPE.md.

**Also shipped this sweep (other tracks).**
- **F-13** — foreign-function-word lexicon closes the short diacritic-free Romance phrase
  gap (`core/language.py`; `tests/test_language_multilingual.py`).
- **#181** — `contradiction.detected` + `reflection.triggered` now emit onto the event bus
  (`orchestration/coordinator.py`; `tests/test_event_bus_observability.py`); the other three
  candidate signals documented as deliberately-not-events ([FINDINGS §10a](FINDINGS.md)).
- **O7** — the dead `conflict` signal revived at source (`conflict = confidence < 0.5`,
  routing indecision), re-arming all six consumers; `C_routing` rebased onto mean routing
  confidence (`tests/test_cognition_coherence.py`, `tests/test_decision_log_conflict.py`).
- **#180 (partial)** — `PlanGraphPanel` colours migrated off raw hex onto semantic tokens.
- **VISION rewrite** — `docs/product/VISION.md` reframed to the "OS for Intelligence" framing
  (docs-only, backward-compatible).

> **Release mechanics reminder:** bump `infrastructure/version.py` and
> `ui/src/config/constants.js` (`VERSION`) in lockstep to `1.8.1`.

---

## Queued — v1.9.0 reliability / production-hardening track

The remaining half of the v1.8.1 sweep. These are **local-first reliability**
items (not distributed-systems build-out — see the
[distributed-systems posture note](OPEN_PROBLEMS.md#part-iii--by-design-limitations-l)).
They ride alongside the learning-loop work in [V1.9.0_SCOPE.md](V1.9.0_SCOPE.md).

| Issue | Item | Size | Notes |
|---|---|---|---|
| [#196](https://github.com/d4shm1r/amagra/issues/196) | One telemetry writer; **zero DDL on the request path** | **Large** | ~58 `except: pass` swallow telemetry failures; ~20 modules own inline `CREATE TABLE`; `routes/core.py:471` hardcodes `logs/decisions.db` (bypasses the registry under `AMAGRA_DATA_DIR`). Promotes [OPEN_PROBLEMS Part VI §3/§5](OPEN_PROBLEMS.md#part-vi--architecture--refactor-debt-r). The new central `db.tune()`/registry is the seam to build on. |
| [#197](https://github.com/d4shm1r/amagra/issues/197) | **Idempotency keys** for metered/mutating endpoints (`/ask`, `/tasks/create`) | Medium | A client retry currently re-runs work and re-increments the usage counter (double-charge on the dormant paid tier). Accept `Idempotency-Key`, dedupe within a TTL window. |
| [#198](https://github.com/d4shm1r/amagra/issues/198) | **Local DR runbook** + bounded task queue | Small (docs-led) | `backups/` exists with no restore path; `task_worker` drains `pending` with no depth cap. DR story = "back up `AMAGRA_DATA_DIR`" — write it down; add a queue-depth guard. |

**Recommended order:** #198 (cheap, docs-led) → #197 (self-contained) →
#196 (the big refactor; do last, on top of a green tree).

---

## Queued — v1.8.2 & follow-ups (conflict / UI / language tracks)

Deferred out of the v1.8.1 sweep by the sessions that shipped F-13 / #181 / O7 / #180.
Each has a concrete next step and a file to touch; file as issues when actionable.

| Item | Next step | Files | Target |
|---|---|---|---|
| **O7 naming-debt** | Rename `conflict → indecision` across the `brain_decisions` column, metric keys, and UI sub-labels (some still say "brain vs router", now a misnomer). Coordinate with live UI-branch work. | `decision/log.py`, `cognition/coherence.py`, `orchestration/coordinator.py`, ~6 UI panels | v1.8.2 |
| **`conflict_rate()` window bug** | `decision/log.py:conflict_rate()` applies `LIMIT ?` to a bare `COUNT(*)` (a no-op) → its "last N" is silently all-time. Rewrite as a subquery / `WHERE id > …`. Pre-existing, surfaced during O7. | `decision/log.py` | v1.8.2 |
| **#180 full conversion** | Finish `PolicyPanel` / `PlanGraphPanel`: remove inline `style={{}}` + the `@/styles/theme` import, compose kit primitives, then delete from the `DEBT` set in `ui/scripts/lint-ui.mjs`. Needs an SVG kit primitive for the plan graph. | `ui/src/components/panels/*`, `ui/src/components/ui/*` | v1.9.x |
| **F-13 residual** | Two-content-word imperatives with no article/lexicon verb (`abre archivo`, `leggi documento`) still slip through (see `KNOWN_MISSES`). Needs a verb-stem heuristic without inflating English false positives. | `core/language.py` | later |

---

## Carry-over from the refactor register (not yet issues)

Tracked in [OPEN_PROBLEMS Part VI](OPEN_PROBLEMS.md#part-vi--architecture--refactor-debt-r);
file as issues when actionable, don't grow a second list here:

- **21 SQLite files → 1–3.** Flip `AMAGRA_DB` single-file mode to default; default
  the data dir out of the working tree so a dev checkout stays git-clean after a run.
- **Spine decision** (`core/runtime.py` + `core/contract.py`, half-adopted): adopt
  or delete. #196's single-writer work gives it its first real job.
- **Dead weight:** split `constants.js` (changelog ships in first-paint chunk),
  delete `orchestration/router.py` (legacy), `TABS_TOMORROW.md`, the `mode` plumbing,
  the `session_history` in-memory global.
- **`core_brain.DOMAIN_SIGNALS`** is a 5-agent duplicate of `router.py`'s 10-agent
  patterns — have `core_brain` consume `router.py`'s patterns (one source of truth).
  See [V1.9.0_SCOPE.md](V1.9.0_SCOPE.md) "Deferred finding".

---

## Carry-over from the vision / measurement pass (2026-07-23)

Surfaced while rewriting [`../product/VISION.md`](../product/VISION.md) to the "OS for
Intelligence" framing and **re-measuring its scorecard live on v1.8.0** (single local `phi4-mini`,
n=12 `/ask`, SQLite memory). The VISION rewrite itself ships in this sweep (docs-only,
backward-compatible); these are the follow-ups it exposed. File as issues when actionable.

- **Live routing-coherence gap (NEW, notable).** On live traffic `c_routing` measured **0.73**,
  while the offline ablation (`ablation_eval.py`, 138 prompts) scores **~1.0** signal-only. Offline
  asks *"right agent on clean prompts?"*; live asks *"did routing stay self-consistent across a real
  session?"* — the harder number. **Caveat:** n=12, single model, fresh instance — could be noise
  or model-specific. **Next step is to reproduce at N≥100 across models**, not to "fix" it; if the
  gap holds, graduate to [`OPEN_PROBLEMS.md`](OPEN_PROBLEMS.md) as a routing open problem and record
  the number in [`FINDINGS.md`](FINDINGS.md).
- **Held-out routing generalization set.** The refreshed 100% signal-only figure is
  *in-distribution* (the `auto_train` set the router is tuned against) — it proves no regressions,
  not generalization. Build a held-out set of unseen phrasings; it doubles as the
  [`V1.9.0_SCOPE.md`](V1.9.0_SCOPE.md) DoD #4 "beats baseline on a held-out set" gate.
- **Scorecard re-measure at scale.** Retire the n=12 / single-model / SQLite caveat: re-run UCI /
  C(t) / verifier on a **populated, multi-model** instance (Anthropic + Ollama, ≥100 decisions) for
  benchmark-grade numbers. Pairs with the [O5](OPEN_PROBLEMS.md#o5) real-traffic push.
- **VISION ↔ scope cross-link.** The rewrite's *Evolution* principle names its own honest gap
  (`lrn_routing_accuracy` is an assumed constant, not live-measured) — that gap **is** what
  [`V1.9.0_SCOPE.md`](V1.9.0_SCOPE.md) closes (O2). Add a pointer each way.

---

## Explicitly deferred (with reason)

- **Distributed-systems concerns** (K8s, sharding, saga, WAF, OAuth, multi-region, …)
  — by-design deferred until a hosted multi-node tier is a deliberate project, and
  gated behind the S1/S2 security residuals. Recorded in the
  [posture note](OPEN_PROBLEMS.md#part-iii--by-design-limitations-l) so they are not
  re-filed as gaps.
- **Learning upgrades** (self-optimization daemon, learned router at scale, experience
  replay) — **data-gated on [O5](OPEN_PROBLEMS.md#o5)**, not code-gated. Building them
  before real feedback trains on eval traces (violates FAILURES F-02/F-03).
