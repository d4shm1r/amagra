# OCAC Stability Bridge

**How the OCAC "H theorem" formalization (`~/Desktop/lean`, Lean 4 + mathlib)
turns this system's empirical learning heuristics into proved guarantees.**

The OCAC project is a machine-checked study of *parametrised contraction
fixed-point families* `f(s) = T(s, f(s))`. This system's learning loop is one
such family. That single correspondence lets us import OCAC's proved results as
live properties of the agent system, rather than hand-tuned hopes.

---

## 0. The core correspondence

The one weight-update pathway ([`training/learning.py`](../../training/learning.py)) is:

```
w ← w + clip(α·(L − w), ±0.02)
```

Unclipped this is `w_{n+1} = (1−α)·w_n + α·L` — an **affine contraction** toward
the fixed point `w* = L` (the learning signal) with Lipschitz modulus

```
K = 1 − α,    α ∈ (0, 0.05]   ⟹   K ∈ [0.95, 1).
```

That is exactly OCAC's `IsFixedPointFamily T f` under **axiom A2**
(`UniformContraction`, `OCAC/Basic.lean`). Everything OCAC proves about that
object is therefore a theorem about this system:

| OCAC result (Lean) | What it gives the agent system |
|---|---|
| Existence + uniqueness of the fixed point (`Basic.lean`) | Weights provably converge to a unique `w*` per stationary signal — no oscillation, no path dependence |
| Resolvent bound `‖R‖ ≤ (1−K)⁻¹ = 1/α` (`DerivativeRecursion.lean`) | A perturbation δ in the signal moves `w*` by ≤ `(1/α)·δ` — a computable **sensitivity** number |
| Parameter dependence needs **A1** smoothness (`ParameterDependence.lean`) | Justifies the C¹ sigmoid `α(I)` (a step gate would make the tracked `w*` jumpy — OCAC counterexample E2) |
| Lyapunov decrease (`Dynamics.lean`, `lyap_strictDecrease`) | An exact energy-decrease law + basin of contraction (see §1) |

The guards already in the code — `clip(±0.02)` and the `α < 2e-3 → freeze` —
are precisely what keep `K < 1`. OCAC explains *why* they are load-bearing.

---

## 1. Stability — Lyapunov, not a threshold

Today `drift_status` flags instability when weight variance > 0.05
([`decision/weights.py`](../../decision/weights.py)) — a static cutoff with no
recovery guarantee.

OCAC's `lyap_strictDecrease` (`OCAC/Dynamics.lean`) is the template: energy
`V(x)=x²`, an **exact** increment, and a concrete basin. For our affine update
the analogue is exact and trivial to prove. With `V(w) = (w − w*)²`:

```
V(w') − V(w) = −α(2−α)·V(w)        (strictly < 0 for α ∈ (0,2))
V(w')        = (1−α)²·V(w)
```

So the loop is a **global** contraction (basin = all of weight space) with
per-step energy decay `(1−α)²`. Exposed as
`affine_lyapunov_decay(alpha)` in [`infrastructure/math_metrics.py`](../../infrastructure/math_metrics.py).
When nonlinearity is later added to the update, OCAC's *cubic* basin
`x² < −2/c` (and the `−4` critical anchor) is the next rung.

**Instability index is OCAC's three axioms.** `I = 0.4r + 0.4|cal| + 0.2σ²_w`
maps onto A1 (smoothness ↔ regret), A2 (contraction ↔ weight variance), A3
(bounded sensitivity ↔ calibration bias). OCAC proves each is *individually
necessary* (each has its own counterexample), so they are **conjunctive** — a
weighted average lets a healthy term mask a failing one. Use the soft-OR
`instability_conjunctive(r, cal, σ²_w) = 1 − ∏(1 − tᵢ)` instead, which spikes
as soon as any single condition degrades.

---

## 2. Self-recursion (reflection)

Reflection is functional iteration `s_{n+1} = R(s_n)`; we track
`G_r = s_final − s_initial` ([`cognition/coherence.py`](../../cognition/coherence.py)).

