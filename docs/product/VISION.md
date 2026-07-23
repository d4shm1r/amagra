# Amagra — An Operating System for Intelligence (Vision)

> Source: distilled from a strategic reflection (`checkIdea.md`, June 2026) and the v1.9.0
> reframe (July 2026). This is a **direction doc**, not a commitment. Concrete, buildable
> items extracted from it are folded into `docs/ROADMAP.md`; the long-horizon framing lives here.
>
> **Two things in this doc are load-bearing and must stay in balance:** the *principles* (what
> governs the system) sit on top; the *measured reality* (§ "Where it actually stands") sits
> underneath and keeps them honest. A principle earns its place only when a number can prove —
> or disprove — it. **Last measured: 2026-07-23 · release v1.8.0** — live `/cos/*` rows read from a
> freshly booted local instance (single 3.8B model, n=12 decisions; treat as directional), routing
> from a 138-prompt offline eval. Everything not in the scorecard is direction.

---

## The thesis

Models change. Interfaces change. Devices change. Work does not.

Amagra is the persistent intelligence layer that sits **above** models, agents, and tools. It
understands intent, coordinates execution, preserves memory, verifies reasoning, and improves
through observation. The center of the system is the **user**, not a model.

> Models become replaceable. Knowledge becomes durable. Trust becomes measurable.

**Intelligence That Persists.** · *One Memory. Every Model. Complete Transparency.*

The differentiator in 2026 is no longer "we have agents / memory / orchestration" — everyone
claims those. It is that the system is **trustworthy, observable, adaptive, and acts with
restraint.** Those are operating-system properties, not features.

---

## The Intelligence Loop

Amagra is not a set of components sitting side by side. It is one loop, and every component is
a stage of it. This is a diagram of **shipped parts**, not a wishlist — the parts named below
run today (see the scorecard for how far each stage actually reaches).

```
   Observe  →  Understand  →  Reason  →  Execute  →  Verify  →  Learn  →  Remember
      │            │            │           │           │          │          │
   event_bus    signal      core_brain    agents +   critic /   metrics   FAISS memory
   world_model  routing     consensus     skills     exec gate  engine    + decision log
      └──────────────────────────── feeds back into ──────────────────────────┘
```

> Amagra doesn't respond to prompts. It executes intentions — and closes the loop by measuring
> the outcome and remembering what it learned.

The loop is the spine of the rest of this document. Principles describe how each stage *should*
behave; the scorecard reports how well it *actually* does.

---

## System principles

Not UI principles — principles that govern the runtime. Each names the mechanism that backs it,
or is honestly marked **[direction]** where the mechanism isn't real yet.

**Intelligence over interaction.** Users express goals; Amagra determines execution.
*Backed by:* signal-first routing (100% offline, 138 prompts), `core_brain` reasoning layer.

**Trust over confidence.** Every answer should expose evidence, assumptions, and uncertainty —
confidence without explanation is not trust. *Backed by:* decision replay, provenance, critic
gate. *Frontier:* transparency at ~31% (see scorecard) — this is the honest distance-to-vision.

**Memory over history.** The system remembers what *matters*, not everything; memory should
change the quality of thinking, not merely increase recall. *Backed by:* FAISS memory with
quality weighting, consolidation, pruning. *[direction]* cross-device, multi-user.

**Coordination over automation.** The goal is intelligent coordination between humans, models,
tools, and agents — not autonomy for its own sake. *Backed by:* router + skill graph + exec gate.

**Transparency over magic.** If the system cannot explain itself, it should not act.
*Backed by:* exec gate, verifier, `/cos/transparency` surface.

**Evolution over configuration.** Every interaction should leave the system slightly more
capable, without the user tuning anything. *Backed by:* telemetry → metrics engine → outcome
weighting. *Frontier:* learning is measured but not yet a closed policy-update loop (see caveat).

**Privacy by architecture.** Personal cognition belongs to the user, never the platform.
*Backed by:* local-first runtime, user-owned data dir. *[direction]* vaults, zero-knowledge.

---

## Where it actually stands — reviewed (v1.8.0 · 2026-07-23)

This is the credibility anchor of the whole document. Numbers below are **measured against the
running system** (`/health`, `/cos/uci`, `/coherence`, `/cos/transparency`, `/verify/stats`) or
the offline eval — not estimates. Several are healthy-on-a-small-window, not large-N benchmarks;
read the caveats. Rows are keyed to the **loop stage** they measure, so distance-to-vision is
legible per stage.

