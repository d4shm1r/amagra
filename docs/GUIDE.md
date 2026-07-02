# Amagra — User Guide

**URL:** http://localhost:3000  
**API:** http://localhost:8000

---

## Quick Start

```bash
ai-start    # starts Ollama + FastAPI backend on port 8000
ai-ui       # starts React dashboard on port 3000 (separate terminal)
ai-stop     # stops everything
ai-logs     # tails the backend log
```

Manual start (if aliases unavailable):
```bash
source ~/.venvs/langgraph-env/bin/activate
cd ~/agentic-ai && uvicorn api:app --host 0.0.0.0 --port 8000
cd ~/agentic-ai/ui && npm start
```

Want AMAGRA in your app menu as a native window? One-time setup:
```bash
bash desktop/install-desktop-entry.sh   # installs the launcher entry + icon for this checkout
```

---

## The Mental Model

The dashboard has three modes:

1. **Ask** — Chat or Task Queue. You're working. The system answers.
2. **Watch** — Overview, Brain, Traces. You're checking what happened.
3. **Understand** — Timeline, Cog Map, Data. You're analysing patterns over time.

Most sessions are mode 1. Modes 2 and 3 are for maintenance, debugging, and research.

**Before asking:** check the **Coherence badge** at the top. Green = healthy. Yellow = watch. Red = investigate first (open Brain → Drift Monitor).

---

## Chat Tab

Send a message, press Enter. The system:
1. Extracts a `QuerySignal` (domain, shape, verbosity) — no LLM call, <1ms
2. Routes to the best agent
3. Runs the agent — this is where latency lives (~15–50s depending on reflection)
4. May reflect: grounded eval, then LLM critique + rewrite if confidence is low

**Typical latency:** No reflection: ~15–20s · Light: ~20–25s · Full: ~45–55s

### Reading the Signal Card

```
[python] [code] [normal] [78% conf] [light reflect]
  ↑         ↑       ↑         ↑            ↑
domain   shape  verbosity  routing      reflection
                           confidence    mode
```

- `conf < 40%` → routing signal was weak; agent picked by LLM fallback, less reliable
- `full reflect` → extra LLM critique-and-rewrite cycle; slower but more accurate

### When the answer seems wrong

1. **Check the Signal Card** — wrong domain? Add domain keywords to your query ("in Python", "in Blazor") or use a Force-Route button
2. **Check the Memory Viewer** — irrelevant memories? Click 👎 to penalise them
3. **Open Brain Inspector** — find the decision in the Brain tab, check regret and conflict

### Giving Feedback

Always rate responses when quality is clearly good or clearly bad.

- 👍 → `performance=0.90` in learning kernel + `+0.03` quality to accessed memories
- 👎 → `performance=0.25` in learning kernel + `−0.05` quality to accessed memories

**These are the only ground-truth signals the system has.** Every other quality signal is a proxy estimate. Use them.

### Force-Route Buttons

Colored buttons above the input box. Click one to bypass the coordinator.

| Button | Agent | Best for |
|--------|-------|----------|
| Python | python_dev | Python code, FastAPI, asyncio, pytest |
| .NET | dotnet_dev | C#, Blazor, .NET, MAUI, SignalR |
| Network | it_networking | DNS, VPN, SSH, firewalls, Linux |
| AI/ML | ai_ml | ML models, embeddings, LangChain |
| Learn | knowledge_learning | Explanations, concepts, teaching |
| Terse | terse | One-sentence factual lookups only |
| Auto | (coordinator) | Let the brain decide |

**When to force-route:** brain misrouted 2+ times in a row · you know exactly which domain applies · testing an agent in isolation.

### Pinned Context

Yellow bar below the agent selector. Text here is invisibly prepended to every message.

**Set it when you enter a work context, clear it when you leave.**
- `Working on ~/agentic-ai memory_db.py` — keeps Python Dev on-topic
- `Blazor WASM project, .NET 8, targeting Cloudflare Pages` — gives Blazor Dev full context
- Stale context misleads agents — clear it when switching domains

### File Attachments (RAG)

Click ⊕ (attach button) to upload PDF, Markdown, code, or plain text. Top-k matching chunks are automatically injected into every message that references the files. Chip shows upload status: uploading → ready → error.

---

## Task Queue Tab

Use for anything that takes time or doesn't need live interaction.

**Use Tasks when:** job is self-contained and well-defined · will take > 30 seconds · want to queue multiple things · want to walk away

**Use Chat when:** need answer now · might ask follow-ups · debugging live output · exploratory

### Writing a Good Task

**Weak:**
> Title: "research thing" — Prompt: "find out about fastapi"

**Strong:**
> Title: "FastAPI auth middleware patterns"  
> Agent: Python Dev  
> Prompt: "Research the main patterns for JWT authentication middleware in FastAPI 0.100+. Cover: (1) how to inject a dependency that validates tokens, (2) how to attach the decoded payload to request state, (3) common mistakes with async middleware. Python 3.11. Output as code examples with brief explanations."

