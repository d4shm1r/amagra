# Amagra — Capability Scorecard

Where the system actually stands. Metric-grounded where a real number exists, marked
*(subj.)* where it isn't. Deliberately not inflated — a low score is the next piece of
work, not something to hide.

**Updated:** 2026-08-06 · **Scale:** 1–10 · **Overall ≈ 6.8** · Sorted by score.

| # | Dimension | Score | Evidence | What moves it |
|---|-----------|:-----:|----------|---------------|
| 1 | **Observability** | **9** | Append-only run log; per-run tracer (prompt→routing→generate→critic→finish) with live steps, cost, vote telemetry; decision replay; `/runs` + `/cos/*`. Every decision carries confidence/signal/action/regret. The recorder is now itself recorded: 22 best-effort sites log through `log_internal_failure` + queryable per-component counters instead of `except: pass` ([#196](https://github.com/d4shm1r/amagra/issues/196)). `contradiction.detected` + `reflection.triggered` emit onto the bus; the other three candidate signals are documented as deliberately *not* events ([§10a](FINDINGS.md)). `response_quality` was computed and silently dropped by the LangGraph state merge — declaring it took coverage **0 → 28/30**. The event bus's first live UI consumer: `GET /cos/events/stream` (SSE) + a persistent terminal dock in the app shell, independent of which tab is open — previously the bus only had a poll-snapshot endpoint and no screen. | The flagship. `internal_failure_counts()` has no surface yet — it is queryable, not visible. |
| 2 | Efficiency | **9** | **TTFT 9.7s → 2.1s** (measured cold boot): the first chat used to pay Ollama's full model load (7.7s) before its first token; a background warm-up at lifespan startup removes it. Plus 52× cache speedup · <12 ms routing · local-first · lazy loading · opt-in escalation · release changelog out of the first-paint chunk. | Little left at this layer without a model-side change. |
| 3 | Memory | 8 | FAISS 628+ vectors · 52× LRU cache · dedup + consolidation (cosine ≥0.93) · 6 types · pruning · outcome-weighting. | Recall quality on a held-out set. |
| 4 | Routing | 7 | Keyword 97% dev / **30.8% held-out** (n=91). Semantic fallback (default since 2026-07-07) → **52.7%** held-out, 95% CI [42.6, 62.7]. Gate: 24 rescues vs 3 regressions; `knowledge_learning` sink 81%→7% of misroutes. New: `computational` answer_shape; F-13 closes the short diacritic-free non-English gap. NV-1 probe settles the "routing degrades live" claim as a **category error** — `C_routing` is mean *confidence* (0.73, 0.67 floor), never accuracy. | Held-out ≥70% **and** single-rater labels clearing an inter-rater κ bar. NV-1's offline-vs-live accuracy pair still needs a stable model server. |
| 5 | Reflection | 7 | Triage + grounded eval + LLM critique/rewrite + contradiction gate. Full-reflection rate 58% → 15–20%. **Now measured** (controlled A/B, force none vs full): on the rigorously-graded stress subset **71% → 86%** (10/14 → 12/14, rescued 1 / broke 0); overall **69% → 65%** (n=26), with all 3 "breaks" in marker-graded categories — likely grading fragility, not regression. The easy set is ceiling-bound (28/28 both arms), which is why the stress set exists. | A bigger n and non-heuristic graders for the 3 marker-based categories. The direction is positive; the sample can't carry it yet. |
| 6 | Reasoning | 7 | Self-consistency **+0.19** (0.61→0.80, GSM8K N=100, phi4-mini) — and **now on by default** for scalar-numeric queries, the class it was measured on. Escalation gate: trust 69% @ **0.97**, escalate 31% @ 0.42 — **90% of errors in 31% of volume**. Compute-shaped queries now *execute* in the bwrap sandbox rather than being token-predicted, proven end-to-end ([#186](https://github.com/d4shm1r/amagra/issues/186)). | A *live* frontier run (the 0.95 ceiling is still simulated) and a 2nd benchmark. |
| 7 | Reliability | 7 | **1,276 tests** (was 1,114) · append-only run log · per-decision auditability. v1.8.1 hardening block: provider request timeouts ([#193](https://github.com/d4shm1r/amagra/issues/193)), bounded rate-limit window ([#194](https://github.com/d4shm1r/amagra/issues/194)), SQLite thread-safety audit + `busy_timeout`/WAL fixing intermittent `database is locked` ([#195](https://github.com/d4shm1r/amagra/issues/195)), idempotency keys so a retry runs and charges once ([#197](https://github.com/d4shm1r/amagra/issues/197)), bounded task queue with 429 backpressure + [DR runbook](../ops/DISASTER_RECOVERY.md) ([#198](https://github.com/d4shm1r/amagra/issues/198)). CI **actually runs the UI** now (lint + vitest + build) — the design system was enforceable in principle and enforced by nobody; 9 a11y contract tests. `/tools/run` was found with no offline-LLM handling — a dead Ollama escaped as a bare 500 with no CORS headers, which a browser reports as a misleading "CORS policy" error rather than the real cause; now maps through the same `_map_invoke_error` every other generation endpoint uses. | Closing the held-out routing gap; the neutral-mode metric still disagrees with real logs. |
| 8 | Tool Use | 6 | Bounded tool loop in every agent. Substrate measured (perfect-agent ceiling, 6 end-state tasks): **17% as-shipped → 100%** once jailed writes were exposed behind `AMAGRA_WORKSPACE_WRITE=1`. Browser reach: `fetch_page` + headless-Chromium tools, one SSRF/allowlist/injection policy, 18 offline tests. compute→`run_python` runs through the real sandbox — but with a **scripted** model, so it proves the path, not the picker. `POST /tools/run` / `GET /tools/list` existed since the loop was built but had **zero UI callers** — a Tools tab now makes it reachable, with each call streaming onto the observability terminal (row 1) as it happens. Reachability, not capability: the score is unchanged. | Unchanged and still the gate: the `--live` number where the model drives its own tool calls. The 100% is a *ceiling*, not a result. |
| 9 | Safety | 6 | Threat model S1–S5 reviewed; local-first/private. Web-fetch surface shipped *with* its defenses (SSRF guard, redirect re-validation, allowlist, injection posture). Availability side hardened this cycle (bounded queue, bounded rate-limit state, request timeouts). | S1-residual / S2 / S3 are deferred — availability work doesn't move them. Documented DNS-rebind residual. |
| 10 | Adaptability | 6 | The full decision-economics loop is now **wired**: counterfactual → `strategy_memory` (task_class → strategy stats) → EV selector (`value·P(success) − latency − cost`, Beta-shrunk, abstains on thin evidence) → router override behind `AMAGRA_DECISION_ECON=1`, plus an off-policy held-out evaluator. Outcome-weighted routing weights and reflection→memory bias as before. | **Deliberately not scored up:** the held-out evaluator reports **INSUFFICIENT on current data** rather than a win. This is machinery, not learning — it is gated on real traffic ([O5](OPEN_PROBLEMS.md)), not on code. |
| 11 | Planning | 5 | `deep_pipeline.py` is a **closed loop** — plan→execute→verify→replan, with step outputs threaded forward (was a blind fan-out). Pinned by deterministic fake-runner tests. | End-to-end task completion under a real model. The plumbing is proven; the outcome isn't. *(subj. until measured)* |
| 12 | Autonomy | 4 | Request→response assistant. No long-horizon autonomous execution loop. (A bounded task queue with a serial worker is scheduling, not autonomy.) | A real one. *(subj.)* |

## The shape

A strong **local-first substrate** — observability and efficiency are the standouts, with
memory and routing *engineering* behind them — while the **frontier capabilities** (reasoning,
planning, autonomy) are still early, and measured rather than assumed.

**The load-bearing caveat:** routing is 97% on dev and 30.8% held-out (52.7% with semantic
fallback). Read every "intelligence" score as *engineering maturity, not validated
generalization*, until held-out numbers move and the labels clear an inter-rater bar.

**What this cycle changed, in one line:** the *engineering* rows moved (efficiency,
reliability, observability's own blind spot), reasoning shipped the lever it had already
measured, and the two rows most people would expect to jump — Adaptability and Tool Use —
deliberately did not, because both gained machinery and neither gained a number.

## In flight

- **One blocker, three owed numbers.** The `--live` agentic run ([FINDINGS §10](FINDINGS.md)),
  NV-1's offline-vs-live routing accuracy pair, and Planning's end-to-end completion rate all
  wait on the same thing: a model server that survives sustained pipeline load. This box's
  Ollama OOM-crashes under it. The harnesses run and exit clean on empty data — the wiring is
  not what's missing.
- **Data-gated, not code-gated:** the decision-economics loop (O2) is built end to end and
  reports INSUFFICIENT. It needs real traffic ([O5](OPEN_PROBLEMS.md): feedback coverage 0%,
  21 counterfactual sessions vs 400+ needed), and building the learning on eval traces instead
  would violate [FAILURES F-02/F-03](FAILURES.md).
- **Open bug:** the neutral-mode metric disagrees with the accumulated `logs/` — it flags a
  different agent than the most volatile track. Skips on a clean checkout, so it hides.

## Keeping it honest

Update a row **only when a dimension materially changes** — a new eval number, a shipped
capability, a fixed threat — and move the date and the overall with it. If you can't point
to a metric or a concrete mechanism, mark it *(subj.)* and keep it conservative. Resist
grading on effort or intent; the value of this file is that you can trust it at a glance.

**Detail lives in [FINDINGS.md](FINDINGS.md)** — §3/§3a routing, §5 memory, §6 reflection,
§9 reasoning, §10 agentic, §10a observability. This file is the dashboard, not the report.
For everything *unsettled* — open problems, conjectures, by-design limits — see
[OPEN_PROBLEMS.md](OPEN_PROBLEMS.md); for the orchestration-layer directions and their
maturity, [STRATEGIC_SCORECARD.md](STRATEGIC_SCORECARD.md).
