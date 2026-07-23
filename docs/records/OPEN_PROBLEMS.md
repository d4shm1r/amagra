# Amagra — Open Problems, Conjectures & Known Issues

*A standing register of what is **not** settled: the load-bearing unknowns, the
things built-but-not-wired, the by-design limits, and the conjectures the system
leans on but has not validated. Modeled on the OCAC open-problems discipline —
every entry carries an **epistemic layer** so a hope is never mistaken for a
result.*

**This is a records document, not a task tracker.** Actionable bugs and feature
work live in [GitHub Issues](https://github.com/d4shm1r/amagra/issues) (the live
queue); this file maps the *shape* of what's open and links out. See also
[FAILURES.md](FAILURES.md) (invariants + confirmed failure modes),
[ISSUES.md](ISSUES.md) (by-design limitations), [STRATEGIC_SCORECARD.md](STRATEGIC_SCORECARD.md)
(maturity control surface), [METRICS_ROADMAP.md](METRICS_ROADMAP.md).

**Updated:** 2026-07-23

---

## Epistemic layers

Six, never to be blurred. The first duty of this document is that a `[C]` is
never read as an `[M]`.

| Tag | Meaning | Debate possible? |
|---|---|---|
| **[M]** | **Measured gap** — a limitation with a number. Every `[M]` states whether the number is *validated* (held-out, external) or *internal-only* (self-authored set). | only about the number |
| **[B]** | **Built, not wired** — the code exists and is tested, but is not in the production decision path. | about the wiring, not the mechanism |
| **[D]** | **Needs data** — blocked on real traffic, labels, or a held-out set; not on code. | about the threshold, not the direction |
| **[L]** | **By-design limit** — expected behavior of the substrate (small local model, no tools, single machine). Documented so it is not re-filed as a bug. | no — it's a trade-off, not a defect |
| **[C]** | **Conjecture** — believed true at scale, unproven on *this system's* data. This is where honesty is cheapest to lose. | yes |
| **[R]** | **Research / gated** — deferred behind an explicit named dependency; starting it before the dependency is wasted work. | about the gate |

**The honesty rule this register enforces** (inherited from the OCAC method and
from [FINDINGS.md §3a](FINDINGS.md)): a better number on single-rater / self-authored
data is still *not a validated one*. Headline internal metrics (97–99% routing,
+0.19 reasoning lift, 100% agentic ceiling) are indicative of engineering, not
proof of accuracy — each is tagged accordingly below.

---

## Part I — Open problems (the load-bearing unknowns)

These are the ones where the answer changes the product, not just the polish.

### O1. Is the routing target even well-defined? [M · D]

- **Status.** Internal routing accuracy is 97–99% on the self-authored ablation
  set; on a **held-out adversarial set (n=91)** the keyword fast-path alone scores
  **30.8%** (Wilson CI [22%, 41%]) and the on-by-default semantic fallback recovers
  it to **52.7%** ([43%, 63%]). The fallback fix shipped (`orchestration/semantic_fallback.py`),
  shrinking the `knowledge_learning` sink from 81% → 7% of misroutes.
- **The real problem.** Both numbers rest on **single-rater labels** (one author's
  best call). The prior question — *is there a right answer to route to?* — is
  unanswered. `evaluation/rater_harness.py` collects blind labels and computes
  Fleiss' κ; the bar is **κ ≳ 0.6** before the majority vote becomes gold.
- **Closes when.** Inter-rater κ ≥ 0.6 established, then held-out accuracy re-measured
  against consensus labels. Until then: internal metrics only.

### O2. The decision-theoretic policy layer is wired but unproven [B · D]

- **Status (updated 2026-07-23, v1.9.0 branch).** The engine —
  `decision/strategy_memory.py` (task_class → strategy stats) and
  `decision/strategy_selector.py` (EV = value·P(success) − latency − cost, with
  Beta-shrinkage + abstention) — is now **connected end to end**:
  - the missing feed exists: `decision/experience.py` persists **both arms** of a
    `cognition/counterfactual.py` comparison into strategy memory, and `explore()`
    replays the highest-regret historical decisions to manufacture alternatives;
  - the router **reads it**: `strategy_selector.recommend()` is called on the
    core_brain fast path behind `AMAGRA_DECISION_ECON=1` (off by default), as the
    last override so evidence wins over the rule/learned-router heuristics;
  - a readiness gate exists: `workbench/evaluation/decision_econ_readiness.py`
    reports coverage/divergence and holds held-out accuracy at **PENDING** rather
    than faking a win.
