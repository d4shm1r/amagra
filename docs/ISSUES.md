# Amagra — Known Issues

**Legend:** 🔴 Active bug · 🟡 Known limitation · ⬜ Deferred

---

## Active Bugs

### 🔴 Profile leak — knowledge_learning mid-response echo
- **Observed:** knowledge_learning occasionally echoes "the user's context: imagine teaching students…" mid-response
- **Cause:** `core/user_profile.py` injected too prominently; LLM treats it as content rather than framing
- **Frequency:** Low — intermittent, not reproducible on demand
- **Fix direction:** Wrap profile injection in a structural separator, or move to a separate `<user_context>` block

### 🔴 Filesystem hallucination
- **Observed:** "Where is my project from yesterday?" returns fictional file paths and directories
- **Cause:** No tool access to the filesystem; phi4-mini generates plausible paths from training data
- **Fix direction:** Add a read-only filesystem tool to `context_tools.py`, wire into relevant agents

### 🔴 Multi-language drift
- **Observed:** Albanian input triggers mixed-language response + profile leak
- **Cause:** phi4-mini has weak multilingual instruction-following; English system prompt conflicts with non-English input
- **Fix direction:** Detect non-English input in coordinator, strip profile injection, or add "respond in the user's language" instruction

### 🔴 Build intent over-classification
- **Observed:** LLM fallback returns `action="build"` for imperative queries that aren't coding tasks
- **Example:** "Repeat months of the year backward as listed" → `build` → python_dev → code reflection → 79s for a 1-line answer
- **Location:** `core_brain.py` near line 264, after `data = json.loads(raw)`
- **Fix direction:** Post-classifier guard: if `action="build"` but query has no code noun (code/script/function/component/class), downgrade to "explain"

---

## Structural Limitations

### 🟡 Full reflection adds ~30–55s per cycle
- By design — runs grounded eval + LLM critique + LLM rewrite (up to 3 iterations)
- Mitigation: reflection triage (Phase 19) reduced full rate from ~58% to ~15–20%
- Direction: 1-iteration cap for non-code tasks; routing time-sensitive queries through Task Queue

### 🟡 All agent weights below 1.0 after eval runs
- After 100-prompt eval, proxy signals (0.75/0.55) push all weights down. Expected.
- Weights recover with real usage sessions.
- Watch: if weights don't recover after 20+ real sessions, proxy signal formula may need adjusting.

### 🟡 terse agent conflict rate ~87%
- Keyword router almost never routes to terse; brain overrides it via `answer_shape == "factual"` path
- Router fix applied in Phase 22. Brain terse rate should improve over time.
- Monitor: `GET /analysis/failures` — terse conflict rate should be declining.

### 🟡 it_networking / ai_ml structural conflict (~45–49%)
- Many queries contain both networking and AI/ML terminology. Domains genuinely overlap.
- Not a bug — agents give useful answers; it's a signal-ambiguity problem.
- Direction: compound routing path for queries scoring ≥ 0.30 in two domains simultaneously.

### 🟡 ai_ml ↔ knowledge_learning output overlap
- Same AI/ML topic routed to both agents produces ~85% identical output
- phi4-mini's responses for general AI/ML questions don't diverge much based on system prompt alone
- Direction: sharpen ai_ml prompt to be code/implementation-focused; let knowledge_learning own conceptual explanations

### 🟡 nomic-embed-text cold-load timeout
- First query after `ai-start` can take 3–8s extra (Ollama loads the nomic model on first embed call)
- Workaround: send a throwaway query ("hi") first, or add a warm-up call to `api.py` startup

### 🟡 Feedback coverage is 0% (all quality signals are proxies)
- No real sessions with 👍/👎 ratings yet. Every performance signal is a proxy.
- Priority: collect real feedback. Even 50–100 ratings will shift the quality signal distribution.

### 🟡 Counterfactual analysis has no statistical validity yet
- 312 traces, 21 real sessions — far below the 400+ needed for meaningful statistical comparisons
- Results are directional only. Full analysis after 400+ real sessions with feedback > 50%.

### 🟡 py_11 routing miss (CSV parsing without "python" keyword)
- "Write a script to parse a large CSV…" → domain=general, conf=0.0 → fallback routing
- Direction: add "csv", "parse file", "script" to the python keyword set

---

## Open Directions

**Routing:**
- False-negative domain detection on short queries — 1-keyword queries are above the routing threshold (conf=0.33) but often ambiguous. Consider minimum 2-keyword threshold for queries < 4 tokens.
- Compound query detection false positives — LLM slow path. Non-compound queries occasionally route to deep pipeline. Needs a benchmark.

**Memory:**
- Episodic inflation at scale — every response writes an episodic record. After 1000+ sessions the episodic type will dominate without a retrieval cap (suggested: max 3 episodic results per query).
- Wrong-domain memory cross-contamination — high-similarity queries sometimes retrieve memories from adjacent domains. The causal graph flags this as `wrong_domain_memories`. Needs a domain-affinity penalty in the retrieval formula.

**Learning:**
- Calibration dominated by eval data — 291 of 312 calibration samples are from the eval run. Real session calibration will take time to dominate.
- Learned router retraining hook missing — trained once on 312 traces. Add auto-retrain hook after every 50 real sessions.

**Architecture:**
- Deep Pipeline v2 — v1 gives each agent the full query with a scoped hint. v2 should use an LLM call to split the query into genuinely independent sub-questions per agent.

---

## Resolved

| Fix | Phase |
|-----|-------|
| Menu hover CSS `!important` vs inline state (F-18) | 32 |
| Introduction redundant in sidebar | 32 |
| Inconsistent tab layout — 16 tabs with own maxWidth (F-19) | 32 |
| AGENTS defined in 4 separate places | 30 |
| No feedback visibility in Progress tab | 31 |
| `OLLAMA_MODEL=llama3` config mismatch (should be phi4-mini) | 27 |
| Phantom agents in `/agents` endpoint | 27 |
| `action=unknown` ~10% of queries | 29 |
| No keyboard shortcuts in UI | 28 |

---

*Update this file when new bugs are observed or issues are resolved.*  
*Run `GET /analysis/failures` for a live failure cluster report.*