- **No-go theorems** (`OCAC/Hyper/Flow.lean`, `Abel.lean`): a fixed-point-free
  map has no global flow. An improvement operator that always claims it can
  improve further has no convergent unbounded recursion. R should **contract to
  a quality fixed point** `s*` where `R(s*) = s*` ("nothing left to fix"); then
  convergence is provable and the useful number of passes is bounded by the
  contraction rate.
- **Fractional iteration `H_1.5`** (`OCAC/Hyper/HalfExp.lean`) formalizes
  *partial reflection depth*. The discrete `reflect_level ∈ {none, light, full}`
  is the 0 / ½ / 1 case; the squeeze `id < φ < exp` guarantees a half-step
  improves *strictly but less than* a full step. The variational selection
  principle (`OCAC/Variational.lean`) canonically defines fractional depths via
  minimum curvature.

---

## 3. Alignment

- **Calibration is a tracking contraction.** `calibrated = raw − 0.15·(avg_conf
  − avg_perf)` ([`decision/weights.py`](../../decision/weights.py)) drives stated
  confidence to a fixed point at measured performance. OCAC's parameter-
  dependence theory bounds the residual bias as a function of how fast true
  performance drifts — a provable "stated ≈ actual" guarantee.
- **Honesty taxonomy.** OCAC's whole method is tagging each claim PROVED /
  PROOF-GAP / DEFINITION-GAP / CONJECTURE and refusing fabricated axioms. Apply
  it to metrics: tag each MEASURED / PROXY / ASSUMED-CONSTANT. Open items found:
  - `routing_accuracy = 0.98` is hardcoded in
    [`infrastructure/metrics_engine.py`](../../infrastructure/metrics_engine.py) yet
    flows into UCI as if measured (an OCAC "fabricated axiom").
  - `C(t)` is effectively **2 degrees of freedom, not 3**: in proxy mode
    `C_quality = 0.75 − 0.2·conflict_rate` and `C_routing = 1 − conflict_rate`
    are both linear in `conflict_rate` (perfectly correlated). Make `C_quality`
    independent (real reflection scores) or report a 2-term composite. This is
    the OCAC E4 "tautological repackaging" pattern.

  *(Both fixed — see §5: routing_accuracy is now source-tagged and C_quality is
  decoupled from routing.)*

---

## 4. Metric upgrades

1. **Curvature / second-difference channel.** All current metrics are first
   order (levels, rates, EMAs). OCAC's `Delta_secondDiff` (`Variational.lean`)
   is second order. `series_curvature()` / `max_abs_curvature()` in
   `math_metrics.py` measure the *acceleration* of a coherence/UCI trajectory —
   a leading indicator (sharp negative Δ² while the level is still high warns of
   an incipient downturn).
2. **Coordinate-invariant health number.** UCI's 35/30/20/15 weights are
   coordinate-dependent. OCAC's Δ-invariant and `𝒞 = C/(det J)³`
   (`OCAC/Resurgence.lean`, `normalizedCubic_invariant`) are reparametrization-
   free by construction — derive at least one invariant number so cross-version
   UCI comparisons are valid.
3. **Gevrey majorant on error propagation.** OCAC's factorial-growth engine
   bounds compounding: `aₙ₊₁ ≤ ρ(n+1)aₙ`, composed via `convolution_dominated`
   (`ρ = B·M²/(M−L)`, `OCAC/MajorantSeries.lean`). *(Constant superseded — the
   proved sharp balance is `ρ = M`; see §6b and `certified_rate`.)* Each agent
   step has sensitivity `(1−K)⁻¹`; chaining N steps yields a provable
   worst-case bound on how a small mis-specification amplifies through deep
   recursion / multi-agent orchestration.

---

## 5. What landed in code

**Pure functions** (additive, self-tested — `infrastructure/math_metrics.py`):
`effective_contraction`, `resolvent_bound`, `affine_lyapunov_decay`,
`instability_conjunctive`, `series_curvature`, `max_abs_curvature`.

