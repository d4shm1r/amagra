# Amagra — Metric Improvements (continuation of the OCAC bridge)

*Continues [`docs/OCAC_STABILITY_BRIDGE.md`](docs/OCAC_STABILITY_BRIDGE.md) §4–5. Anchored
on the **latest OCAC finding** (Lean `STATUS_AND_ROADMAP`, 2026‑06‑25): the canonical cubic
tensor `cubicFDeriv = iteratedFDeriv ℝ 3 (T s)` and its proved scalar reduction
`cubicFDeriv_diag_eq_cubicCoeff`, with the honest conclusion that scalarizing it to a stability
number is **not** canonical — it needs a marginal **direction** `v` and **covector** `ℓ`, because
**a norm erases the sign** that `C ≤ −ε` (attractor vs. repeller) depends on.*

---

## The one thesis

The bridge already imported OCAC's *affine* results (contraction, resolvent, Lyapunov decay,
curvature, invariant health, chain bound — all shipped in
[`evaluation/math_metrics.py`](evaluation/math_metrics.py)). The newest finding is **sharper and
not yet reflected**:

> Stability is a **signed** quantity. The sign of the cubic/curvature term is what separates
> *self‑correcting* drift from *runaway* drift. Any metric that collapses it through a norm
> (`abs`, variance, magnitude) destroys the one bit that matters.

Two shipped metrics make exactly that mistake. Fixing them is the highest‑value, lowest‑risk
work — and it traces to a proved theorem, not a heuristic.

---

## P1 — `max_abs_curvature` discards the load‑bearing sign ★ ship first

