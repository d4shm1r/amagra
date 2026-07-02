# Metrics Improvement Roadmap — phased, execution-ready

*Derived from [`improvements.md`](IMPROVEMENTS.md) and the latest OCAC finding (signed
cubic / "put the sign back"). Each phase is self-contained, additive, and gated behind the
existing test suite. Ship phases in order; each ends green before the next starts.*

**Working rule:** every new metric is a **pure function with a self-test** in
[`evaluation/math_metrics.py`](../../evaluation/math_metrics.py) first, then wired into its consumer.
No consumer change ships without its pure function already merged and tested.

---

## Phase 0 — Baseline & guardrails *(pre-work, ~15 min)*

- [ ] **0.1** Run the current suite green: `PYTHONPATH=. python3 -m pytest tests/ -q`.
- [ ] **0.2** Run the metric self-tests: `python3 evaluation/math_metrics.py` → "all tests passed ✓".
- [ ] **0.3** Snapshot current dashboard numbers (`GET /telemetry/routing`, `hierarchical_metrics()`)
      to a scratch file — the before/after reference for "no regression."
- **Exit:** both suites green, baseline captured.

---

## Phase 1 — Signed curvature indicator *(P1 · ~30 min · pure fn)*

Fixes the `abs()` sign-loss in `max_abs_curvature`.

- [ ] **1.1** Add `curvature_leading_indicator(series)` to `math_metrics.py` (returns
      `{signed_peak, regime, warn}`; `regime ∈ {downturn, rebound, linear, flat}`).
- [ ] **1.2** Self-tests: signed peak < 0 on a high-level downturn `[0.9,0.9,0.9,0.6]`;
      > 0 on a rebound `[0.6,0.6,0.6,0.9]`; `warn` True only when `signed_peak < 0 and last > 0.7`;
      `[]`-safe on series shorter than 3.
- [ ] **1.3** Keep `max_abs_curvature` as-is (back-compat); add a one-line docstring note that the
      signed variant is the alarm of record.
- [ ] **1.4** Wire into `cognition/coherence.py print_dynamics` and the UCI curvature alarm in
      `metrics_engine.py` (`uci_curvature`) so the dashboard alarm uses the signed regime.
- **Exit:** `python3 evaluation/math_metrics.py` green; dashboard shows downturn vs. rebound
  distinctly on the snapshot series.

---

## Phase 2 — Lens-of-Stability `drift_status` *(P2 · ~1 h)*

Replaces the `variance > 0.05` magic number with a signed test + basin recovery guarantee.

- [ ] **2.1** Pure fn `drift_status_v2(weight_history: dict[str, list[float]])` in `math_metrics.py`
      → `{status, regime, agent}` using `series_curvature` (signed Δ²) + divergence check.
- [ ] **2.2** Self-tests: self-correcting track (curving back) ⇒ `status="self_correcting"`;
      diverging+accelerating track ⇒ `status="runaway"` with the right `agent`; empty/short-safe.
- [ ] **2.3** In `decision/weights.py`, have `drift_status()` call the pure fn off the per-agent
      weight history; **keep the old variance field** in the return dict for back-compat, add the
      new `regime`/`status` keys.
- [ ] **2.4** Confirm no caller breaks: `grep -rn "drift_status" --include=*.py .` and check each
      consumer reads only existing keys or the additive ones.
- **Exit:** suite green; `drift_status()` returns both the legacy variance and the signed verdict.

---

## Phase 3 — Provenance tags on every metric *(P6 · ~1 h)*

Finishes the honesty taxonomy already started for `routing_accuracy`.

- [ ] **3.1** Define the vocabulary once: `source ∈ {"measured", "proxy", "assumed_constant"}`.
- [ ] **3.2** In `metrics_engine.py hierarchical_metrics()`, attach `<name>_source` to each pillar
      input (reliability/intelligence/adaptation/productivity sub-terms), mirroring the existing
      `lrn_routing_accuracy_source` pattern.
