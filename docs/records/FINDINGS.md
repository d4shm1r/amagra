# Signal-First Routing: Findings

**Published:** June 7, 2026 · **Updated:** July 7, 2026 (§3a held-out re-baseline)  
**System:** LangGraph + phi4-mini · RTX 2050 4GB · SQLite + FAISS

---

## Abstract

Key empirical findings from developing a local-first agentic AI over 37 phases. The central finding: replacing LLM-based intent classification with deterministic geometric signal detection increased routing accuracy from 70% to 97% while reducing median classification latency from ~800ms to ~12ms. **These are internal development metrics on a self-authored set — on a held-out adversarial set (n=91) the keyword rules alone score ~31%; an on-by-default semantic fallback recovers this to ~53% (see §3a). Treat the headline numbers as indicative of the engineering, not as validated accuracy.**

---

## 1. The Routing Problem

The system routes each query to one of seven specialist agents. Early routing used a keyword matcher with an LLM fallback for ambiguous queries.

The LLM fallback was expensive and inconsistent — same query could classify differently across runs, and ~30% of queries hit the fallback, each adding 600–900ms.

**Core insight:** intent signals are geometric, not linguistic. A Python question and a networking question don't require semantic understanding to distinguish — they occupy different regions of keyword space, consistently.

---

## 2. QuerySignal Architecture

Replaced probabilistic LLM classification with deterministic domain scoring:

1. **Token extraction** — strip stopwords, extract domain-bearing tokens
2. **Domain scoring** — each token votes for domains via a weighted keyword registry
3. **Confidence threshold** — if `domain_conf ≥ 0.33` for exactly one domain, route deterministically
4. **LLM fallback** — only fires for genuinely ambiguous queries (conf < 0.33 or multi-domain tie)

The routing confidence score is not a softmax probability — it's `1 − exp(−0.40 × hits)`, stable and auditable. LLM fallback rate: ~30% → ~3%.

---

## 3. Accuracy Progression

| Change | Accuracy |
|--------|----------|
| Baseline — keyword-only routing | 70% |
| Added QuerySignal confidence scoring | 82% |
| Signal-first path, LLM as fallback only | 92% |
| Terse agent factual-shape path added | 94% |
| Full signal-first routing, ablation verified | **97%** |
| action=unknown eliminated via pattern coverage | ~97% |
| QuerySignal only, no LLM (ablation) | **99%** |

The remaining 3% are genuinely ambiguous queries (multi-domain, compound intent) that require LLM intervention by design.

### 3a. Held-out reality check — why we don't quote a single headline number

The 97–99% figures above are **internal development metrics, not validated accuracy.** The
prompts and the routing rules were authored by the same person, so that benchmark largely
measures "can the rules recognise prompts that resemble the rules?" — evaluation on the
development distribution, not a held-out test. An external eval-methodology review flagged
this directly, and it's correct.