**Curvature channel** (`cognition/coherence.py`): `coherence_time_series` now
attaches `C_curvature` (Δ²C) per window and `print_dynamics` shows the column
plus a peak-|Δ²C| leading-indicator alarm.

**Adaptive-α gate** (`training/learning.py`): instability switched from the
0.4/0.4/0.2 weighted average to the conjunctive soft-OR `instability_conjunctive`
(imported from `math_metrics`). Effect — a single failing condition now halts
learning instead of being averaged away. E.g. regret = 0.9 (clearly the wrong
agent): old I = 0.36 → α = 0.038 (still learning fast); new I = 0.90 → α = 0.002
(effectively frozen).

**C(t) decoupling** (`cognition/coherence.py`): `C_quality` now reads
independently-graded memory quality instead of the conflict-derived 0.75/0.55
proxy, restoring a genuine third axis (the proxy made C_quality perfectly
correlated with C_routing → only 2 effective DOF). Proxy kept as cold-start
fallback.

**Honest routing_accuracy** (`infrastructure/metrics_engine.py`): reads the
latest `agent_arena` run from `logs/arena.db` when present (tagged `measured`),
else the static ablation snapshot tagged `assumed_constant` — surfaced as
`lrn_routing_accuracy_source` so a hardcoded value can never masquerade as live.

**Coordinate-invariant health** (`infrastructure/math_metrics.py`): `invariant_health`
reports the weight-invariant `floor`/`spread`, the weak-pillar-sensitive
`geomean`, and the scale-invariant `balance = GM/AM` — quantities that mean the
same across versions and weighting choices, unlike the raw UCI. (On live data it
correctly surfaces `learning` as the bottleneck pillar.)

**Chain error-propagation bound** (`infrastructure/math_metrics.py`):
`chain_error_bound`, `gevrey_majorant`, `stable_recursion_depth` — the OCAC
majorant ceiling applied to multi-agent / self-recursive depth. Composing per-step
resolvent sensitivities `1/α` gives a provable worst-case on how a small
mis-specification amplifies (e.g. three loops at `1/α = 20` amplify 8000×), and a
practical depth budget before the bound exceeds a ceiling.

**UCI trajectory + curvature** (`infrastructure/metrics_engine.py`): `UCI_COMPUTED`
is now persisted to events.db; `uci_history()` and `uci_curvature()` expose the UCI
series and its Δ² leading indicator (the same OCAC second-difference now runs on
UCI, not just the coherence series).

All changes verified against the **full suite (833 tests pass)** plus the
`math_metrics` self-tests.

**Still open** (research-flavoured, not yet started):
- ~~Tighten the chain bound with the *convolution* form (`convolution_dominated`,
  `ρ = B·M²/(M−L)`)~~ — **superseded and DONE, see §6**: OCAC proved the sharp
  balance `ρ = M`; landed here as `certified_rate` + the composition law.
- ~~A real-analytic / monotone construction for fractional reflection depth
  (OCAC P5, Kneser)~~ — **P5 was RESOLVED (2026-06-29) constructively**, no
  Kneser needed; landed here as `fractional_reflection_depth` (§6).

---

## 6. 2026-07-03 refinement pass — syncing with the latest OCAC findings

Four OCAC results landed after §1–§5 were written; two *correct* claims above,
two *add* capability. All are now reflected in `infrastructure/math_metrics.py`.