> **Measurement context (2026-07-23, v1.8.0).** The live rows were refreshed on a **freshly
> booted local instance** driven by **12 real `/ask` requests**, brain = **`phi4-mini` (3.8B,
> local single model)**, embeddings = `nomic-embed-text`, memory backend = **SQLite** (FAISS not
> installed in this env). This is a *small, single-model, cold-started* window — decisions `n=12`,
> memory 23 vectors — so treat every live figure as directional, not benchmark-grade. The routing
> row is a separate **offline** eval (138 prompts). Where a number moved materially from the
> populated 2026-07-02 snapshot, the delta is noted.

The wedge has moved. What began as *"a local cross-model prompt debugger"* is now a
**local-first agentic runtime with a native desktop presence**: a one-file Linux **AppImage** and
an **Electron desktop app** both boot the backend + built UI on one port with no terminal
(macOS/Windows scaffolded, not yet published); **chat is the home** behind a single ☰ launcher,
with the experience contract written down in [`DESIGN_PRINCIPLES.md`](../design/DESIGN_PRINCIPLES.md);
and the operating-layer parts are **real, not slideware** — routing, FAISS memory, the
critic/verifier gate, decision replay, a consensus engine, and a live observability/UCI surface
all run today.

### Reviewed scorecard

| Loop stage | Dimension | Measured value (2026-07-23) | Source & caveat |
|---|---|---|---|
| — | **Release** | **v1.8.0** | live instance reports 1.8.0 |
| — | Codebase | ~260 Python modules · ~50k LOC · 46 UI components · 81 test modules | repo, vendored/venv excluded (structural, not re-counted) |
| Understand | Specialist agents · skills | **10 active** (12 defined) · **21** routing skills | `/health`, skill graph |
| Understand | **Routing accuracy** | **100%** signal-only · **97%** full stack · vs **70%** action-first baseline | `ablation_eval.py`, **138 prompts (2026-07-23)**, offline; full-stack/baseline from eval logs (2026-06-09) |
| Reason/Verify | **UCI** (unified capability index) | **90.9 / 100** | live `/cos/uci` (n=12) |
| Reason/Verify | — Reliability / Capability / Efficiency / Learning | 0.92 · 0.91 · 0.96 · 0.83 | live sub-scores |
| Verify | Coherence **C(t)** | **0.876** (routing **0.73**, calib 1.0, quality 0.90) | live — **n=12** window; routing coherence on live traffic runs well below the offline ablation (see honest read) |
| Verify | Step-verifier pass rate | **100%** (mean score 0.96, n=12) | `/verify/stats` — same small model self-scoring |
| Execute | Exec-gate accept / retry-improve | 92% / 0% | live `/cos/uci` (n=12; 1 retry, did not improve) |
| Remember | Memory | SQLite backend, **23 vectors**, avg quality 0.90 | live — fresh instance, not scale-tested (FAISS path unused here) |
| Trust | **Transparency** | **30.8%** components fully transparent (4/13; 1 partial, 3 opaque, 5 unobserved) | live `/cos/transparency` — **stable** vs 2026-07-02 |

### Honest read (what's proven vs. still aspirational)

- **Strong & measured (Understand / Execute / Verify):** routing quality (100% offline on 138
  prompts, from a 70% baseline) and the reasoning/exec gates (verifier 100%, exec-gate accept 92%)
  are the load-bearing wins. UCI at **90.9** is a genuinely high self-reported capability score,
  though on a 12-decision window.
- **In-distribution, not generalization (Understand):** the 100% signal-only figure is on the
  `auto_train` prompt set the router is tuned against — it proves *no regressions* on known
  shapes, not accuracy on unseen phrasing. A held-out set is the honest next measurement.
- **The new, honest gap (Understand → Verify):** on **live traffic**, routing coherence
  `c_routing` measured **0.73**, well below the offline ablation's near-perfect score. The offline
  eval measures *can the router pick the right agent on clean prompts*; the live figure measures
  *did routing stay self-consistent across a real session* — and the latter is the harder, truer
  number. This gap is the most useful thing this re-measure surfaced.
- **Small-sample & self-scored (Verify / Learn):** every live figure is `n=12` on a fresh
  instance, and the verifier/quality scores are a **3.8B local model grading its own output** —
  expect them to soften under a larger, multi-model, adversarial load. The UCI learning pillar
  still takes `lrn_routing_accuracy` as an **assumed constant (0.98)**, not a live-measured figure,
  so the *Evolution* principle remains partly aspirational: telemetry is measured, but the
  policy-update loop that would close it is not yet continuous.
