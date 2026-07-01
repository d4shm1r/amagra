# Amagra — The AI Operating Layer (Vision)

> Source: distilled from a strategic reflection (`checkIdea.md`, June 2026). This is a
> **direction doc**, not a commitment. Concrete, buildable items extracted from it have
> been folded into `docs/ROADMAP.md`; the long-horizon framing lives here.
>
> **Last reviewed: 2026-07-02 · release v1.6.3.** The section *"Where it actually stands"*
> below grounds this vision in **measured** reality — run against the live system, with
> sample sizes and caveats stated. Everything else in this doc remains direction.

---

## The reframe

Amagra is positioned today as *"the local cross-model prompt debugger."* That's the wedge,
not the ceiling. Looking at what's actually built — memory, routing, observability, the
agent framework, the critic gate, decision replay — the real shape is:

> **An AI operating layer with a built-in model-truth layer.**

The interesting thing was never "compare Claude vs GPT." It's that the system already
**remembers, routes, observes, verifies, and explains.** Those are operating-system
capabilities. Models are replaceable; the layer above them is permanent.

```
        Today                         Direction
   Prompt → compare           User → Amagra Core → Agents
   models → divergence               → Models → Tools → Devices
```

**The moat is not any model.** It's Memory · Context · Coordination · Trust · Observability —
the systems already in the codebase. GPT-6 arrives, Amagra remains. New devices arrive,
the memory follows the person, not the application.

---

## Where it actually stands — reviewed (v1.6.3 · 2026-07-02)

The wedge has moved. What began as *"a local cross-model prompt debugger"* is now a
**local-first agentic runtime with a native desktop presence**. Three shifts define the
current state:

1. **It's an app you install, not a repo you configure.** A one-file Linux **AppImage**
   (published on tag) and a native **Electron desktop app** (`desktop/`) both boot the
   FastAPI backend + built UI on one port and open a real AMAGRA window — no terminal.
   macOS/Windows (Electron/dmg/nsis) is scaffolded, not yet published.
2. **Chat is the home.** The sidebar, top-nav, and per-tab chrome collapsed into a single
   gold ☰ that opens a phone-style app-grid launcher. The experience contract is written
   down in [`DESIGN_PRINCIPLES.md`](DESIGN_PRINCIPLES.md) and now filters every feature.
3. **The operating-layer parts are real, not slideware** — signal-first routing, FAISS
   memory, the critic/verifier gate, decision replay, a Consensus engine, and a live
   observability/UCI surface all run today.

### Reviewed scorecard

Numbers below are **measured against the running system** (`/health`, `/cos/uci`,
`/coherence`, `/cos/transparency`, `/verify/stats`) or the offline eval — not estimates.
Read the caveats; several are healthy-on-a-small-window, not large-N benchmarks.

| Dimension | Measured value | Source & caveat |
|---|---|---|
| **Release** | **v1.6.3** (2026-07-02) | tagged; live instance still reports 1.6.0 until redeploy |
| Codebase | ~260 Python modules · ~50k LOC · 46 UI components · 81 test modules | repo, vendored/venv excluded |
| Specialist agents · skills | **10 active** (12 defined) · **21** routing skills | `/health`, skill graph |
| **Routing accuracy** | **98%** signal-only · **97%** full stack · vs **70%** action-first baseline | `ablation_eval.py`, 100 prompts (2026-06-09), offline |
| **UCI** (unified capability index) | **89.8 / 100** | live `/cos/uci` |
| — Reliability / Capability / Efficiency / Learning | 0.88 · 0.91 · 0.99 · 0.79 | live sub-scores |
| Coherence **C(t)** | **0.975** (routing 1.0, calib 1.0, quality 0.92) | live — but only a **20-decision window** |
| Step-verifier pass rate | **100%** (mean score 0.89, n=200) | `/verify/stats` |
| Exec-gate accept / retry-improve | 98% / 100% | live `/cos/uci` |
| Memory | FAISS, **91 vectors**, avg quality 0.92 | live — single dev instance, not scale-tested |
| **Transparency** | **30.8%** components fully transparent (4/13; 2 partial, 4 opaque, 3 unobserved) | live `/cos/transparency` |

### Honest read (what's proven vs. still aspirational)

- **Strong & measured:** routing quality (98% offline, from a 70% baseline) and the
  reasoning/exec gates (verifier 100%/n=200, exec-gate accept 98%) are the load-bearing
  wins. UCI at **89.8** is a genuinely high self-reported capability score.
- **Healthy but small-sample:** C(t) 0.975 is over a 20-decision window, and the UCI
  learning pillar takes `lrn_routing_accuracy` as an **assumed constant (0.98)**, not a
  continuously live-measured figure — the real routing proof is the offline ablation.
