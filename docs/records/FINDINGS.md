# Signal-First Routing: Findings

**Published:** June 7, 2026 · **Updated:** July 6, 2026 (§9 reasoning)  
**System:** LangGraph + phi4-mini · RTX 2050 4GB · SQLite + FAISS

---

## Abstract

Key empirical findings from developing a local-first agentic AI over 37 phases. The central finding: replacing LLM-based intent classification with deterministic geometric signal detection increased routing accuracy from 70% to 97% while reducing median classification latency from ~800ms to ~12ms. **These are internal development metrics on a self-authored set — on a held-out adversarial set the same router scores ~42% (see §3a). Treat the headline numbers as indicative of the engineering, not as validated accuracy.**

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

So there is a second, deliberately hostile eval (`evaluation/adversarial_eval.py`): 33 held-out
prompts written to be hard and **keyword-free** — cross-domain ("spin up containers to run an
AI experiment"), keyword-decoys, and paraphrases that avoid the trigger words the rules key on.

| Eval | Signal-only routing accuracy |
|------|------------------------------|
| Curated ablation (same set used for tuning) | ~99% |
| **Held-out adversarial** (33 prompts) | **42.4%**, Wilson 95% CI **[27%, 59%]** |

The drop is the honest finding, and the *failure pattern* is the useful part: paraphrases
collapse to the fallback agent (`knowledge_learning`) — i.e. the rules keyword-match, they
don't generalise — and cross-domain prompts pick a plausible-but-not-primary specialist.
Production sits between these two numbers, closer to the floor than the ceiling.

**Caveat on the 42% itself:** those labels are single-rater (one author's best call). Before
*either* number is publishable, the prior question — is the routing target even well-defined? —
needs answering with inter-rater agreement. `evaluation/rater_harness.py` collects independent
blind labels and computes Fleiss' κ; the bar is κ ≳ 0.6, after which the majority vote becomes
consensus gold labels. Until then: internal metrics only.

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

**Same honesty caveat as §3a.** N=100 is a single internal sample, phi4-mini-specific, with
no held-out set, and the 0.6 threshold is fit on these 100 problems. Treat **+0.19** as
directional and the **97% / 42%** split as a promising-but-unvalidated confidence signal
until production votes accrue and the threshold is refit. The cost is real: N× local
generations per reasoning query (~N × 14.5s on this CPU), which is why the gate is opt-in and
shape-gated rather than always-on.

---

## 10. Conclusions

Intelligence in a routing system comes from structure, not scale. A well-defined signal space with a clear confidence threshold outperforms an LLM classifier on latency, consistency, and debuggability — while reserving the LLM for genuinely ambiguous or novel queries.

The memory system works well at current scale (628+ entries) but requires active management to prevent episodic inflation. The FAISS LRU cache is the highest-ROI optimization: a simple data structure delivering 52× speedup.

The system's most durable property is auditability: every routing decision is logged with confidence score, domain signal breakdown, action classification, and regret — making failure modes identifiable and fixable without model retraining.

---

*Runtime: FastAPI + LangGraph + React · Evaluated on RTX 2050 4GB*
