# TCST Agent Model

**A grounded reading of the "time-coherent structure" agent framing against the
code that already exists in this repo — what is real, what is notation, and the
one piece worth building.**

The TCST framing models an agent not as a function that emits outputs but as a
**structured system that evolves under explicit deformation rules**. That is a
useful lens, but most of its equations are continuous-time hats on things this
system already does discretely. This doc separates the load-bearing idea from the
dressing and points each claim at a file. It is a companion to
[OCAC_STABILITY_BRIDGE.md](OCAC_STABILITY_BRIDGE.md), which already lands the
curvature / variational / fixed-point machinery the TCST writeup gestures at.

Honesty tags follow the OCAC convention: **REAL** (implemented, a file does it),
**METAPHOR** (true description, no mechanism yet), **DRESSING** (standard ML
re-notated).

---

## 0. The state object

TCST: `S(t) = (Θ(t), M(t), R(t), A(t))` — parameters, memory, reasoning rules,
action interface, all time-dependent.

| TCST component | What it is here | File (canonical) |
|---|---|---|
| `Θ(t)` — parameters | per-agent routing weights, calibration | [`training/learning.py`](../../training/learning.py), [`decision/weights.py`](../../decision/weights.py) |
| `M(t)` — memory | SQLite → FAISS at 800 entries, dedup, consolidation | [`memory_core/backend.py`](../../memory_core/backend.py), [`memory_core/db.py`](../../memory_core/db.py) |
| `R(t)` — reasoning rules | signal heuristics → CoreBrain → risk gate → critic | [`orchestration/core_brain.py`](../../orchestration/core_brain.py), [`cognition/reflection.py`](../../cognition/reflection.py) |
| `A(t)` — action interface | skill graph (21 nodes) → 10 specialist agents | [`infrastructure/skill_graph.py`](../../infrastructure/skill_graph.py), [`agents/registry.py`](../../agents/registry.py) |

The genuine claim of TCST is that **all four are state**, not just `Θ`. This repo
already treats them that way — `R` and `A` are mutable structures (`reflect_level`
is chosen per query; `skill_graph` re-scores per query), not frozen scaffolding.
So the object is **REAL** here; the novelty is purely in how the flows *couple*
(§5).

---

## 1. The four flows, mapped

### (1) Parameter flow — `dΘ/dt = −∇L`   · DRESSING

This is SGD with a continuous hat. The real update is the **affine contraction**
in [`training/learning.py`](../../training/learning.py):

```
w ← w + clip(α·(L − w), ±0.02)
```

Already formalized as an OCAC fixed-point family with a Lyapunov decay law — see
[OCAC_STABILITY_BRIDGE.md §0–1](OCAC_STABILITY_BRIDGE.md). The TCST gradient
notation adds nothing the contraction view doesn't already give (and the
contraction view gives a *provable* convergence the gradient hat does not).

### (2) Memory flow — `dM/dt = Φ_write − Φ_forget`   · REAL