- **The visible gap:** **transparency sits at ~31%.** The "observable / accountable"
  thesis at the heart of the vision is *partly* delivered — 4 components disclose evidence
  **and** confidence; the rest are partial/opaque (tracked in issues #47/#48). This is the
  most honest measure of distance-to-vision, and it's the number to move next.
- **Unproven at scale:** memory is 91 vectors on one machine; multi-user, cross-device, and
  the whole Trust/Consensus-as-product layer remain direction, not fact.

> **One-line status:** a working, installable, local-first agentic runtime with excellent
> routing and reasoning gates and a calm chat-first UX — with observability/trust as the
> real, measured frontier still to close.

---

## The Amagra Core (organizing concept)

A single named center everything plugs into:

- memory · context · permissions · identity · routing · trust

The center of the system is the **user**, not a model. Existing components map cleanly:

| Existing system | Future role |
|-----------------|-------------|
| Memory          | Personal knowledge graph |
| Routing         | AI orchestration engine |
| Event bus       | System nervous system |
| Skill graph     | Agent ecosystem |
| Critic gate     | Quality-assurance layer |
| Prompt debugger | Truth / verification layer |
| Telemetry       | Self-improvement engine |
| Decision replay | Explainability framework |

---

## Product evolution (messaging arc)

1. **AI Workspace** (current) — "Compare models. Debug prompts. Inspect reasoning." Good for
   developers, early adopters, GitHub stars.
2. **Personal AI Runtime** — "A local intelligence layer that remembers your work, routes
   tasks to the best model, and explains every decision." Competes with OpenWebUI / AnythingLLM
   / LibreChat, but differentiated by memory + provenance.
3. **AI Operating System** — "One memory. Every model. Every device." No longer competing
   with chat UIs; competing with ecosystems.

### Candidate long-form positioning
> Amagra is the AI operating layer that sits above models, agents, and devices. It remembers
> context, routes work to the right intelligence, verifies outcomes through model consensus,
> and makes every decision observable.

Short forms: **"One Memory. Every Model. Complete Transparency."** ·
**"The trusted intelligence layer that survives every model generation."**

---

## The widening context ladder

The unit of understanding should grow over time — *contextually, not via surveillance*:

```
Conversation → User → Workspace → Life
```

Example: today *"Explain gradient descent."* → tomorrow *"Continue my ML study plan,"* with
the system holding previous lessons, mistakes, projects, goals, and preferred learning style.
That is where **memory becomes intelligence.**

---

## Buildable feature seeds (→ see ROADMAP for scheduling)

These are the parts of the vision that are concrete enough to schedule:

- **Consensus Engine** — when a task matters, ask several models, then produce an agreement
  score, confidence score, and contradiction map → a *Consensus Answer* or *"Models disagree,
  here's why."* This turns the existing divergence/debugger work from a debug feature into a
  **trust feature**. (Natural extension of the cross-model debugger.)
- **Trust Layer** — every claim tagged as fact / estimate / assumption / opinion, and
  traceable. Pairs with the existing provenance + decision-replay story.
- **Executive Mode** — instead of answers, give *decisions*: Option A vs B with trade-offs,
  a recommendation, reasoning, and a confidence level.
- **Proactive surface** — the system warns about risks, surfaces opportunities, prepares
  materials before meetings, monitors projects. "What needs my attention today?" → one
  prioritized answer. (Builds on the Cognitive OS suggestion engine + world model.)
- **Taste Engine** — learns what *this* user considers good/beautiful and their communication
  + decision patterns, so outputs feel curated rather than generic.
- **Memory vaults + zero-knowledge** — separate personal / business / financial vaults,
  user-owned memory, granular permissions, full audit logs: *"Show me everything you accessed
  to generate this answer."*
- **Cross-device memory** — desktop / mobile / browser extension / IDE plugin all see the same
  project. The memory follows the person.

---

## The luxury / "Apple-like" thesis

The premium feeling does **not** come from more features. It comes from **consistency,
reliability, simplicity, beautiful design, privacy, and high-quality output every time.**

- **Effortless** — short goals, not long prompts. *"Launch this business idea"* → the system
  coordinates the plan, research, deck, scheduling.
- **Deeply personal** — a secure model of how you think, not just facts you've stated.
- **Proactive** — behaves like an exceptional chief of staff.
- **Minimal interface** — voice / text / a timeline / a dashboard. "What needs my attention
  today?" returns a prioritized answer drawn from every system.

The end-state feeling is a **trusted digital partner** that quietly handles complexity and
presents only what matters — not a powerful tool you have to operate.
