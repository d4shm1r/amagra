# Amagra — Capability Scorecard

> **A standing, at-a-glance overview of where the system actually stands.**
> Scored the same way the rest of `docs/records/` is: metric-grounded where a real
> number exists, marked *(subjective)* otherwise, and deliberately **not inflated**.
> This is an honest self-assessment, not a marketing sheet — a low score is a
> pointer to the next piece of work, not something to hide.

**Last updated:** 2026-07-08 · **Scale:** 1–10 · **Overall ≈ 6.5/10**

> **In flight (measure-first agentic track):** `agentic_eval.py` measures the
> tool-execution substrate end-to-end; the read-only-catalog blocker under Autonomy/
> Planning/Tool Use is fixed (writes exposed behind an opt-in gate, jail intact). The
> `--live` model-driven path is built and its scoring logic is test-verified, and the
> multi-step executor is now a closed plan→execute→verify→replan loop with observation
> threading (fake-runner tests), and the first browser capability (`fetch_page`) ships
> with SSRF/injection defenses. The one outstanding item that moves rows is the real
> Ollama `--live` run — its completion/validity numbers, not the wiring. See
> [FINDINGS §10](FINDINGS.md).

| Dimension   | Score | Basis |
|-------------|-------|-------|
| Planning    | 5/10  | World-model planner exists (Phase 37); the multi-step executor (`deep_pipeline.py`) is now a **closed loop** — plan→execute→verify→**replan**, with completed-step outputs threaded forward so steps build on each other (was a blind fan-out). Both pinned by deterministic fake-runner tests ([FINDINGS §10](FINDINGS.md)). Not >5: the wiring is proven but end-to-end *task completion* under a real model is still the unmeasured `--live` number — that, not the plumbing, earns the bump *(subjective until measured)* |
| Reasoning   | 6/10  | Self-consistency +0.19 (0.61→0.80 GSM8K, N=100, phi4-mini). **Escalation gate now measured end-to-end** (`escalation_gate_eval.py`, reuses the shipped gate): trust 69% @ 0.97 / escalate 31% @ 0.42, 90% of errors captured in that 31%; simulated gated ≈**0.95** at a 0.90 ceiling while escalating only 31% → near-frontier accuracy at ~⅓ frontier cost. Not 7: ceiling is simulated (no live frontier run), single N=100 sample, one benchmark, SC still opt-in. See [FINDINGS §9](FINDINGS.md) |
| Memory      | 8/10  | FAISS (592+ vectors), 52× LRU cache, dedup/consolidation (cosine ≥0.93), 6 memory types, pruning, outcome-weighting. See [FINDINGS §5](FINDINGS.md) |
| Tool Use    | 6/10  | Specialist-agent routing + bounded tool loop (`tool_loop.py`) wired into every agent via `respond_with_optional_tools`. **Substrate now measured** (`agentic_eval.py`, perfect-agent ceiling on 6 end-state-checked tasks): catalog-as-shipped **17%** (read-only — writes weren't exposed) → **100%** after exposing the already-jailed `write_file`/`make_dir`/`move` behind opt-in `AMAGRA_WORKSPACE_WRITE=1`. Not >6: that's the *perfect-agent* ceiling, not model-driven — the `--live` (phi4-mini drives its own tool calls) number is still owed, and it, not the ceiling, is what earns a bump. **Browser reach added**: `fetch_page` (HTTP GET + readability) plus interactive headless-Chromium tools (`browser_open/read/click/fill`, Playwright, opt-in `AMAGRA_BROWSER=1`, accessibility-tree snapshots) — all sharing one SSRF/allowlist/injection policy, 18 offline tests. Real-browser smoke run still owed (like `--live`). See [FINDINGS §10](FINDINGS.md) |
| Routing     | 7/10  | Keyword fast path: 97% dev-set but **30.8% held-out** (n=91 keyword-only). Semantic fallback (**ON by default since 2026-07-07**, in core_brain + eval) lifts held-out to **52.7%** (Wilson 95% CI [42.6%,62.7%]); ship gate 24 rescues vs 3 regressions, `knowledge_learning` sink 81%→7% of misroutes. <12ms keyword path; on fallthrough +~1 local ONNX embed (~2–5ms CPU, no network, auto-selected out-of-the-box, Ollama fallback), degrades to baseline if no embedder; fully auditable. Generalization materially improved but single-rater labels (κ) still ungate any public number. See [FINDINGS §3/§3a](FINDINGS.md) |
| Reflection  | 7/10  | Reflection triage + grounded eval + LLM critique/rewrite + contradiction gate; full-reflection rate 58%→15–20%. See [FINDINGS §6](FINDINGS.md) |
| Efficiency  | 8/10  | 52× FAISS cache speedup, <12ms routing, local-first, opt-in escalation, lazy loading |
| Autonomy    | 4/10  | Request→response assistant; no long-horizon autonomous execution loop *(subjective)* |
| Reliability | 6/10  | 974+ tests, append-only run log, per-decision auditability — but held-out routing exposes generalization gaps |
| Safety      | 6/10  | Security review complete (threat-model S1–S5); local-first/private; S1-residual/S2/S3 deferred. New agent web-fetch surface ships *with* its defenses (SSRF guard, redirect re-validation, domain allowlist, untrusted-content injection posture — [FINDINGS §10](FINDINGS.md)); net-neutral to the score (documented DNS-rebind residual) pending a review pass |
| Observability | 9/10 | Append-only run log + per-run tracer (prompt→routing→generate→critic→finish, live steps + cost + vote telemetry), decision replay, `/runs` + `/cos/*` endpoints; every decision logged with confidence/signal/action/regret. The flagship strength — "inspect every AI decision." See [FINDINGS §9 conclusion](FINDINGS.md) |
| Adaptability | 6/10  | Outcome-weighted learning loop nudges routing weights, reflection→semantic-memory bias, confidence-calibration track (measure-first). Real but incremental routing adaptation — not robust continual learning, and generalization is the known gap (§3a; training-on-eval overfits, §8) *(partly subjective)* |

**Read of the shape:** a strong **local-first substrate** — **observability is the standout
(9)**, alongside memory, efficiency, and routing *engineering* — with the **frontier capabilities**
(reasoning, planning, autonomy) still early and, importantly, *measured honestly rather
than assumed*. The single most load-bearing caveat is the routing dev-vs-held-out gap
(97% dev vs 30.8% keyword-only held-out; semantic fallback recovers it to 52.7%): treat
any "intelligence" score as engineering maturity, not validated generalization, until
held-out numbers move *and* the single-rater labels clear an inter-rater κ bar.

## How to keep this current

Update a row **only when a dimension materially changes** (a new eval number, a shipped
capability, a fixed threat) — and update the date + overall. Keep scores tied to evidence:
if you can't point to a metric or a concrete mechanism, mark it *(subjective)* and keep it
conservative. The point of this file is a truthful mirror you can trust at a glance, so
resist grading on effort or intent.
