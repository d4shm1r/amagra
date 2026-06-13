# Signal-First Routing: Findings

**Published:** June 7, 2026  
**System:** LangGraph + phi4-mini · RTX 2050 4GB · SQLite + FAISS

---

## Abstract

Key empirical findings from developing a local-first agentic AI over 37 phases. The central finding: replacing LLM-based intent classification with deterministic geometric signal detection increased routing accuracy from 70% to 97% while reducing median classification latency from ~800ms to ~12ms.

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

## 9. Conclusions

Intelligence in a routing system comes from structure, not scale. A well-defined signal space with a clear confidence threshold outperforms an LLM classifier on latency, consistency, and debuggability — while reserving the LLM for genuinely ambiguous or novel queries.

The memory system works well at current scale (628+ entries) but requires active management to prevent episodic inflation. The FAISS LRU cache is the highest-ROI optimization: a simple data structure delivering 52× speedup.

The system's most durable property is auditability: every routing decision is logged with confidence score, domain signal breakdown, action classification, and regret — making failure modes identifiable and fixable without model retraining.

---

*Runtime: FastAPI + LangGraph + React · Evaluated on RTX 2050 4GB*
