# Amagra — Known Limitations

> **Active bugs and feature work now live in [GitHub Issues](https://github.com/d4shm1r/amagra/issues).**
> This file is only the record of **by-design / monitor-only** behaviors — things that
> are expected, not tasks. File anything actionable as an issue instead.

**Legend:** 🟡 Known limitation (by design) · 👀 Monitor

---

## Structural Limitations

### 🟡 Full reflection adds ~30–55s per cycle
- By design — runs grounded eval + LLM critique + LLM rewrite (up to 3 iterations).
- Mitigation: reflection triage (Phase 19) reduced the full rate from ~58% to ~15–20%.

### 🟡 All agent weights below 1.0 after eval runs
- After a 100-prompt eval, proxy signals (0.75/0.55) push all weights down. Expected.
- 👀 If weights don't recover after 20+ real sessions, the proxy signal formula may need adjusting.

### 🟡 terse agent conflict rate ~87%
- The keyword router almost never routes to terse; the brain overrides it via the `answer_shape == "factual"` path. Router fix applied in Phase 22.
- 👀 `GET /analysis/failures` — terse conflict rate should be declining.

### 🟡 it_networking / ai_ml structural conflict (~45–49%)
- Many queries contain both networking and AI/ML terminology. The domains genuinely overlap — agents still give useful answers; it's a signal-ambiguity problem, not a bug.

### 🟡 ai_ml ↔ knowledge_learning output overlap
- The same AI/ML topic routed to both agents produces ~85% identical output; phi4-mini's responses don't diverge much on system prompt alone.

### 🟡 Feedback coverage is 0% (all quality signals are proxies)
- No real sessions with 👍/👎 ratings yet. Every performance signal is a proxy.
- 👀 Even 50–100 real ratings will shift the quality-signal distribution.

### 🟡 Counterfactual analysis has no statistical validity yet
- 312 traces, 21 real sessions — far below the 400+ needed for meaningful comparisons. Results are directional only.

### 🟡 Calibration dominated by eval data
- 291 of 312 calibration samples are from the eval run. Real-session calibration will take time to dominate.

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

*New bug or feature idea? → [open an issue](https://github.com/d4shm1r/amagra/issues/new).*
*Run `GET /analysis/failures` for a live failure-cluster report.*