So there is a second, deliberately hostile eval (`evaluation/adversarial_eval.py`): **91 held-out**
prompts (grown from an initial 33; the extension deliberately over-samples the `paraphrase`
category, where the weakness concentrates). All are **keyword-free** — cross-domain ("spin up
containers to run an AI experiment"), keyword-decoys, paraphrases that avoid the trigger words
the rules key on, and terse-traps.

| Eval | Routing accuracy |
|------|------------------|
| Curated ablation (same set used for tuning) | ~99% |
| **Held-out — keyword fast path only** (n=91) | **30.8%**, Wilson 95% CI **[22%, 41%]** |
| **Held-out — + semantic fallback** (on by default) | **52.7%**, Wilson 95% CI **[43%, 63%]** |

The drop on the keyword path is the honest finding, and the *failure pattern* pointed straight
at the fix: **81% of all misroutes collapsed into the single `knowledge_learning` fallback
bucket** — the rules keyword-match, they don't generalise, so any paraphrase with no trigger word
fell through to the catch-all.

**The fix (shipped, on by default 2026-07-07):** `orchestration/semantic_fallback.py` routes the
keyword-free fallthroughs by embedding k-NN to training exemplars instead of dumping them in the
sink. Held-out **30.8% → 52.7% (+22 pts)**, and the sink shrank from **81% → 7%** of misroutes.
The ship gate (`evaluation/semantic_threshold_study.py`) recorded **24 rescues vs 3 regressions**,
and showed no similarity floor helps (right/wrong routes separate only weakly, AUC 0.663) — so the
rescue runs unfloored. It uses a local ONNX embedder (~2–5 ms, no network) when present and falls
back to Ollama, degrading to the 30.8% keyword baseline when neither is available. Production now
sits at the 52.7% figure with an embedder present.

**Caveat — this is the real ceiling, and it applies to 52.7% exactly as much as to 30.8%:** the
labels are single-rater (one author's best call). A better number on single-rater labels is still
not a *validated* one. Before either figure is publishable, the prior question — is the routing
target even well-defined? — needs answering with inter-rater agreement. `evaluation/rater_harness.py`
collects independent blind labels and computes Fleiss' κ; the bar is κ ≳ 0.6, after which the
majority vote becomes consensus gold labels. Until then: internal metrics only.

---

## 4. The action=unknown Problem

Before Phase 29, ~10% of queries returned `action=unknown` and fell through to a slower path. The fix was pattern coverage, not model retraining. Five new pattern groups added:

- **show me / list the / list all** → `lookup`
- **update / modify / refactor / optimize** → `build`
- **troubleshoot / diagnose / why is** → `debug`
- **why would / what does / meaning of** → `explain`
- **how to / help me / best practice** → `plan`

**Lesson:** Pattern gaps matter more than model capability at this scale. The LLM already knew how to handle these queries — the bottleneck was the classifier upstream.

---

## 5. Memory System Findings

### 5.1 Deduplication at Scale

After 312 evaluation runs and real sessions, the memory store accumulated 828 entries with significant semantic overlap. FAISS consolidation (cosine ≥ 0.93) removed 236 near-duplicates — 28.5% reduction — with no measurable quality loss.

Key finding: **eval runs inflate memory**. 291 of 312 traces are eval decisions, not real sessions. Eval queries are structurally similar, generating repetitive episodic memories. A production system should namespace eval memories separately.

### 5.2 Memory Type Distribution

| Type | Notes |
|------|-------|
| episodic | Grows fastest — every response writes one |
| procedural | Step-by-step task traces |
| lesson | Knowledge & Learning outputs |
| code | Python Dev outputs |
| reflection | Only from full-reflection path (~15–20% of queries) |
| failure | Explicit failure annotations; lowest count, highest weight (1.3) |

Episodic memories will dominate retrieval at scale without a cap. Recommended: max 3 episodic results per query injection.

### 5.3 LRU Cache Impact

A 512-slot LRU cache over FAISS query results produced a **52× speedup** for repeated or similar queries in a session. Cache hit rate in real sessions: ~40% (queries within a session are topically related).

---

## 6. Reflection Triage Impact

Full reflection (grounded eval + LLM critique + LLM rewrite, up to 3 iterations) adds 30–55 seconds. Before triage: ~58% of queries triggered full reflection.

Triage logic: only fire full reflection for `action=build` or `action=debug` where `confidence < 0.70`. Lookup, explain, and plan queries skip reflection entirely.

**Result:** Full reflection rate: 58% → 15–20%.

Largest single saving: disabling reflection entirely for the terse agent path (one-line factual answers never need critique).

---

## 7. Model Behavior on Consumer Hardware

**phi4-mini (3.8B) via Ollama on RTX 2050 (4GB VRAM):**

- Median first-token latency: 1.2s cold, 0.4s warm
- Throughput: ~28 tokens/second
- Context window: 16k tokens (practical limit ~8k before coherence degrades)
- Strong: Python, networking, general IT, factual lookup
- Weak: multi-step math, long-form structured output, multilingual

**Observed failure modes:**

1. **Profile leak** — user context injected in system prompt occasionally surfaces verbatim in response
2. **Build over-classification** — LLM fallback returns `action=build` for imperative queries lacking code vocabulary
3. **Multilingual drift** — non-English input + English system prompts → mixed-language responses

These are prompt engineering problems, not phi4-mini bugs. A 70B model would avoid most by following instructions more reliably. At 4GB VRAM, phi4-mini is the right trade-off: fast, private, acceptably accurate.

---

## 8. What Didn't Work

- **LLM for routing classification** — too slow, too inconsistent
- **Memory injection for the terse agent** — memories add context that contradicts "one-line answer"; quality dropped
- **Full reflection for all queries** — time cost collapsed UX; most queries don't need 3 iterations
- **Training on eval data** — 291/312 traces are eval queries. Training on them overfits to eval distribution, not actual usage

---

## 9. Reasoning: Self-Consistency Recovers Multi-Step Math

§7 lists multi-step math as phi4-mini's clearest weakness. **Self-consistency** — sample
the same prompt N times at a non-zero temperature and majority-vote the final answer — is
the cheapest lever against it: inference-time compute, no weight changes.

**Setup:** GSM8K, phi4-mini via Ollama, N=100 problems, 5 samples at temp 0.7, exact-match
on the final number (no LLM judge). `evaluation/reasoning_eval.py`.

| Condition | Accuracy |
|-----------|----------|
| baseline — single greedy sample | 0.61 |
| voted — 5 samples, majority vote | **0.80** |
| **lift** | **+0.19** |

Voting fixed 23 problems and broke 4 (net +19/100).

**The useful finding is the confidence signal, not the lift.** The winning-vote agreement
(winner votes / valid votes) separates right from wrong almost cleanly:

| Winning agreement | Accuracy |
|-------------------|----------|
| ≥ 3/5 (confident) | 67/69 = **0.97** |
| ≤ 2/5 (split)     | 13/31 = **0.42** |

Every error lived in the low-agreement bucket: escalating just the 31 split-vote problems
targets **18 of the 20 total errors — 90% of the mistakes in 31% of the volume.** The
failures split into two populations: (a) the correct answer *was* sampled but lost a close
vote — recoverable by more samples or a bigger model; and (b) the model never produced it
at all — a genuine capability ceiling voting can't fix. So "reasoning" here is really two
problems wearing one label.

**Shipped as an escalation gate, not just an eval.** `cognition/self_consistency.py` exposes
the vote agreement as a confidence score with an escalation decision (`≥ 0.6` trust the local
answer, else escalate); the coordinator wires it behind `AMAGRA_SELF_CONSISTENCY=1` for
numeric-reasoning queries only, and `run_tracer` logs `vote_confidence` per run so the
threshold can be calibrated from production traffic rather than this one sample.

**The gate's system-level payoff, measured.** `evaluation/escalation_gate_eval.py` takes the
saved per-problem votes and applies the *shipped* `escalation_decision` (it reuses the runtime
call, so eval and production can't drift), then simulates routing the 31 escalated problems to
a stronger ceiling model:

| Ceiling accuracy on the escalated subset | Gated accuracy | Escalation rate |
|------------------------------------------|----------------|-----------------|
| 0.80 | 0.918 | 31% |
| 0.90 | **0.949** | 31% |
| 0.95 | 0.965 | 31% |

So the trajectory is **baseline 0.61 → voted 0.80 → gated ≈0.95** (ceiling 0.90) while sending
only **31% of queries** to the expensive model — near-frontier accuracy at roughly a third of
the frontier cost. The trust/escalate accuracies (0.97 / 0.42) and the 31% rate are *measured*;
the gated column is a simulation linear in the ceiling parameter — a live frontier column
(`reasoning_eval.py --ceiling`) is the one number still missing to make it fully end-to-end.

**Same honesty caveat as §3a.** N=100 is a single internal sample, phi4-mini-specific, with
no held-out set, and the 0.6 threshold is fit on these 100 problems. Treat **+0.19** as
directional and the **97% / 42%** split as a promising-but-unvalidated confidence signal
until production votes accrue and the threshold is refit. The cost is real: N× local
generations per reasoning query (~N × 14.5s on this CPU), which is why the gate is opt-in and
shape-gated rather than always-on.

---

## 10. Agentic Execution: The Substrate Ceiling Was the Bottleneck

The scorecard rated Planning (5) and Autonomy (4) *(subjective)* because nothing
measured multi-step, tool-using task completion. `evaluation/agentic_eval.py`
supplies the missing instrument, and it separates a question the scorecard had
conflated: the **substrate ceiling** (given a *perfect* agent that emits exactly
the right tool calls, does the real plumbing — `tools/catalog.py` →
`tools/tool_loop.py` → `tools/workspace.py` — complete the task and leave the
correct end state on disk?) from **model capability** (can phi4-mini drive that
loop, `--live`, pending). The ceiling is the honest floor: if a perfect agent
scores 0, the model can never beat it, and no prompt work matters until the
substrate is fixed. Six deterministic tasks (write a file, build a package,
read-modify-write, search-then-report, rename, read-only), each checked by a
workspace end-state assertion, offline, <1s.

**The finding: the substrate was the bottleneck, not the model.** The tool
catalog exposed only *reads* — so even a flawless agent could complete just the
one read-only task:

| Substrate | Completion | Blocked by |
|-----------|-----------|------------|
| baseline (catalog as shipped) | 1/6 = **17%** | `write_file` / `make_dir` / `move` not exposed |
| after exposing jailed writes  | 6/6 = **100%** | — |

The fix was small and matched the existing posture: the write ops already existed
in `workspace.py`, fully jailed (traversal/symlink/absolute-path → `PathEscape`),
but were reachable only over HTTP. Exposing `write_file`/`make_dir`/`move` through
the catalog behind an opt-in `AMAGRA_WORKSPACE_WRITE=1` gate (mirroring the
sandbox/web opt-ins; reads stay always-on) lifts the ceiling to 100% while keeping
the jail intact through the new seam (`tests/test_catalog_writes.py`). An agent
turn already routes through this catalog via `respond_with_optional_tools`, so with
`AMAGRA_AGENT_TOOLS=1` the specialists can now *act*, not just read.

**Honesty caveat.** 100% is the *perfect-agent* ceiling, not model-driven
completion — it proves the plumbing can no longer be the excuse, not that
phi4-mini drives it well. The `--live` mode (model emits its own tool calls via
the production `models.llm` path, writes auto-enabled per isolated temp workspace,
tool-call validity reported) is **now built and its measurement logic is
verified deterministically** with injected model doubles — a competent double
completes 6/6, a narrate-only double is correctly scored 0 / "no tool calls
emitted" (`tests/test_agentic_eval.py`). What remains is purely a **hardware
run**: point it at an Ollama box (`--live`), and the resulting completion +
validity numbers — not the ceiling — are what can move Autonomy off 4.

**Closing the loop: observation threading + bounded replan.** With the substrate
unblocked, the remaining gap was in the multi-step executor itself
(`cognition/deep_pipeline.py`). It was already verify-gated (retry/abort wired via
`step_verifier.py`), but had two holes that made it a *fan-out*, not a sequential
agent: (1) each step saw only its own description plus the original query — never
the **outputs of the steps it depends on**, so "integrate the components" ran
blind to what "implement the components" produced; and (2) a `replan` verdict was
committed identically to `continue` — the recommendation existed but did nothing.
Both are now closed: completed-step outputs are threaded forward into each step's
task (bounded to the last 3 steps × 500 chars to cap prompt growth), and a
`replan` verdict re-decomposes the *remaining* work once, splicing the new steps
into a mutable execution queue and threading the failure note so they adapt to it.
Replan is budgeted (`AMAGRA_PIPELINE_REPLAN`, default 1; `0` restores the old
commit-and-continue exactly) so it cannot loop. Both behaviours are pinned
deterministically with fake runners, no model needed
(`tests/test_deep_pipeline_executor.py`): a later step provably carries the digest
of an earlier one, a forced `replan` splices and runs a recovery step, and
`budget=0` provably does not. The honest status is unchanged in kind — the
*plumbing* of a closed executor now exists and is tested; whether phi4-mini drives
it to higher end-to-end completion is still the `--live` measurement above, and
that number, not the wiring, is what moves Planning/Autonomy off their scores.

**Browser use, defensively (Phase C, step 1).** The first browser capability is
the smallest one that's useful: `tools/web_fetch.py` does an HTTP GET + readability
extraction (bs4, no browser engine), exposed as the `fetch_page` tool behind an
opt-in `AMAGRA_WEB_FETCH=1` gate. It is built as a *security* surface from the
start, because a fetched page is attacker-controlled input to an agent that can
also write files and run code: (a) an **SSRF guard** resolves the host and refuses
any private/loopback/link-local/reserved IP, and re-validates the final URL after
redirects (so a public host can't 302 the agent onto `127.0.0.1:8000/admin`);
(b) an optional **allowlist** (`AMAGRA_FETCH_ALLOWLIST`) restricts fetches to named
domains and their subdomains; (c) every result is stamped `untrusted=True` with a
`WARNING` that the text is *data, not instructions* — the prompt-injection posture
that instructions found inside page content must never justify a tool call. Nine
offline tests (DNS + HTTP injected) cover extraction, each guard, redirect
re-validation, the marker, and the catalog gate (`tests/test_web_fetch_tool.py`).
One residual is documented not hidden: the resolve-then-refetch gap leaves a
DNS-rebinding window that IP-pinning would close in v2. This adds real agent reach
*and* the injection/SSRF defenses that the heavier Playwright-driven browser tools
(next) will reuse.

**Interactive browsing (Phase C, step 2).** `tools/browser.py` drives a real
headless Chromium (Playwright) an agent can navigate and act on: `browser_open`,
`browser_read`, `browser_click`, `browser_fill`. Two choices make it fit a small
local model and stay safe: (1) **text snapshots, not screenshots** — `browser_read`
returns a flattened accessibility tree (`[role] name` per line, the screen-reader
view), which a 3.8B model can operate on and pixels are not; selectors accept
Playwright's `text=Label` engine so the model clicks by visible label. (2) **One
shared policy with fetch** — navigation reuses `web_fetch._validate` (SSRF guard +
redirect re-validation + `AMAGRA_FETCH_ALLOWLIST`) and every snapshot carries the
same `untrusted=True` + `WARNING`. Playwright is optional and lazily imported: the
module imports without it, the tools appear in the catalog only when
`AMAGRA_BROWSER=1` *and* Playwright is installed, and the functions accept an
injected page so nine tests (`tests/test_browser_tool.py`) cover navigation, the
SSRF/redirect guard, ax-tree flattening, click/fill, the marker, and the gate with
**no browser at all**. Same honesty line as `--live`: the logic is proven offline;
a real-Chromium smoke run needs a machine where `playwright install chromium` has
run, and that end-to-end pass is what would let the browser reach count toward a
score rather than the wiring alone.

---

## 10a. Observability: which runtime moments are events ([#181](https://github.com/d4shm1r/amagra/issues/181))

A dissolved CogOS tab ([#178](https://github.com/d4shm1r/amagra/issues/178)) had
built a "Live Cognitive Events" feed *in the browser* — `synthesizeEvents()` walked
`/decisions`, `/contradictions`, and `/coherence/dynamics` and invented event rows
next to `EventLogPanel`, which renders the real typed stream from `event_bus`. Two
feeds both called "events", one fabricated client-side. The transparency score
(`GET /cos/transparency`) grades a component as **observed** only when it discloses
through the bus, so a hand-reconstructed signal scores as unobserved — the score was
right and the old tab routed around it.

The fix is per-signal: emit the genuine runtime moments, and record why the rest are
deliberately not events.

| Candidate signal | Verdict | Why |
|---|---|---|
| `contradiction.detected` | **Emitted** (`coordinator.py`) | A real moment — the contradiction gate escalated to full reflection. `EventType` was reserved but never fired; now it does. |
| `reflection.triggered` | **Emitted** (`coordinator.py`) | Reflection actually running is a moment worth a timeline row; wired at the single point where the reflection loop runs. |
| `routing.conflict` | **Not an event** | Structurally dead: the keyword-router path was removed, so `final_agent` is always the brain's pick and the decision `conflict` flag is always `False`. There is no second router to disagree. Chasing this flag through the metrics stack surfaced [OPEN_PROBLEMS O7](OPEN_PROBLEMS.md) — the dead `conflict` column was load-bearing in six places; it has since been repurposed at the source as a routing-indecision signal (`confidence < 0.5`), reviving all six, with `C_routing` additionally rebased onto mean confidence. |
| `coherence.shifted` | **Not an event** | A windowed derivative, not a moment. It is a chart, and it already is one (Diagnostics › Coherence). |
| `regret.high` | **Not an event** | Regret is a scalar attached to the decision row, surfaced in Runs › Decisions; a threshold-crossing timeline row would duplicate it without adding a moment. |

Contract pinned by `tests/test_event_bus_observability.py` (imports only `event_bus`,
so it runs without the LangGraph runtime): the two emitted signals reach
`recent_events` — i.e. `GET /cos/events` — and live subscribers receive them.

---

## 11. Conclusions

Intelligence in a routing system comes from structure, not scale. A well-defined signal space with a clear confidence threshold outperforms an LLM classifier on latency, consistency, and debuggability — while reserving the LLM for genuinely ambiguous or novel queries.

The memory system works well at current scale (628+ entries) but requires active management to prevent episodic inflation. The FAISS LRU cache is the highest-ROI optimization: a simple data structure delivering 52× speedup.

The system's most durable property is auditability: every routing decision is logged with confidence score, domain signal breakdown, action classification, and regret — making failure modes identifiable and fixable without model retraining.

---

*Runtime: FastAPI + LangGraph + React · Evaluated on RTX 2050 4GB*