[`math_metrics.py:462`](evaluation/math_metrics.py#L462) computes the OCAC second difference
`Δ²` (`series_curvature`, correctly signed) and then **throws the sign away**:

```python
return round(max((abs(c) for c in curv), default=0.0), 6)   # abs() — the OCAC anti-pattern
```

So an *incipient downturn* (`Δ² < 0` while the level is still high — the alarm the bridge §4.1
explicitly wants) and a *recovery overshoot* (`Δ² > 0`) produce the **same** number. This is the
app‑level instance of the finding: a norm folded away the sign. Add a signed leading indicator:

```python
def curvature_leading_indicator(series: list[float]) -> dict:
    """Signed Δ² alarm — keeps the sign the OCAC cubic finding says is load-bearing.
    Negative peak while level is high ⇒ incipient downturn (warn);
    positive ⇒ self-correcting rebound (safe)."""
    curv = series_curvature(series)
    if not curv:
        return {"signed_peak": 0.0, "regime": "flat", "warn": False}
    signed_peak = min(curv, key=abs) if False else max(curv, key=abs)  # largest |Δ²|, signed
    return {
        "signed_peak": round(signed_peak, 6),
        "regime": "downturn" if signed_peak < 0 else "rebound" if signed_peak > 0 else "linear",
        "warn": signed_peak < 0 and series[-1] > 0.7,   # bending down from a high level
    }
```

Keep `max_abs_curvature` for backward compat; route the dashboard alarm through the signed one.
*Traces to:* `Delta_secondDiff` (`OCAC/Variational.lean`) + the sign lesson of
`cubicCoeff_neg_iff`.

---

## P2 — `drift_status`: a Lens of Stability, not a variance threshold

[`decision/weights.py:382`](decision/weights.py#L382) flags instability when **weight
variance > 0.05** — a magnitude cutoff the bridge §1 already called out as "a static cutoff with
no recovery guarantee." Variance is sign‑blind: a cluster of weights *converging* to a new stable
configuration and a cluster *diverging* can show the same variance.

The latest finding gives the right object — the **signed cubic coefficient** and its proved basin
`x² < −2/c` (`lyap_strictDecrease_radius`, the `−4` anchor `cubicCoeff_critical`). Replace the
threshold with a **two‑part signed test**:

1. **Sign** of the drift's second difference per agent weight track → self‑correcting (`< 0`,
   curving back) vs. runaway (`> 0`).
2. **Basin membership**: is the current excursion inside the proved recovery radius? If yes, emit
   a *recovery guarantee* ("provably self‑corrects"); if no, escalate.

```python
def drift_status_v2(weight_history: dict[str, list[float]]) -> dict:
    worst = None
    for agent, track in weight_history.items():
        c2 = series_curvature(track)            # signed Δ²
        if not c2:
            continue
        runaway = c2[-1] > 0 and abs(track[-1] - track[0]) > 0.05   # diverging AND accelerating
        if runaway and (worst is None or c2[-1] > worst[1]):
            worst = (agent, c2[-1])
    return {
        "status": "runaway" if worst else "self_correcting",
        "regime": "no recovery guarantee" if worst else "inside basin — provably returns",
        "agent":  worst[0] if worst else None,
    }
```

This turns a tunable magic number (`0.05`) into a *signed, theorem‑backed* signal. *Traces to:*
`lyap_strictDecrease` / basin `x² < −2/c` (`OCAC/Dynamics.lean`).

---

## P3 — Neutral‑mode stability for the multi‑agent weight vector (the finding's hard part)

The finding's real content: scalarizing a vector‑valued cubic to a *signed* number needs a
**direction + covector** = the right/left eigenvectors of the *neutral mode* (eigenvalue ≈ 1 of
the Jacobian). Amagra's per‑agent weights are exactly such a vector, and current metrics collapse
them with `σ²_w` (a norm — see `instability_index` /
[`math_metrics.py:37`](evaluation/math_metrics.py#L37)).

The principled metric: find the agent‑weight direction nearest the contraction boundary (the
agent with the smallest effective `α`, i.e. `K = 1−α` closest to 1 — the slowest‑contracting,
"neutral" mode) and report its **signed** drift along that mode, not the pooled variance. This is
the one mode about to lose contraction; pooled variance can't see it.

```python
def neutral_mode_drift(alphas: dict[str, float], drifts: dict[str, float]) -> dict:
    """Project drift onto the slowest-contracting (neutral) agent mode and keep its sign."""
    agent = min(alphas, key=alphas.get)        # smallest α ⇒ K nearest 1 ⇒ neutral mode
    signed = drifts.get(agent, 0.0)            # signed, not |·|
    return {"mode": agent, "K": 1 - alphas[agent], "signed_drift": signed,
            "regime": "stabilizing" if signed < 0 else "destabilizing"}
```

Distinctive: nobody's agent dashboard reports a *signed, mode‑resolved* stability number; they
report norms or Lyapunov exponents (also sign‑folded magnitudes). *Traces to:* the scalarization
obligation of `stability_core` (direction `v` + covector `ℓ`, `OCAC/Dynamics.lean`).

---

## P4 — Apply the cubic basin to the **nonlinear** quality update

The bridge treats the *affine* weight update (global basin, trivially stable). But
`quality_update` ([`math_metrics.py:133`](evaluation/math_metrics.py#L133)) is genuinely
**nonlinear** — a logistic log‑odds map `q ← σ(σ⁻¹(q) + γδ)`. The affine theory does **not**
cover it; the *cubic* theory does. Its sigmoid has a nonzero third derivative whose **sign flips
at q = 0.5** — precisely the regime where the latest finding bites. A streaming‑feedback fixed
point near the saturated ends (`q→0` or `q→1`) has a *bounded* basin, not a global one.

Improvement: expose `quality_update_basin(q, gamma)` reporting whether the current quality sits in
the contracting region, so noisy feedback near saturation can't silently push a memory's quality
into a non‑recoverable corner. This is the first place in Amagra where the *cubic* (not affine)
OCAC result is the correct tool. *Traces to:* `lyap_strictDecrease_radius` (bounded basin) +
`cubicCoeff_neg_iff` (sign‑dependent stability).

---

## P5 — Close the two items the bridge left open

From [`OCAC_STABILITY_BRIDGE.md`](docs/OCAC_STABILITY_BRIDGE.md) §5 "Still open":

- **Convolution chain bound.** `chain_error_bound` is a plain product of independent per‑step
  factors. Tighten it to the OCAC *convolution* form `convolution_dominated`
  (`ρ = B·M²/(M−L)`) for **depth‑dependent coupling** — the realistic case where an agent's
  output feeds the next agent's input (orchestration / self‑recursion), so steps are *not*
  independent. Add `chain_error_bound_convolution(...)` alongside the existing product form.
- **Continuous reflection depth.** `reflect_level ∈ {none, light, full}` is the discrete 0/½/1
  case of OCAC's `H_{1.5}` half‑iterate. If a graded `reflect_level ∈ (0,1)` is ever wanted, the
  squeeze `id < φ < exp` (`lt_phi`/`phi_lt_exp`) gives free, exact bounds on a fractional pass.
  Low priority until graded depth is actually needed.

---

## P6 — Finish the honesty taxonomy (provenance on *every* metric)

The bridge fixed two fabricated‑axiom cases (`routing_accuracy` source tag, `C_quality`
decoupling). Make it systematic: every number in `hierarchical_metrics`
([`infrastructure/metrics_engine.py`](infrastructure/metrics_engine.py)) carries a
`*_source ∈ {measured, proxy, assumed_constant}` field, mirroring OCAC's
PROVED / PROOF‑GAP / DEFINITION‑GAP tagging. Today only `routing_accuracy` has it. A dashboard
that mixes measured and assumed numbers without labels is the exact thing the OCAC method exists
to prevent.

---

## Suggested order

| # | Change | File | Effort | Why now |
|---|--------|------|--------|---------|
| P1 | Signed curvature indicator | `math_metrics.py` | ~30 min | Pure fn + self‑test; fixes a live sign‑loss bug in the alarm |
| P2 | Lens‑of‑Stability `drift_status` | `decision/weights.py` | ~1 h | Kills the `0.05` magic number; adds a recovery guarantee |
| P6 | Provenance tags | `metrics_engine.py` | ~1 h | Cheap, finishes a started job, high trust payoff |
| P4 | Cubic basin for quality update | `math_metrics.py` | ~1–2 h | First correct use of the *nonlinear* OCAC result |
| P3 | Neutral‑mode signed drift | `decision/weights.py` | exploratory | The publishable, distinctive metric |
| P5 | Convolution chain bound | `math_metrics.py` | research | Tightens deep‑orchestration guarantees |

Every item is a **pure additive function with a self‑test** (the established pattern in
`math_metrics.py`), so each lands behind the existing suite with zero risk to routing/memory.
The through‑line is one sentence from the latest finding: **put the sign back.**
