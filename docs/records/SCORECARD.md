# Amagra — Capability Scorecard

Where the system actually stands. Metric-grounded where a real number exists, marked
*(subj.)* where it isn't. Deliberately not inflated — a low score is the next piece of
work, not something to hide.

**Updated:** 2026-07-14 · **Scale:** 1–10 · **Overall ≈ 6.5** · Sorted by score.

| # | Dimension | Score | Evidence | What moves it |
|---|-----------|:-----:|----------|---------------|
| 1 | **Observability** | **9** | Append-only run log; per-run tracer (prompt→routing→generate→critic→finish) with live steps, cost, vote telemetry; decision replay; `/runs` + `/cos/*`. Every decision carries confidence/signal/action/regret. | The flagship. Nothing pending. |
| 2 | Memory | 8 | FAISS 592+ vectors · 52× LRU cache · dedup + consolidation (cosine ≥0.93) · 6 types · pruning · outcome-weighting. | Recall quality on a held-out set. |
| 3 | Efficiency | 8 | 52× cache speedup · <12 ms routing · local-first · lazy loading · opt-in escalation. | — |
| 4 | Routing | 7 | Keyword 97% dev / **30.8% held-out** (n=91). Semantic fallback (default since 2026-07-07) → **52.7%** held-out, 95% CI [42.6, 62.7]. Gate: 24 rescues vs 3 regressions; `knowledge_learning` sink 81%→7% of misroutes. | Held-out ≥70% **and** single-rater labels clearing an inter-rater κ bar. |
| 5 | Reflection | 7 | Triage + grounded eval + LLM critique/rewrite + contradiction gate. Full-reflection rate 58% → 15–20%. | Measured answer-quality delta, not just rate. |
| 6 | Reasoning | 6 | Self-consistency **+0.19** (0.61→0.80, GSM8K N=100, phi4-mini). Escalation gate measured: trust 69% @ **0.97**, escalate 31% @ 0.42 — **90% of errors in 31% of volume**. Simulated gated ≈0.95 at a 0.90 ceiling. | A *live* frontier run (ceiling is simulated), a 2nd benchmark, SC on by default. |
| 7 | Tool Use | 6 | Bounded tool loop in every agent. Substrate measured (perfect-agent ceiling, 6 end-state tasks): **17% as-shipped → 100%** once jailed writes were exposed behind `AMAGRA_WORKSPACE_WRITE=1`. Browser reach: `fetch_page` + headless-Chromium tools, one SSRF/allowlist/injection policy, 18 offline tests. | The `--live` number (model drives its own tool calls). The 100% is a *ceiling*, not a result. |
| 8 | Reliability | 6 | **1,114 tests** · append-only run log · per-decision auditability. Agent layer now covered (was **zero** — `conftest` mocks langchain messages, so nothing could assert on what an agent sent). | Closing the held-out routing gap; the neutral-mode metric currently disagrees with real logs. |
| 9 | Safety | 6 | Threat model S1–S5 reviewed; local-first/private. Web-fetch surface shipped *with* its defenses (SSRF guard, redirect re-validation, allowlist, injection posture). | S1-residual / S2 / S3 are deferred. Documented DNS-rebind residual. |
| 10 | Adaptability | 6 | Outcome-weighted loop nudges routing weights; reflection→semantic-memory bias; confidence-calibration track. | Real but incremental. Not continual learning; generalization is the known gap. *(partly subj.)* |
| 11 | Planning | 5 | `deep_pipeline.py` is a **closed loop** — plan→execute→verify→replan, with step outputs threaded forward (was a blind fan-out). Pinned by deterministic fake-runner tests. | End-to-end task completion under a real model. The plumbing is proven; the outcome isn't. *(subj. until measured)* |
| 12 | Autonomy | 4 | Request→response assistant. No long-horizon autonomous execution loop. | A real one. *(subj.)* |

## The shape

A strong **local-first substrate** — observability is the standout, with memory, efficiency
and routing *engineering* behind it — while the **frontier capabilities** (reasoning,
planning, autonomy) are still early, and measured rather than assumed.

**The load-bearing caveat:** routing is 97% on dev and 30.8% held-out (52.7% with semantic
fallback). Read every "intelligence" score as *engineering maturity, not validated
generalization*, until held-out numbers move and the labels clear an inter-rater bar.

## In flight

- **Owed:** the real Ollama `--live` run. Its completion/validity numbers — not the wiring —
  are what move Planning and Tool Use. ([FINDINGS §10](FINDINGS.md))
- **Open bug:** the neutral-mode metric disagrees with the accumulated `logs/` — it flags a
  different agent than the most volatile track. Skips on a clean checkout, so it hides.

## Keeping it honest

Update a row **only when a dimension materially changes** — a new eval number, a shipped
capability, a fixed threat — and move the date and the overall with it. If you can't point
to a metric or a concrete mechanism, mark it *(subj.)* and keep it conservative. Resist
grading on effort or intent; the value of this file is that you can trust it at a glance.

**Detail lives in [FINDINGS.md](FINDINGS.md)** — §3/§3a routing, §5 memory, §6 reflection,
§9 reasoning, §10 agentic. This file is the dashboard, not the report.
