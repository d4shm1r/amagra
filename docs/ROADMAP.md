# Amagra — Roadmap v2

> **The token meter for agentic AI.**
> Run an agentic task, see what it cost, verify each step, replay the decision,
> and check whether the models actually agreed it was right.

**Who it's for:** developers already burning tokens on agentic coding
(Claude Code / Cursor / Codex / OpenHands users) who have no idea whether the
spend was worth it.

**Why now:** the *State of the AI Economy 2026* deck shows agentic coding is the
live wave (it burns ~1,200× the tokens of a chat task) and that the industry's
single unsolved problem is that **tokens are the billing metric but not yet a
unit of value**. That gap is exactly what Amagra's verification + replay +
cross-model agreement already measure.

> **The one rule this version exists to enforce:** distribution is the
> bottleneck, not features. You do not get to build Line 2 until Line 1 draws a
> real external signal. No more shipping into the void.

---

## The 0 → 1 sequence

### Line 1 — Distribution *(do this before any new code)*

The product has never been shown to a single stranger. Fix that first.

| Step | Concrete action |
|------|-----------------|
| Reframe the pitch | Replace the abstract "accountable AI runtime" copy with the wedge above, everywhere (README, landing, POSITIONING.md). |
| Record one 60-sec GIF | agentic task → cost ticks up → step verifier flags a bad step → decision replay → "models agreed: 2/3." That's the whole product in one clip. |
| **Post it** | Show HN + r/LocalLLaMA, same day. Angle: *"I built a local 'token meter' that tells you if your agent's work was actually correct."* |

**Success metric (honest — not MRR):** did *one stranger* run a task? First HN
comment, first star, first issue from someone who isn't you. That is the 0 → 1.

### Line 2 — Make the wedge undeniable *(only if Line 1 draws blood)*

| Item | Detail |
|------|--------|
| **Run Report** | One screen: cost + per-step verify pass/fail + cross-model agreement score + replay link, for a single agentic run. Assemble what already exists; build nothing new underneath. |
| **OpenAI-compatible `/v1`** | `OPENAI_BASE_URL=localhost:8000/v1` drop-in so devs point existing agent tooling at Amagra and get the meter for free. |

### Line 3 — Moat *(only after real users; let usage pull it)*

Accumulated decision/verify history per project = the data-gravity moat. Do not
build it speculatively.

---

## Already built (real, verified)

The engineering is genuine — that has never been the problem. These all
correspond to working code and are the raw material for the wedge above:

- **Cross-model debugger** — `POST /debug/prompt`, run one prompt across N models, divergence highlight.
- **Consensus engine** — pairwise agreement matrix + verdict over N model answers (`core/consensus.py`).
- **Step verifier + critic gate** — per-step pass/fail and per-response scoring.
- **Decision replay + routing telemetry** — the "why did it do that" trace.
- **Per-run cost tracking** — `cost_usd` on the generation path → `GET /runs/cost`.
- **Persistent semantic memory** — SQLite → FAISS → outcome-weighted, LRU-cached.
- **Multi-provider** — Ollama / Anthropic / OpenAI-compat adapters; hybrid escalation.
- **Self-hosted install** — Docker image (`d4shm1r/amagra`), compose, one-file AppImage.

Full version-by-version history lives in git tags (v1.0 → v1.6) and
[`HISTORY.md`](records/HISTORY.md). It is preserved, just no longer the headline.

---

## Strategic positioning

**The category to own:** not "local chat UI" (Open WebUI owns that). The wedge is
**telling a developer whether their agentic-AI spend was worth it** — cost,
correctness, and agreement in one place.

**Genuinely differentiated — protect these:**
- Decision replay + routing telemetry (nobody else shows *why*).
- Cross-model agreement score (turns "models disagree" into a trust signal).
- The critic gate / step verifier loop.
- Honest-metrics culture — weaponize it; no competitor admits weakness in their README.

**NOT a moat:** routing accuracy, agent system prompts, the number of tabs, model
quality (last year's frontier commoditizes in months — the deck's [slide 59]).

**The real moat (later, usage-pulled):** accumulated decision/verification history.
Apps that survive defend with proprietary data + domain workflow, not horizontal breadth.

---

## Frozen until a stranger uses it

Moved to [`_someday.md`](product/_someday.md): pricing tiers, revenue projections,
marketplace, Agent SDK, Workspaces/RBAC, v1.7/v2.0 milestones, and further UI
redesign passes. None of it is wrong — it is just premature at user #0. The deck
shows even hyperscaler AI revenue is a rounding error against GDP; designing
enterprise tiers before the first user is backwards.