- **What's still open.** The selector still *abstains everywhere on real data*
  because exploration has not yet populated ≥`min_attempts` alternatives per class
  (dry-run finds candidates; a live `--explore` run against an Ollama box is the
  next step). No held-out accuracy number exists yet.
- **Closes when.** A live exploration run makes ≥1 class selectable **and diverge
  from baseline** (the readiness harness's green gate), then the selector **beats
  the signal/rule baseline on a held-out set** with graded outcomes.
- **Depends on:** real graded traffic (O5) + a live exploration pass. The machinery
  gap — the thing this register flagged as the single highest-leverage build — is
  now closed; what remains is data, not code.

### O3. Reasoning: two problems wearing one label [M · D]

- **Status.** Self-consistency (5 samples, majority vote) lifts GSM8K **0.61 → 0.80
  (+0.19)** on phi4-mini; the vote-margin gate (`cognition/self_consistency.py`) sends
  ~31% of volume and captures ~90% of errors (0.97 confident vs 0.42 split). Shipped
  as an opt-in escalation gate.
- **The problem.** Errors split into (a) *the model sampled the right answer but lost
  a close vote* (recoverable) and (b) *the model never produced it* (a genuine
  capability ceiling voting can't fix). N=100, single internal sample, phi4-mini-specific,
  0.6 threshold fit on the same 100 problems. **The gated ≈0.95 column is a simulation
  linear in an assumed ceiling** — no live frontier model has actually answered the
  escalated subset.
- **Closes when.** `reasoning_eval.py --ceiling` runs a real frontier model on the
  31 escalated problems (the one missing end-to-end number), and the 0.6 threshold is
  refit on accrued production votes.

### O4. Agentic autonomy: the ceiling is proven, the drive is not [M · D]

- **Status.** With jailed writes exposed (`AMAGRA_WORKSPACE_WRITE=1`), a *perfect*
  agent completes **6/6** substrate tasks (was 1/6 — the substrate, not the model, was
  the bottleneck). The `--live` harness (model emits its own tool calls) is built and
  verified deterministically with injected doubles.
- **The problem.** 100% is the **perfect-agent ceiling**, not model-driven completion.
  Browser reach (`tools/web_fetch.py`, `tools/browser.py`) is likewise proven *offline
  only* — SSRF/redirect/injection guards tested with no real network or Chromium.
- **Closes when.** A hardware run (`--live` against an Ollama box; `playwright install
  chromium` for the browser smoke) produces real completion + tool-call-validity numbers.
  **Only that number — not the wiring — moves Planning/Autonomy off their scores.**

### O5. Every quality signal is a proxy [M · D]

- **Status.** Feedback coverage is **0%** — no real 👍/👎 sessions yet. Calibration is
  **291/312 eval-derived**; counterfactual analysis has **21 real sessions vs the 400+**
  needed for statistical validity. Post-eval, all agent weights drop below 1.0 (proxy
  artifact, not quality — see [FAILURES.md P-06](FAILURES.md)).
- **Closes when.** 50–100 real ratings shift the quality-signal distribution; 100+ real
  sessions make the learned router (`orchestration/learned_router.py`) meaningful and let
  calibration escape the eval distribution.
- **Invariant guarding this:** never train the learned router on eval/seed traces
  ([FAILURES.md F-02/F-03](FAILURES.md)).

### O7. The dead `conflict` signal and its inert consumers [M · fixed · naming-debt residual]

- **Root cause.** Issue #20 made the core brain the sole routing authority and removed
  the keyword router, so `orchestration/coordinator.py` wrote `conflict = False`
  **unconditionally** — there was no second router to disagree. The `brain_decisions.conflict`
  column was therefore structurally 0 on every row, and six consumers read it. Surfaced
  while resolving [#181](https://github.com/d4shm1r/amagra/issues/181).
- **The fix (two moves).**
  1. **Source revival.** `coordinator.py` now writes `conflict = decision.confidence <
     _INDECISION_CONF` (0.5): the column is *repurposed* from "brain overrode keyword
     router" to **routing indecision** — the brain wasn't confident this query mapped to
     one domain. This re-arms all six consumers at once, on one live signal.
  2. **Coherence rebase.** `C_routing` was additionally decoupled onto `mean routing
     confidence` (a finer, continuous signal than the thresholded rate), with
     `low_confidence_rate` reported alongside.

  | Consumer | Was (`conflict ≡ 0`) | Now |
  |---|---|---|
  | `cognition/coherence.py` — `C_routing` | axis pinned at 1.0, inflating composite C → UCI | rebased onto mean confidence; `conflict_rate` now live |
  | `decision/log.py:conflict_rate()` | always 0 | live low-confidence-routing rate |
  | `routes/maintenance.py` — auto weight-rebuild (`> 0.35`) | could never fire | fires when indecisive routing is sustained |
  | `training/report_generator.py` — `(1 − conflict_rate)·w` | constant free bonus | live term |
  | `training/specialization.py`, `cognition/failure_miner.py` — clusters | always empty | populated by indecisive routes |

- **Verified.** `tests/test_cognition_coherence.py` (C_routing rebase + a regression that it
  no longer reads the dead flag) and `tests/test_decision_log_conflict.py` (`conflict_rate()`
  reflects logged indecision, is not structurally 0). Expect composite C to *drop* from its
  previously-inflated value on real traffic — that is the correction landing.
- **Residual (naming-debt, tracked not silent).** The column/metric is still *named*
  `conflict` and some UI sub-labels still say "brain vs router" / "% routing conflict" — now
  a misnomer for "routing indecision." Rename `conflict → indecision` across the schema,
  metric keys, and UI labels as a follow-up. Also noted en route: `decision/log.conflict_rate()`
  applies `LIMIT ?` to a bare `COUNT(*)` (a no-op), so its "last N" window is actually all-time —
  a pre-existing bug, out of O7's scope but worth a separate fix.

---

## Part II — Conjectures the system leans on [C]

Believed true, unproven on Amagra's own data. Stated as conjectures so a roadmap
bet is never quoted as a finding.

- **C1 — Signal routing generalizes with the semantic net.** *Conjecture:* the
  52.7% held-out figure is a floor that rises with exemplar coverage, not a ceiling of
  the approach. *Falsifier:* adding exemplars fails to move held-out accuracy above the
  keyword baseline once κ-validated labels exist.
- **C2 — Strategy memory will beat the baseline.** *Conjecture (O2's payoff):* once
  exploration fills alternatives per class, EV selection outperforms signal/rule routing
  on held-out tasks. *Grounds:* real ingest already shows a 2× cost gap for the same class
  (python_dev 47s vs pipeline+reflect:light 104s). *Falsifier:* selector wins on cost but
  not on success-adjusted utility.
- **C3 — The self-consistency gate holds in production.** *Conjecture:* the 0.97/0.42
  confident/split split survives on production votes with the threshold refit. *Falsifier:*
  the vote-agreement AUC collapses on real traffic (cf. the semantic floor's weak AUC 0.663).
- **C4 — Pattern gaps dominate model capability at this scale** ([FINDINGS §4](FINDINGS.md)).
  *Conjecture:* most residual routing/action errors are upstream classifier gaps, fixable
  without a bigger model. *Falsifier:* a capability-matched larger model closes errors that
  pattern coverage cannot.

---

## Part III — By-design limitations [L]

Expected behavior of a small, local, private substrate. Documented here so they
are **not re-filed as bugs**. Full list + workarounds in [FAILURES.md Part 2](FAILURES.md)
and [ISSUES.md](ISSUES.md).

| # | Limit | Note / mitigation |
|---|---|---|
| F-10 | Filesystem/file-path questions | No FS tool; model invents plausible paths. |
| F-11 | Real-time / current information | Knowledge cutoff, no default internet. |
| F-12 | Episodic recall of specific files/edits | Semantic memory of *content*, not of your files. |
| F-13 | Multilingual input | Mitigated (`core/language.py`, recall ≥95% on measured set). Short diacritic-free Romance phrases now caught by a foreign-function-word lexicon; residual = two-content-word imperatives with no article (`abre archivo`). |
| F-14 | Exact calculation (2^64, SHA256, date diffs) | LLMs don't compute exactly — see O6 below for the real fix. |
| F-17 | Compound queries >2 domains | **Deep Pipeline v1 fans out to 2 agents max; 3rd domain silently dropped.** Closes with #16. |
| — | Full reflection adds 30–55s/cycle | By design; triage cut the full rate 58% → 15–20%. |
| — | ai_ml ↔ knowledge_learning output overlap (~85%) | phi4-mini doesn't diverge on system prompt alone. |

### O6. Exact/compute queries should route to execution, not generation [R]

- The correct fix for F-14 is not a bigger model — it is **routing "compute/enumerate"
  intents to tool/code execution** rather than asking phi4-mini to produce the number.
  Tracked as **[#186](https://github.com/d4shm1r/amagra/issues/186)**; this is the *only*
  exact fix for vector/arithmetic answers.

### Distributed-systems posture — deliberately deferred, not a gap [L]

Amagra is **local-first**: an Electron/AppImage desktop app (primary), a single-node
Docker-compose deploy (secondary), and a *dormant* hosted tier gated behind the S1/S2
security residuals. That is a deliberate architecture, not an unfinished one. The
in-process `event_bus`, single-writer WAL SQLite, and per-process rate limiter are the
**correct** choices at this scale.

The following are therefore **out of scope until a multi-node hosted tier is deliberately
designed** (and S1/S2 fixed first) — filing any of them as a gap is re-filing a trade-off
as a bug:

> load balancing · reverse proxy · API gateway · Kubernetes/Helm · service discovery ·
> cross-service circuit breakers · message queues · pub/sub · distributed transactions ·
> saga · DLQ · leader election · CAP / eventual consistency · sharding · partitioning ·
> replication / read replicas · distributed locks · autoscaling / horizontal scaling ·
> CDN / edge caching · blue-green / canary / rolling deploys · multi-region · failover ·
> WAF · DDoS · OAuth · JWT rotation · TLS termination · chaos engineering · gRPC · HTTP/2·3

**Soft coupling to watch:** the in-memory rate limiter ([#194](https://github.com/d4shm1r/amagra/issues/194))
and `_minute_window` are per-process and silently break the moment there is more than one
replica — so they anchor "stay single-node until the hosted tier is a deliberate project."
What *is* in scope now — the local-first reliability gaps — is the v1.9.0 sweep in Part IV.

---

## Part IV — Known concrete issues (live queue)

Pointers into the GitHub queue, grouped by theme. **These are actionable — status
lives on the issue, not here.**

- **Routing quality:** re-tune risk-gate thresholds against the post-fix distribution
  ([#174](https://github.com/d4shm1r/amagra/issues/174)); route compute/enumerate to
  execution ([#186](https://github.com/d4shm1r/amagra/issues/186)).
- **Deep pipeline:** LLM sub-question split per agent — the fix for F-17
  ([#16](https://github.com/d4shm1r/amagra/issues/16), gates #110/#111).
- **UX / delivery:** two-speed experience ([#81](https://github.com/d4shm1r/amagra/issues/81)),
  AppImage cross-platform delivery ([#80](https://github.com/d4shm1r/amagra/issues/80)),
  design-system conversion of PolicyPanel/PlanGraphPanel ([#180](https://github.com/d4shm1r/amagra/issues/180)
  — *colour vocabulary migrated to tokens; the larger inline-style → kit-primitive
  conversion, including the SVG plan graph, remains*).
- **Distribution:** launch post + demo GIFs + first-stranger tracking
  ([#116](https://github.com/d4shm1r/amagra/issues/116)/[#115](https://github.com/d4shm1r/amagra/issues/115)/[#117](https://github.com/d4shm1r/amagra/issues/117)).
- **v1.9.0 production-hardening sweep** — local-first reliability gaps, not distributed-systems
  build-out (see the posture note below): provider-call timeout on the main generation path
  ([#193](https://github.com/d4shm1r/amagra/issues/193)), unbounded in-memory rate-limit window
  ([#194](https://github.com/d4shm1r/amagra/issues/194)), thread-safety of `check_same_thread=False`
  SQLite connections ([#195](https://github.com/d4shm1r/amagra/issues/195)), single telemetry writer /
  zero DDL on the request path — promotes Part VI §3/§5 ([#196](https://github.com/d4shm1r/amagra/issues/196)),
  idempotency keys for metered/mutating endpoints ([#197](https://github.com/d4shm1r/amagra/issues/197)),
  local DR runbook + bounded task queue ([#198](https://github.com/d4shm1r/amagra/issues/198)).

---

## Part V — Security residuals [R]

All risky capabilities are **off by default**; these are exposure concerns beyond
localhost or once optional features / a hosted tier are enabled. Full write-up in
the local-only `REVIEW_FINDINGS.md §3`.

| ID | Risk | Status |
|---|---|---|
| **S1** | Prod boot guard keys on `ENV` (defaults `development`) — a server deploy that forgets `ENV` boots open despite `REQUIRE_AUTH=0`. | Regression-tested, **not fixed**; tracked. |
| **S2** | Multi-tenant memory scoping `owner_key_id=? OR IS NULL` → NULL rows world-readable across tenants. | Dormant until hosted. **Must fix before any hosted Pro tier.** |
| **S3** | `AMAGRA_AGENT_TOOLS=1` + web search = prompt-injection exfil path (untrusted content steers a model that can also write/run). | Mitigated by off-by-default + `untrusted` marker; **deeper taint/confirm fix deferred.** |
| — | `web_fetch` resolve-then-refetch leaves a **DNS-rebinding window**. | Documented; IP-pinning closes it in v2. |

*(S4 sandbox boundary and S5 timing oracle are **fixed** — bubblewrap jail + `compare_digest`; recorded in HISTORY, not open.)*

---

## Part VI — Architecture / refactor debt [R]

The July-2026 fourth-pass analysis ([REFACTOR_ANALYSIS_2026-07.md](REFACTOR_ANALYSIS_2026-07.md)).
**Steps 1–2 shipped as v1.8.0** (unified ask pipeline — the lost-chats persistence
defect is *fixed*; generation-model warm-up, TTFT 9.7s → 2.1s). **Steps 3–6 remain:**

- **§3/§5 — `telemetry.record()` writer.** ~58 `except: pass` blocks swallow telemetry
  failures; ~20 modules own inline `CREATE TABLE`; `/ask` ran migration DDL per request;
  `routes/core.py:471` hardcodes `logs/decisions.db`, bypassing the registry (silently
  no-ops under `AMAGRA_DATA_DIR`). *Done when:* zero DDL on the request path, one writer
  owns connections, failures logged not swallowed.
- **§3/§6 — 21 SQLite files → 1–3.** Flip `AMAGRA_DB` single-file mode to default; default
  the data dir out of the working tree (a dev checkout should stay `git`-clean after running).
- **§4/§6 — Dead weight.** Split `constants.js` (85% changelog ships in the first-paint
  chunk + duplicates ROADMAP as a second version-truth); delete `orchestration/router.py`
  (self-declared legacy), `TABS_TOMORROW.md`, the `mode` plumbing, the `session_history`
  in-memory global.
- **§2 — Spine decision.** `core/runtime.py` + `core/contract.py` (~1.3k LOC) are built,
  tested, and **half-adopted** — the worst state. *Decide explicitly:* adopt (persistence
  chain becomes middleware layers) or delete. Recommendation: adopt — §1 gives it its first
  real job.

---

## Part VII — OCAC math track: diagnostic-before-controller [R]

The [OCAC stability bridge](../design/OCAC_STABILITY_BRIDGE.md) imports proved
contraction/recursion results as runtime metrics. The discipline is deliberate:
**land each result as a pure, self-tested function first; wire into a controller
only when there is real signal to act on.** Open items:

- **#110 — graded reflection-depth dial.** `fractional_reflection_depth` exists;
  **the design question is now unblocked** by OCAC2's P6/D1 result: there is *no*
  unique interpolation selected by smoothness (the canonical half-iterate isn't even
  C²), so what `reflect_level = 0.5` executes is a **product decision, not a forced
  one** — pick by criteria and calibrate on live traffic.
- **#111 — `certified_rate` / `gevrey_rate_estimate` depth budgeting.** Gated on **#16**
  creating real recursion depth — today's paths are ≤1 retry, so there is no series to
  measure. **New OCAC2 caveat to honor when wiring:** `no_geometric_supersolution` proves
  a naive geometric-rate depth budget is *provably optimistic* — promote the `.rising`
  flag (the A3-but-not-A3′ signature) from advisory to a **gate**.
- **#74 — neutral-mode signed drift** (P3): the distinctive publishable metric —
  identify the slowest-contracting agent mode (smallest α, K→1) and report its *signed*
  drift. [METRICS_ROADMAP Phase 5](METRICS_ROADMAP.md).
- **Metrics roadmap Phases 1–6** — signed curvature indicator (undo the `abs()` sign-loss),
  Lyapunov `drift_status_v2` (basin, not threshold), per-metric provenance tags, cubic
  saturation basin. All pure-function-first.
- **Stale-anchor note:** the bridge doc's §6 cites `MajorantSeries.lean`/`GevreyComposition.lean`
  as the frontier; OCAC2 has moved it to `GevreyKernel.lean` / `MajorantComparison.lean` /
  `NoGeometricSupersolution.lean` / `PeriodicRigidity.lean`. A **§7 sync** is owed.

---

## Part VIII — Recently resolved

Closed items are recorded here (not silently deleted) so a reader sees what moved
and where the evidence lives. An entry earns a place here only against its
"done when"; the detail lives in the linked finding/test, not in this register.

| Item | Resolution | Evidence |
|---|---|---|
| **F-13** — short diacritic-free Latin phrases missed by language detection | Added a curated foreign-function-word lexicon (SQ/ES/DE/FR/PT/IT) consulted only after the English-stopword gate, so `instala el paquete` / `mostra il file` now flag without new English false positives. | `core/language.py`; `tests/test_language_multilingual.py` (5 pass; recall ≥95%, zero English FP). Residual documented (two-content-word imperatives). |
| **#181** — routing conflicts/contradictions synthesized in the UI | Per-signal decision: `contradiction.detected` + `reflection.triggered` now emit from the runtime onto the event bus; `routing.conflict` / `coherence.shifted` / `regret.high` recorded as deliberately-not-events. | [FINDINGS §10a](FINDINGS.md); `orchestration/coordinator.py`; `tests/test_event_bus_observability.py` (4 pass). |
| **#180** *(partial)* — PolicyPanel/PlanGraphPanel design-system conversion | Colour vocabulary migrated off raw hex onto the semantic tokens (`T`/`SEM`); the inline-style → kit-primitive conversion (incl. the SVG plan graph) remains open in Part IV. | `ui/src/components/panels/PlanGraphPanel.jsx`; `ui/scripts/lint-ui.mjs` ratchet still green. |

---

## How this document stays honest

1. **Every claim carries a layer.** No `[C]` is promoted to `[M]` without a validated
   number; no `[B]` is called done without a wired-and-beats-baseline check.
2. **Numbers state their provenance** — validated vs internal-only, `measured` vs `proxy`
   vs `assumed_constant` (the same taxonomy the metrics stack enforces).
3. **This file records; the queue executes.** When an `[R]`/`[B]` becomes actionable,
   file it as a GitHub issue and link it here — do not grow a second task list.
4. **An entry closes only against its "done when."** Directional evidence updates the
   status line; it does not close the problem.

*New open problem or conjecture? Add it here with a layer tag. New actionable bug?
→ [open an issue](https://github.com/d4shm1r/amagra/issues/new) and link it in Part IV.*
