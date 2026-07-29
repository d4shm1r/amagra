# Upcoming Releases — the v1.8.x → v1.9.0 staging ladder

**Opened:** 2026-07-23 · **Current shipped:** v1.8.0 · **Working branch:** `feat/v1.9.0-decision-economics`

This document is the **release sequencing plan**, not a scope analysis — that lives in
[V1.9.0_SCOPE.md](V1.9.0_SCOPE.md). The goal: land a large body of in-flight work
**incrementally** across `v1.8.1 → v1.8.2 → v1.8.3` so nothing is lost or blocked behind
one giant merge, then cut a **clean `v1.9.0`** once the decision-economics loop is finished.

## The rule that makes this safe

Slice along **branch boundaries, not file boundaries.**

The current worktree is a *blended* changeset — multiple sessions edited the same files
(`orchestration/coordinator.py`, `api.py`, `decision/log.py`), so it cannot be cut into
sub-releases by `git add -p` without fragile, individually-untested partial commits.
Therefore the blended tree ships as **one** release (v1.8.1). Every subsequent slice
arrives as its **own branch** (the three parallel sessions), which *is* cleanly separable
and testable in isolation before merge.

Each slice must be green (`make test`) **as the committed state**, not just in the working tree.

---

## v1.8.1 — decision-economics groundwork + reliability hardening `[this worktree]`

The current uncommitted tree, committed as one release. Theme: instrumentation and
robustness under the decision-economics program, plus provider/DB hardening.

| Area | Files | Notes |
|---|---|---|
| Decision economics (instrumentation only, **not yet closing O2**) | `decision/experience.py`, `strategy_selector.py`, `decision/log.py`, `tests/test_decision_economics.py`, `workbench/evaluation/decision_econ_readiness.py` | The EV selector + counterfactual recording. The loop is wired but still evidence-starved — see [O2](OPEN_PROBLEMS.md#o2). |
| Reliability hardening | `infrastructure/db.py`, `task_graph.py`, `cognition/run_tracer.py`, `context_snapshot.py`, `decision/log.py` + `tests/test_db_thread_safety.py`, `test_decision_log_conflict.py` | Thread-safety + write-conflict coverage. |
| Rate limit / observability | `api.py`, `.env.example` + `tests/test_rate_limit.py`, `test_event_bus_observability.py` | Per-minute limit + event-bus assertions. |
| Providers | `providers/base.py`, `ollama.py` + `tests/test_providers.py` | Provider robustness. |
| Language | `core/language.py` + `tests/test_language_multilingual.py` | Multilingual handling. |
| Coherence / core-brain | `cognition/coherence.py`, `orchestration/core_brain.py` + guard tests | |
| Review loop (flag-gated, **off by default**) | `orchestration/coordinator.py`, `models/state.py`, `tests/test_review_loop.py` | See "Parked" below. Ships dark under `AMAGRA_REVIEW_LOOP=0`. |
| Docs | `VISION.md`, `FINDINGS.md`, `FAILURES.md`, `PROJECT_MAP.md`, `OPEN_PROBLEMS.md`, this file | |

**Release gate:** full suite green (last run: 1234 passed, 1 skipped). Bump
`infrastructure/version.py` + `ui/src/config/constants.js` to `1.8.1` in lockstep.

## v1.8.2 — `[parallel session branch, TBD]`

Reserved for the next session branch to land. Fill in when it pushes.

## v1.8.3 — `[parallel session branch, TBD]`

Reserved for the third session branch. Fill in when it pushes.

## v1.9.0 — the finalizer (clean minor)

Cut only when the headline is *done*, not staged:

- **O2 closed** — decision-economics loop fed with real counterfactual evidence, not just
  wired. Blocked on feedback coverage ([O5](OPEN_PROBLEMS.md#o5): ~21 sessions vs ~400 needed).
- **Review loop promoted** — `AMAGRA_REVIEW_LOOP` default-on, wired to feed each revision as
  a decision-economics data point; pipeline path brought in (see Parked).
- Consolidated CHANGELOG covering v1.8.1–v1.8.3 rolled into the v1.9.0 notes.

---

## Parked / deferred (carry-forward, do not lose)

- **Review-loop completion** (from the `coordinator.py` refactor, 2026-07-23):
  - Currently single-agent path only; `run_pipeline` deliberately keeps the legacy runner
    (it finalizes sub-agents internally) — the pipeline does **not** get the graph-level loop yet.
  - `max_revisions` default `1` (= legacy regenerate-once). Raising it beyond ~10 risks
    LangGraph's `recursion_limit` (25) — raise the limit if higher fan is wanted.
  - Not yet added to `.env.example`: `AMAGRA_REVIEW_LOOP`, `AMAGRA_MAX_REVISIONS`.
  - Not yet an entry in [OPEN_PROBLEMS.md](OPEN_PROBLEMS.md) as a tracked "topology promotion" item.
  - Fan-out/fan-in and a human-checkpoint (HITL) node remain absent — the two graph-engineering
    gaps identified alongside this work.
- **Human-in-the-loop node** — no `interrupt()` checkpoint in the graph; needed for the
  strict-compliance path.