- **The visible gap (Trust):** **transparency sits at ~31%** — and held **stable** under live
  traffic (4/13 fully transparent; 5 components never emitted an observable event at all). The
  "observable / accountable" thesis is *partly* delivered; the rest are partial/opaque/unobserved
  (tracked in issues #47/#48). This is the most honest measure of distance-to-vision, and the
  number to move next.
- **Unproven at scale (Remember):** memory is 23 vectors on one fresh machine (SQLite, not the
  FAISS path); multi-user, cross-device, and the whole Trust/Consensus-as-product layer remain
  direction, not fact.

> **One-line status:** a working, installable, local-first agentic runtime with excellent routing
> and reasoning gates and a calm chat-first UX — with observability/trust as the real, measured
> frontier still to close.

---

## The Amagra Core (organizing concept)

A single named center everything plugs into — memory · context · permissions · identity ·
routing · trust — with the **user** at the center, not a model. Existing components map cleanly
onto their loop role and their future role:

| Existing system | Loop stage | Future role |
|-----------------|-----------|-------------|
| Memory          | Remember  | Personal knowledge graph |
| Routing         | Understand| AI orchestration engine |
| Event bus       | Observe   | System nervous system |
| World model     | Observe   | World state (self / workspace / project / external) |
| Skill graph     | Execute   | Agent ecosystem |
| Critic gate     | Verify    | Quality-assurance layer |
| Prompt debugger | Verify    | Truth / verification layer |
| Telemetry       | Learn     | Self-improvement engine |
| Decision replay | Learn     | Explainability framework |

---

## Product evolution (messaging arc)

1. **AI Workspace** (current) — "Compare models. Debug prompts. Inspect reasoning." Good for
   developers, early adopters, GitHub stars.
2. **Personal AI Runtime** — "A local intelligence layer that remembers your work, routes tasks
   to the best model, and explains every decision." Competes with OpenWebUI / AnythingLLM /
   LibreChat, differentiated by memory + provenance.
3. **AI Operating System** — "One memory. Every model. Every device." No longer competing with
   chat UIs; competing with ecosystems.

### Candidate long-form positioning
> Amagra is the operating system for intelligence: it sits above models, agents, and devices,
> understands intent, routes work to the right intelligence, verifies outcomes through model
> consensus, and makes every decision observable — so the model can change and the intelligence
> layer endures.

Short forms: **"Intelligence That Persists."** · **"One Memory. Every Model. Complete
Transparency."** · **"The trusted intelligence layer that survives every model generation."**

---

## The widening context ladder

The unit of understanding should grow over time — *contextually, not via surveillance*:

```
Conversation → User → Workspace → Life
```

Example: today *"Explain gradient descent."* → tomorrow *"Continue my ML study plan,"* with the
system holding previous lessons, mistakes, projects, goals, and preferred learning style. That is
where **memory becomes intelligence** — the *Memory over history* principle made concrete.

---

## Buildable feature seeds (→ see ROADMAP for scheduling)

The parts of the vision concrete enough to schedule. Each is tagged with the loop stage it
extends.

- **Consensus Engine** *(Verify)* — when a task matters, ask several models, then produce an
  agreement score, confidence score, and contradiction map → a *Consensus Answer* or *"Models
  disagree, here's why."* Turns the divergence/debugger work from a debug feature into a **trust
  feature**.
- **Trust Layer** *(Verify)* — every claim tagged as fact / estimate / assumption / opinion, and
  traceable. Pairs with existing provenance + decision-replay. Directly moves the transparency
  frontier.
- **Decision / Executive Mode** *(Reason)* — instead of answers, give *decisions*: Option A vs B
  with trade-offs, a recommendation, reasoning, risk, and a confidence level. (Decision
  Intelligence #1 — EV selector shipped; benchmark in `docs/records`.)
- **World State + Proactive surface** *(Observe)* — maintain self / workspace / project /
  external state so the system knows what you're doing, what's blocked, what changed overnight.
  "What needs my attention today?" → one prioritized answer. (Builds on world model + suggestion
  engine.)
- **Taste Engine** *(Learn)* — learns what *this* user considers good and their communication +
  decision patterns, so outputs feel curated rather than generic.
- **Memory vaults + zero-knowledge** *(Remember)* — separate personal / business / financial
  vaults, user-owned memory, granular permissions, full audit logs: *"Show me everything you
  accessed to generate this answer."*
- **Cross-device memory** *(Remember)* — desktop / mobile / browser extension / IDE plugin all see
  the same project. The memory follows the person, not the application.

---

## The luxury / "Apple-like" thesis

The premium feeling does **not** come from more features. It comes from **consistency,
reliability, simplicity, beautiful design, privacy, and high-quality output every time** — the
*restraint* half of the differentiator.

- **Effortless** — short goals, not long prompts. *"Launch this business idea"* → the system
  coordinates plan, research, deck, scheduling.
- **Deeply personal** — a secure model of how you think, not just facts you've stated.
- **Proactive** — behaves like an exceptional chief of staff.
- **Minimal interface** — voice / text / a timeline / a dashboard. "What needs my attention
  today?" returns a prioritized answer drawn from every system.

The end-state feeling is a **trusted digital partner** that quietly handles complexity and
presents only what matters — not a powerful tool you have to operate.