- [ ] **3.3** Add a `provenance` summary block to the returned dict: counts of each source kind, so
      a UI can show "3 measured · 2 proxy · 1 assumed."
- [ ] **3.4** Test: assert every numeric pillar input has a matching `_source`; assert no value
      tagged `measured` is a hardcoded constant (grep guard in a test).
- **Exit:** suite green; no number in the stack can masquerade as measured without a tag.

---

## Phase 4 — Cubic basin for the nonlinear quality update *(P4 · ~1–2 h)*

First correct use of the *cubic* (not affine) OCAC result.

- [ ] **4.1** Pure fn `quality_update_basin(q, gamma, delta_f)` in `math_metrics.py` → reports
      whether `q` sits in the contracting region of the logistic log-odds map and the distance to
      the saturation corners.
- [ ] **4.2** Self-tests: mid-range `q≈0.5` ⇒ in-basin; near-saturation `q≈0.98` with negative
      streaming feedback ⇒ flagged "approaching non-recoverable corner"; monotonic distance.
- [ ] **4.3** Wire as an advisory in the memory quality path (where `quality_update` is called) —
      log a warning event when a memory's quality leaves the basin; **do not** block the update.
- **Exit:** suite green; saturation-corner warnings appear in the event log on synthetic noisy
  feedback, absent on healthy feedback.

---

## Phase 5 — Neutral-mode signed drift *(P3 · exploratory)*

The distinctive, publishable metric — the finding's direction+covector applied to agent weights.

- [ ] **5.1** Pure fn `neutral_mode_drift(alphas, drifts)` in `math_metrics.py` → identifies the
      slowest-contracting agent mode (smallest α ⇒ K nearest 1) and reports its **signed** drift.
- [ ] **5.2** Self-tests: picks the min-α agent; sign preserved; `regime ∈ {stabilizing,
      destabilizing}` matches the drift sign.
- [ ] **5.3** Surface as a new telemetry field (`GET /telemetry/routing` or a metrics panel):
      "neutral mode: <agent>, K=…, signed_drift=…".
- [ ] **5.4** Validate on real logs: does the flagged mode correspond to the agent with the most
      volatile weight track over the last N sessions?
- **Exit:** suite green; neutral-mode call agrees with observed weakest-mode on live data.

---

## Phase 6 — Deep-orchestration bounds *(P5 · research)*

- [ ] **6.1** `chain_error_bound_convolution(eps0, step_factors, coupling)` — the OCAC convolution
      form (`ρ = B·M²/(M−L)`) for depth-dependent coupling, alongside the existing product form.
- [ ] **6.2** Self-tests vs. the independent-product case (must agree when coupling = 0).
- [ ] **6.3** *(defer)* Continuous `reflect_level ∈ (0,1)` using the `id < φ < exp` squeeze —
      only if graded reflection depth is actually wanted.
- **Exit:** suite green; convolution bound ≥ product bound under positive coupling.

---

## Cross-cutting acceptance criteria

1. **No regression:** `pytest tests/ -q` (889) + `math_metrics.py` self-tests green after every phase.
2. **Additive only:** no existing metric key removed or renamed; all new outputs are extra keys.
3. **Traceable:** each new function's docstring names the OCAC theorem it derives from
   (`lyap_strictDecrease`, `cubicCoeff_neg_iff`, `Delta_secondDiff`, `convolution_dominated`, …).
4. **One sentence of intent in every PR:** "put the sign back" / "basin not threshold" / "tag the
   provenance" — the phase's thesis, so review stays anchored.

## Dependency order

```
Phase 0 ─► Phase 1 ─► Phase 2 ─┐
                               ├─► (independent) Phase 3
                               ├─► Phase 4
                               └─► Phase 5 ─► Phase 6
```

Phases 1→2 share the signed-`Δ²` primitive (do 1 first). Phase 3 is independent and can run in
parallel. Phases 4–6 build on the Phase 1 curvature work but not on each other.