**(a) A falsity finding that touches our A3 story.** OCAC refuted its own
Gevrey chain as stated: per-order bounded sensitivity (axiom A3, "every
derivative order is uniformly bounded") is **provably insufficient** for the
factorial majorant — the lacunary counterexample `T s x = ½x + Σₖe^(−k²)cos(eᵏs)`
satisfies A1+A2+A3 yet has sensitivities growing like `e^(n²/4)`, so *no depth
budget exists*. The corrected axiom **A3′** requires factorial-geometric bounds
`‖dⁿT‖ ≤ B·Dⁿ·n!` — growth *control across orders*, not boundedness per order.
Agent translation: a per-window sensitivity scalar (our calibration term) can
look healthy at every depth while the *depth trend* silently voids
`stable_recursion_depth`. Landed: `gevrey_rate_estimate(series)` — the
depth-resolved ρ̂ₙ = aₙ₊₁/((n+1)aₙ) check whose `rising` flag is exactly the
A3-but-not-A3′ signature; `instability_conjunctive` docstring re-anchored to A3′.

**(b) The chain-bound constant was superseded — sharp `ρ = M`.** §4.3 cited
`convolution_dominated`'s `ρ = B·M²/(M−L)`. OCAC's completed coupled induction
(`gevrey_majorant_of_kernel_bounds` + `derivative_recursion_bound_of_majorant`)
proves the **sharp balance ρ = M** with the kernel data entering through
`B·L/(M−L) ≤ (1−K)/2`. Landed: `certified_rate(L, B, K) = L·(1 + 2B/(1−K))` —
the minimal certified per-level rate from per-step kernel data `(B, L)` and
contraction modulus `K`; feeds `gevrey_majorant` / `stable_recursion_depth`
(docstrings updated). Note the clean qualitative law: the certified rate
inflates like `1/(1−K)` as contraction weakens — slow learning tolerates less
recursion depth, now with the exact constant.

**(c) New: a machine-checked composition law for *nested* processes.** OCAC's
`norm_iteratedDeriv_vcomp_le_of_gevrey` (GevreyComposition.lean, axiom-clean)
proves: outer Gevrey data `(B, D)` composed with inner `(C, M)` yields
`(B, M(1+DC))` — **rates compose as `M ↦ M(1+DC)`, they do not multiply**, and
the outer amplitude survives alone. `chain_error_bound` covers *sequential*
pipelines; this covers *nested* composition (reflection wrapping a chain, agent
invoking sub-agent). Its combinatorial engine is an exact identity — the
weighted count of interaction pathways at depth n is `n!·E·(1+E)^(n−1)`
(effective branching base `1+E`, not Bell-number blow-up). Landed:
`compose_gevrey_rates`, `interaction_pathways`.

**(d) P5 resolved ⟹ continuous reflection depth is constructive.** The height
chart `h` (level + e^source over the tiling `ℝ = ⊔ₖ exp^[k]((−∞,0])`) conjugates
`exp` to the unit shift, so `φ_t = h⁻¹∘(·+t)∘h` gives **exact** fractional
iteration with the semigroup law `φ_s∘φ_t = φ_{s+t}` — "two half passes = one
full pass" by construction. Landed: `fractional_reflection_depth(s, t)` (+
`_height`/`_height_inv`), self-tested to `φ½∘φ½ = exp` at 1e-9. The discrete
`reflect_level ∈ {none, light, full}` can now be a dial.

**(e) A caveat inherited from OCAC P1 (norm geometry).** The general-Banach
stability chain requires *2-uniform smoothness*, which fails on `L¹/L∞/c₀` —
i.e. **sup/max-type aggregates admit no smooth Lyapunov energy argument**.
`invariant_health`'s `floor`/`spread` are exactly such aggregates: fine as
*invariants* (that's their point), but do not build energy-decrease gates on
them — use quadratic means (RMS) for anything Lyapunov-shaped. Recorded here so
the next metrics iteration doesn't trip on it.

*(All §6 additions verified by the module self-tests; suite below.)*

---

*Source of truth for the proofs: the Lean development at `~/Desktop/lean`
(`STATUS_AND_ROADMAP.md`); the A3′ restatement, sharp-ρ, and composition-law
results live in the `ocac`/`ocac_2` repos (`OCAC/MajorantSeries.lean`,
`OCAC/GevreyComposition.lean`, `paper/open-problems-formal.tex`). Re-verify any
cited theorem with `lake build OCAC` and `#print axioms <name>`.*