Write/forget are concrete: dedup + consolidation on write, pruning + outcome-
weighting on forget, with auto-promotion SQLite→FAISS at 800 entries
([`memory_core/`](../../memory_core/), routes in [`routes/memory.py`](../../routes/memory.py)).
"Dynamic data manifold" is **METAPHOR** — there is no metric on `M` today, only a
1024-dim embedding space with cosine retrieval. That's enough for the flow; the
manifold language buys nothing until a metric is actually used (it isn't).

### (3) Reasoning-rule flow — `dR/dt = 𝒢(R,M,Θ) − λ∇C_reason`   · REAL

This is the TCST-specific component, and — verified against `think()`, not
assumed — it is **already a closed coupling**, in discrete steps rather than a
continuous flow:

- `𝒢` (rule deformation) ≈ reflection: `reflection_loop` iterates
  evaluate→critique→refine ([`cognition/reflection.py:178`](../../cognition/reflection.py#L178)),
  and CoreBrain re-selects `reflect_level ∈ {none, light, full}` per query via
  the risk gate ([`orchestration/core_brain.py:228`](../../orchestration/core_brain.py#L228)).
- `C_reason` (coherence constraint) ≈ the coherence series + curvature alarm in
  [`cognition/coherence.py`](../../cognition/coherence.py).

`𝒢` **does** read `Θ` and `M` as arguments — this is the correction to an earlier
draft that wrongly listed both as missing:

- `R ← Θ`: `confidence = to_confidence(primary)` (derived from the agent's
  historical weights) feeds `_reflect_level` → `risk_gate`, whose
  `routing_uncertainty` term is `1 − confidence`
  ([`core_brain.py:507-514`](../../orchestration/core_brain.py#L507-L514)). Weights
  drive reflection depth today.
- `R ← M`: the **reflection-history bias** block searches `mem_type="reflection"`
  and swaps agent or forces `full` reflect when this agent scored poorly on
  similar past queries ([`core_brain.py:517-558`](../../orchestration/core_brain.py#L517-L558));
  the **episodic** block searches `mem_type="episodic"` and boosts confidence on
  past success / adds `light` reflect on past failure
  ([`core_brain.py:570-602`](../../orchestration/core_brain.py#L570-L602)).

So the reasoning flow is **REAL** and genuinely coupled to both memory and
weights. The remaining gap is downstream, in (4).

### (4) Action-structure flow — `dA/dt = Ψ(R,Θ,E)`   · partly REAL — **the one open edge**

`A` is reconfigured per query: `select_skills` / `top_agent` re-rank the 21-node
skill graph ([`infrastructure/skill_graph.py:310`](../../infrastructure/skill_graph.py#L310)),
and the world-model planner sequences actions ([`models/world_model.py:94`](../../models/world_model.py#L94)).
But `select_skills(query, n)` takes the **query string and nothing else** — no
`action`, no chosen `primary`, no `confidence`. The planner already *holds* that
reasoning state as parameters ([`orchestration/planner.py:362-364`](../../orchestration/planner.py#L362-L364))
yet calls `select_skills(query, n=3)` and discards it
([`planner.py:378`](../../orchestration/planner.py#L378)). So action geometry is
*reconfigurable* (REAL) but **not coupled to reasoning state** — `Ψ` ignores `R`
and `Θ`. This is the single genuinely-missing coupling (§5).

---

## 2. Curvature and the variational principle — already landed

The TCST writeup's §4 (`K(S) = ∇²_t R`) and §5 (`δF[S] = 0`) are exactly the
OCAC second-difference and variational-selection results, and they are **already
in code** — see [OCAC_STABILITY_BRIDGE.md §4–5](OCAC_STABILITY_BRIDGE.md):

- **Curvature channel:** `series_curvature` / `max_abs_curvature` in
  [`infrastructure/math_metrics.py`](../../infrastructure/math_metrics.py); `C_curvature`
  (Δ²C) attached per window in [`cognition/coherence.py`](../../cognition/coherence.py);
  `uci_curvature()` runs the same Δ² on the UCI trajectory.
- **Variational selection:** OCAC's `Variational.lean` canonically defines
  fractional reflection depth by minimum curvature — the formal backing for
  `reflect_level`'s 0/½/1.

So `α|K(S)|²` in the TCST objective is **not** a new thing to build — it is the
existing curvature leading-indicator, and it is a **loss/monitor term**, not a
solved Euler–Lagrange equation. The variational principle `δF = 0` is a *post-hoc
description* of the trajectory, not a mechanism; the mechanism is greedy
contraction + the curvature penalty. Calling it variational is fine as long as
the doc says that out loud. (It now does.)

**The honesty trap to avoid:** "high curvature = hallucination" is only useful if
`K` is computed independently of whether the output was wrong. The current Δ²C is
computed from the coherence series, which is itself partly outcome-derived — so
treat the curvature alarm as a **PROXY** leading indicator, not a measured
instability. This is the same E4 "tautological repackaging" caution flagged in
the OCAC bridge §3.

---

## 3. The hyperstructure layer — already the routing stack

TCST §6: `R = (R₀, R₁, …, Rₙ)` from base inference up to rule-modifying
reasoning. This system's routing stack *is* that ladder:

| TCST rung | Component |
|---|---|
| `R₀` base inference | direct route (signal heuristics, ~1ms, no LLM) |
| `R₁` compositional | CoreBrain domain/complexity detection ([`core_brain.py:182`](../../orchestration/core_brain.py#L182)) |
| `R₂` meta-reasoning | reflection_loop critique/refine |
| `R₃` rule-modifying | adaptive-α gate that freezes/permits learning |

The upward/downward flow `dRₖ/dt = f(Rₖ, Rₖ₊₁, M)` is **partly REAL**: the rungs
call *down* (CoreBrain → direct route fallback) **and** the reasoning rungs read
memory upward (reflection-bias + episodic blocks, §1(3)). What does not yet feed
back is the *action* rung `A`, which the reasoning rungs don't condition — the §5
gap.

---

## 4. What is NOT being claimed

Stated plainly so the framing can't drift into overclaim — this mirrors the TCST
writeup's own §10 and the OCAC bridge's honesty discipline:

- No physics. No literal spacetime curvature. `K` is a second difference of a
  scalar series.
- No claim that `δF = 0` is solved. It describes; contraction + penalties do.
- The "manifold" / "geometry" language is **decoration** until a metric is used
  in an actual computation. Today none is.

---

## 5. The one piece worth building: the coupling graph

TCST §7 is the only part that distinguishes this from "modular ML with Greek
letters": the flows must be **coupled**, not independent —

```
dΘ/dt ↔ dR/dt ↔ dM/dt        e.g.  dR/dt = h(Θ) + j(M) − ∇C
```

> learning changes reasoning, and reasoning changes learning.

Audited against the code (`think()` line by line, not assumed), **four of five
couplings are already real**. The earlier draft of this doc overcounted the gap;
the corrected status:

| Coupling TCST asserts | Status in repo |
|---|---|
| `R` reads `M` (reflection from experience) | ✓ reflection-bias + episodic blocks ([`core_brain.py:517-602`](../../orchestration/core_brain.py#L517-L602)) |
| `R` reads `Θ` (reflection depth from weight confidence) | ✓ `to_confidence` → risk_gate ([`core_brain.py:507-514`](../../orchestration/core_brain.py#L507-L514)) |
| outcome → `M` weighting | ✓ outcome-weighted memory exists |
| `M`/calibration → `Θ` | ✓ via learning signal `L` |
| `A` reads `R`/`Θ` (skill selection from reasoning state) | ✗ **`select_skills(query)` keys off query only** |

So the reasoning↔memory↔learning triangle is closed. The **one** open edge is
`A ← R`: the skill graph re-ranks against the bare query and ignores the
`action`/`primary`/`confidence` the planner already holds
([`planner.py:362-378`](../../orchestration/planner.py#L362-L378)). Closing it is a
small, bounded change — thread the existing `BrainDecision` fields into
`select_skills` so skill selection is conditioned on reasoning state rather than
the query alone. No new storage, no new flow; just stop discarding state that's
already in scope. That single edit makes the "TCST" label *earned* rather than
retrofitted, and the OCAC chain-error bound (`chain_error_bound`,
`stable_recursion_depth`) caps how far the now-fully-coupled loop can amplify a
mis-specification through depth.

That is the recommended next step if this framing is pursued — not the curvature
layer (done), not the variational solver (a description, not a mechanism), and not
the reasoning couplings (already wired).

### 5a. The cost of closing the loop: saturation

Closing `A ← R` makes the influence graph fully cyclic
(`Θ → R → A → M → Θ`). The structural risk of any closed influence graph is
**coupling saturation**: correlated updates where every channel reinforces the
same routing prior, so skill diversity collapses onto whatever `R` already
favours. This is a property of the topology, not a bug in the patch.

For *this* edge it is partially self-damping, by mechanisms already in the code:

- **Negative-feedback branch.** The reflection-bias block swaps *away* from an
  agent that scored `< 0.60` on similar past queries
  ([`core_brain.py:529`](../../orchestration/core_brain.py#L529)) — so `M → R`
  reinforces on success but diverts on failure. The loop only tightens around
  agents that keep succeeding, which is the desired convergence.
- **Stateless skill scoring.** The `+0.15` bias does not accumulate in the skill
  graph (scores recompute per query); reinforcement can persist only through `M`
  and `Θ`.
- **Existing decay.** `Θ` is clipped `±0.02`/step (OCAC contraction) and `M` is
  pruned/consolidated, bounding how fast the loop can amplify.

So saturation is *the thing to instrument first*, not an imminent failure. The
diagnostic — **before** any entropy *regularizer* or self-calibrated gain — is
rolling **skill-selection entropy**: if it trends down while task success stays
flat, the loop is saturating and `_BIAS_PREFER_AGENT` should be attenuated (or
made confidence-dependent), not raised. Only after that diagnostic exists should
the fixed `0.15 / 0.05` gains be learned from routing outcomes; tuning a closed
feedback loop without it tunes blind.

> **Status: the diagnostic shipped with the coupling.**
> `infrastructure/skill_graph.entropy_report()` measures rolling selection
> entropy (raw bits, normalized against the 21-skill capacity, older-vs-newer
> half delta, coupled-selection share) over the last ≤512 selections, served at
> `GET /cos/skills/entropy`. `falling: true` (newer half ≥ 0.5 bits below the
> older) is the attenuate-don't-raise signal described above. The gains remain
> fixed constants — learning them is still gated, now on what the report shows
> under real load, not on missing instrumentation.

---

## 6. Bottom line

- The TCST *object* `S=(Θ,M,R,A)` is **REAL** here — this repo already treats
  reasoning rules and action geometry as evolving state.
- Flows (1) and the curvature/variational layer are **already implemented** under
  OCAC names; the TCST notation re-describes them.
- The "manifold/geometry/curvature-in-spacetime" language is **decoration** with
  no computation behind it yet.
- The novel, buildable contribution is the **§7 coupling discipline** — but
  verified against `think()`, **four of five couplings already exist**. The
  reasoning↔memory↔learning triangle is closed; the **single** open edge is
  `A ← R` (skill selection ignores reasoning state). Closing that one edge is the
  whole remaining task.

*Companion: [OCAC_STABILITY_BRIDGE.md](OCAC_STABILITY_BRIDGE.md) for the proved
stability results this leans on. Orientation: [PROJECT_MAP.md](PROJECT_MAP.md).*
