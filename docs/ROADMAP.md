# Amagra — Roadmap v2

> **The local AI workspace that lets you compare models and inspect every AI
> decision.** Run one prompt across GPT, Claude, Gemini and your local models, see
> exactly where they disagree, and replay *why* the system answered the way it did —
> all on hardware you control.

> **The pitch is settled elsewhere.** [`POSITIONING.md`](product/POSITIONING.md) is the
> single source of messaging truth; this roadmap defers to it. The job here is
> *sequencing the distribution work*, not re-deciding the story. (The sharper
> "token meter for agentic AI" framing is a real future wedge — it is staged in
> Line 2, not the headline, for the reason spelled out there.)

**Who it's for:** developers who run more than one model and need to see where they
disagree and why the system chose what it did — on their own hardware, with nothing
leaving the machine.

**Why now:** the constraint is **"almost nobody has seen it,"** not "they saw it and
left." Those demand opposite responses, and this is the better problem. The *State of
the AI Economy 2026* read still holds — AI revenue is ~0.4% of US GDP, a rounding error —
so designing enterprise tiers at user #0 is backwards. The next unit of work that moves
Amagra is therefore **evidence + reach**, not another advanced feature no one has watched.

> **The one rule this version exists to enforce:** distribution is the
> bottleneck, not features. You do not get to build Line 2 until Line 1 draws a
> real external signal. No more shipping into the void.

---

## The 0 → 1 sequence

### Line 1 — Distribution *(do this before any new code)*

The product has never been shown to a single stranger. Fix that first. The pitch itself
is already decided — [`POSITIONING.md`](product/POSITIONING.md) is settled and the README,
landing, and [`COMPARISON.md`](product/COMPARISON.md) already tell its story — so Line 1 is
**reach**, not re-writing copy.

| Step | Concrete action |
|------|-----------------|
| Shoot the three GIFs | The three-shot demo already specified in POSITIONING.md: **divergence run** (paste a prompt, fire at 4 models, Aligned/Mixed/Divergent resolves), **decision replay** (click a past answer, watch the routing reconstruct), **offline proof** (pull the network, it still answers locally). Three GIFs ≈ the whole pitch, no narration. |
| **Post it** | Show HN + r/LocalLLaMA, same day. Lead with the divergence run; use the titles already drafted in POSITIONING.md's *Channel hooks* (e.g. *"Compare GPT, Claude, Gemini and local models on one prompt — and replay every decision"*). |

**Success metric (honest — not MRR):** did *one stranger* run a task? First HN
comment, first star, first issue from someone who isn't you. That is the 0 → 1.

### Line 2 — Make the wedge undeniable *(only if Line 1 draws blood)*

| Item | Detail |
|------|--------|
| **Run Report** | One screen: cost + per-step verify pass/fail + cross-model agreement score + replay link, for a single agentic run. Assemble what already exists; build nothing new underneath. |
| **OpenAI-compatible `/v1`** | `OPENAI_BASE_URL=localhost:8000/v1` drop-in so devs point existing agent tooling at Amagra and get the meter for free. |

> **The token-meter wedge lives here, not at the top.** *"Amagra is the token meter for
> agentic AI — see whether your agent's spend was actually correct"* is a genuinely sharper
> pitch, but it only becomes *true for the target user* once the `/v1` drop-in ships: they
> have to be able to point Claude Code / Cursor / Codex at Amagra to get the meter for free.
> Leading with it today would pitch a capability Line 1 forbids us to build yet. So it is
> staged as the **Line-2 repositioning** — revisit the headline in
> [`POSITIONING.md`](product/POSITIONING.md) the moment `/v1` lands and the Run Report is
> real, not before.

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
**showing a developer where their models disagree and why the system decided what it
did** — comparison + decision replay in one place, on their own hardware. (The sharper
"was the agentic spend worth it?" framing is the Line-2 evolution of this once `/v1`
ships, not a competing story — see Line 2.)

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