Rules: name it so you can find it in a list of 20 · write as if emailing a developer who can't ask follow-ups · always specify output format · pick the agent yourself (don't use Auto for tasks).

---

## Overview Tab

System dashboard. Key actions:

- **Memory Health panel** — per-type quality bars, prune candidates count, ✂ Prune button
- **Prune when** `prune_candidates > 5` — removes `quality < 0.55 AND use_count = 0` entries only. Safe to run any time.
- **Export CSV** — all memories. Use before major architectural changes or for offline analysis.

---

## Brain Tab

Full observability into the routing brain.

- **Decision Log** — every decision: agent, intent, action, regret, confidence, conflict/reflect badges
- **Agent Health Panel** — weight bar, calibrated confidence, cal error, avg regret, trend arrow
  - **Weight** below 1.0 = underperformed recently; recovers with good responses
  - **Cal error** = `avg_confidence − avg_reflection`. Positive = overconfident.
  - **Regret** = rolling mean of `max(alt_conf) − chosen_conf`. High = system often routing suboptimally.
  - Healthy: weights near 1.0 ± 0.3 · cal error near 0 · regret < 0.10
  - Warning: weight < 0.6 · cal error > 0.25 · regret > 0.30
- **Drift Monitor** — three detectors: `calibration_drift` · `regret_explosion` · `weight_volatility`
  - If any fires: check `GET /analysis/failures` for root cause
- **Brain Inspector** — click any decision: full signal breakdown, timing, memories, reflection, Replay button
- **Contradiction History** — self-correction events; expand to see diff view

---

## Timeline Tab

Learning dynamics over time. Open periodically, not every session.

- **C(t) line chart** — coherence trending up, stable, or declining?
- **Reflection rate** > 50% means full reflection fires too often. Check triage is working.
- **Conflict rate** > 35% is high. Look at which agents show up in the conflict column.
- **G_r (reflection gain)** — positive fraction should be > 0.6. If negative G_r dominates, reflection is making answers worse.

---

## Cognitive Map Tab

Browse all memories grouped by agent domain.

- Expandable sections: type breakdown, avg quality, count per agent
- Filters: text search, type, agent dropdown
- Click any memory card → full content + metadata (quality, use_count, timestamp)

**Healthy distribution:** High proportion of `reflection` and `code` for code agents; `lesson` for knowledge_learning. `chat` should not dominate.

---

## Data Tab

Intelligence dataset and causal analysis.

- **Causal Path Explorer** — enter any decision ID → full path: signal → selected → rejected → memories → outcome → causal flags
- **Agent specialization** — verdict badges (core / narrow / struggling / redundant)
- **Counterfactual candidates** — decisions ranked by regret + conflict; test alternative routing
- **Memory Backend panel** — FAISS index stats, benchmark runner, promote button

---

## Common Debugging Patterns

### "The brain keeps routing to the wrong agent"

1. Check the Signal Card — what domain and confidence?
2. If `conf < 0.30`: query has no domain keywords → add some
3. If `conf > 0.30` but wrong domain: keyword set may have a gap → report in `docs/records/ISSUES.md`

### "Responses are getting slower"

1. Check reflection rate in Timeline
2. If full reflection fires often: recent responses had low confidence → check calibration error in Agent Health
3. Check `C(t)` — if declining, system is less certain; reflection fires more

### "Memory influences responses incorrectly"

1. Open Memory Viewer in the last response
2. Check which memories scored highest and from which agent
3. If wrong-agent memories score high: domain embedding overlap — rate 👎 to penalise
4. Use Cog Map to find and inspect the specific memory

### "Want to test if a new query type routes correctly"

1. Send the query in Chat
2. Check Signal Card — domain and confidence
3. Open Brain Inspector for that decision
4. If routing wrong: look at what keywords fired (or didn't) and add them to `query_normalizer.py`

---

## API Quick Reference

```bash
# Chat
curl -X POST localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "your question"}'

# Streaming
curl -X POST localhost:8000/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "your question"}'

# Memory
curl localhost:8000/memory/stats
curl localhost:8000/memory/prune           # preview
curl -X POST localhost:8000/memory/prune   # execute

# Learning / drift
curl localhost:8000/learning/drift
curl localhost:8000/decisions

# Eval (no LLM, <2s)
PYTHONPATH=. python3 evaluation/ablation_eval.py

# Full eval (~40 min)
PYTHONPATH=. python3 training/auto_train.py --eval-only
```

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Send message | Enter |
| New line | Shift+Enter |
| Focus chat | Ctrl+K |
| Toggle sidebar | Ctrl+B |
| Open settings | Ctrl+, |
| Open shortcuts | Ctrl+/ |
| Tabs 1–5 | Ctrl+1–5 |
| Close modal | Escape |
