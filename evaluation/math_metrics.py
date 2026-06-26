"""
math_metrics.py
───────────────────────────────────────────────────────────────
Pure mathematical functions from the system's research paper.

No side effects. No I/O. No LLM calls. No DB access.
Every function references the equation number in the paper for traceability.

Usage:
    from math_metrics import pass_at_k, critic_calibration, routing_entropy
    from math_metrics import adaptive_alpha, domain_confidence, quality_update
    from math_metrics import cognition.coherence as coherence

Run this file directly to execute all self-tests:
    python3 math_metrics.py
"""

import math


# ────────────────────────────────────────────────────────────────
# § Learning kernel  (Paper Eq. 1–4)
# ────────────────────────────────────────────────────────────────

def learning_signal(p: float, r: float) -> float:
    """L = p − 0.5·r  (Eq. 1)

    p: response performance ∈ [0, 1]
    r: routing regret = max(alt_confidences) − chosen_confidence ∈ [0, 1]

    Positive L → agent deserves a weight boost.
    Negative L → agent produced a poor response or was the wrong choice.
    """
    return p - 0.5 * r


def instability_index(r: float, cal_error: float, weight_var: float) -> float:
    """I = 0.4·r + 0.4·|cal_error| + 0.2·σ²_w  (Eq. 2)

    r:          routing regret ∈ [0, 1]
    cal_error:  |avg_confidence − avg_performance| per agent, averaged across agents
    weight_var: cross-agent weight variance σ²_w

    I → 0  means stable, well-calibrated system → large learning steps allowed.
    I → 1  means turbulent → learning rate approaches zero (no over-correction).
    """
    return 0.4 * r + 0.4 * abs(cal_error) + 0.2 * weight_var


def adaptive_alpha(I: float, alpha0: float = 0.15, k: float = 8.0) -> float:
    """α(I) = α₀ / (1 + exp(k·(I − 0.5)))  (Eq. 3)

    C1-smooth adaptive learning rate. Replaces the original step function.
    At I = 0.5: α = α₀/2 exactly.
    As I → 1:  α → 0 continuously (no hard cutoff).
    As I → 0:  α → α₀.

    I:      instability index ∈ [0, 1]
    alpha0: base learning rate (default 0.15 — half that of original 0.30)
    k:      steepness of the sigmoid gate (default 8.0)
    """
    return alpha0 / (1.0 + math.exp(k * (I - 0.5)))


def weight_delta(alpha: float, L: float, w: float,
                 clip_lo: float = -0.02, clip_hi: float = 0.02) -> float:
    """Δw = clip(α·(L − w), −0.02, +0.02)  (Eq. 4)

    alpha: adaptive learning rate from adaptive_alpha()
    L:     learning signal from learning_signal()
    w:     current agent weight ∈ [0, 1]
    """
    return max(clip_lo, min(clip_hi, alpha * (L - w)))


# ────────────────────────────────────────────────────────────────
# § Domain confidence  (Paper Eq. 8)
# ────────────────────────────────────────────────────────────────

def domain_confidence(k: int) -> float:
    """c(k) = 1 − exp(−0.40·k)  (Eq. 8)

    k: number of keyword matches in the query.

    Replaces the original c = min(1.0, k × 0.35) which hard-capped at three
    matches and collapsed all high-confidence queries to the same value.
    This function is strictly increasing and never reaches 1.0 in IEEE-754
    double precision for k ≤ 99 (saturates to 1.0 at k = 100).

    k=1 → 0.330  (above routing threshold θ = 0.30)
    k=2 → 0.551
    k=3 → 0.699
    """
    return 1.0 - math.exp(-0.40 * k)


# ────────────────────────────────────────────────────────────────
# § Retrieval score  (Paper Eq. 9)
# ────────────────────────────────────────────────────────────────

# Type weights τ — reflection and failure memories surface more readily
# because they encode corrective information.
_TYPE_WEIGHTS: dict[str, float] = {
    "reflection": 1.4,
    "failure":    1.3,
    "code":       1.2,
    "episodic":   1.1,
    "lesson":     1.1,
}

def retrieval_score(cos_sim: float, quality: float,
                    mem_type: str = "code",
                    age_days: float = 0.0) -> float:
    """score(q, m) = cos(e_q, e_m) · q_m · τ_{type(m)} · exp(−Δt · ln2 / 30)  (Eq. 9)

    cos_sim:  cosine similarity between query and memory embeddings ∈ [0, 1]
    quality:  memory quality score q_m ∈ [0, 1]
    mem_type: memory type key (see _TYPE_WEIGHTS; unknown types → τ = 1.0)
    age_days: record age in days — 30-day half-life exponential decay

    The decay term means a 30-day-old memory contributes half the score of a
    new one with the same content; a 90-day-old memory contributes one-eighth.
    """
    tau   = _TYPE_WEIGHTS.get(mem_type, 1.0)
    decay = math.exp(-age_days * math.log(2) / 30.0)
    return cos_sim * quality * tau * decay


# ────────────────────────────────────────────────────────────────
# § Quality log-odds update  (Paper Eq. 10)
# ────────────────────────────────────────────────────────────────

def quality_update(q: float, delta_f: float, gamma: float = 4.0) -> float:
    """Bayesian quality update in log-odds space  (Eq. 10)

    l_new = l + γ·δ_f
    q_new = σ(l_new)

    q:       current quality ∈ (0, 1)
    delta_f: feedback signal  (+0.03 for 👍 / −0.05 for 👎)
    gamma:   scale factor that maps probability-space deltas to log-odds space

    Resistance property: a memory at q = 0.9 responds four times less to the
    same δ_f than one at q = 0.5, preventing isolated noise from degrading
    high-quality memories.

    Returns updated quality ∈ (0, 1).
    """
    q = max(1e-9, min(1.0 - 1e-9, q))     # keep log well-defined
    l_old = math.log(q / (1.0 - q))
    l_new = l_old + gamma * delta_f
    return 1.0 / (1.0 + math.exp(-l_new))


def quality_update_basin(q: float, gamma: float = 4.0, delta_f: float = 0.0,
                         *, saturation: float = 0.9) -> dict:
    """Is q in the contracting region of the *nonlinear* quality update?

    ``quality_update`` is the logistic log-odds map ``q ← σ(σ⁻¹(q) + γδ)``. The
    affine weight theory (global basin) does **not** cover it; the *cubic* theory
    does. The sigmoid's responsiveness ``σ'(q) = q(1−q)`` collapses toward the
    saturated ends, and its second derivative ``σ''(q) = q(1−q)(1−2q)`` flips sign
    at ``q = 0.5`` (convex below, concave above). So a fixed point near a corner
    (``q→0`` or ``q→1``) sits in a **bounded** basin, not a global one: the same
    ``q(1−q)`` factor that resists noise also resists *recovery* once a memory is
    pushed into the corner — corrective feedback can't pull it back out.

    Reports:
      ``responsiveness``  σ'(q) = q(1−q) — local sensitivity to a log-odds shift
      ``corner_distance`` min(q, 1−q) — monotonic distance to the nearest corner
      ``regime``          convex / concave / inflection (sign of σ'')
      ``in_basin``        True while q stays inside the interior contracting band
                          [1−saturation, saturation]
      ``corrective_feedback`` True when δ points back toward 0.5 (trying to recover)
      ``projected_step``  q_next − q under one update with ``delta_f``
      ``warn``            not in_basin — quality has entered the bounded corner

    Traces to: ``lyap_strictDecrease_radius`` (bounded basin) + ``cubicCoeff_neg_iff``
    (sign-dependent stability).
    """
    q = max(1e-9, min(1.0 - 1e-9, q))
    responsiveness  = q * (1.0 - q)
    corner_distance = min(q, 1.0 - q)
    sigma2 = responsiveness * (1.0 - 2.0 * q)
    regime = ("convex" if sigma2 > 0
              else "concave" if sigma2 < 0
              else "inflection")
    in_basin   = corner_distance >= (1.0 - saturation)
    q_next     = quality_update(q, delta_f, gamma)
    corrective = (q > 0.5 and delta_f < 0) or (q < 0.5 and delta_f > 0)
    return {
        "responsiveness":      round(responsiveness, 6),
        "corner_distance":     round(corner_distance, 6),
        "regime":              regime,
        "in_basin":            in_basin,
        "corrective_feedback": corrective,
        "projected_step":      round(q_next - q, 6),
        "warn":                not in_basin,
    }


# ────────────────────────────────────────────────────────────────
# § Coherence C(t)  (Paper Eq. 11–14)
# ────────────────────────────────────────────────────────────────

def coherence_routing(conflict_count: int, window_size: int) -> float:
    """C_routing(t) = 1 − |{d ∈ W_t : conflict(d)}| / |W_t|  (Eq. 12)

    conflict_count: number of brain/router disagreements in the window
    window_size:    total decisions in the window (w = 20 default)
    """
    if window_size == 0:
        return 1.0
    return 1.0 - conflict_count / window_size


def coherence_calib(agent_cal_errors: list[float]) -> float:
    """C_calib(t) = 1 − (1/|A|) · Σ_a |ĉ(a,t) − p̄(a,t)|  (Eq. 13)

    agent_cal_errors: list of |avg_confidence − avg_performance| per agent.
    Perfect calibration → all errors = 0 → C_calib = 1.
    """
    if not agent_cal_errors:
        return 1.0
    return max(0.0, 1.0 - sum(abs(e) for e in agent_cal_errors) / len(agent_cal_errors))


def coherence_quality(quality_scores: list[float]) -> float:
    """C_quality(t) = (1/|W_t|) · Σ_{d ∈ W_t} q(d)  (Eq. 14)

    quality_scores: per-decision quality proxy (reflection score or 0.75/0.55 proxy).
    """
    if not quality_scores:
        return 0.75
    return sum(quality_scores) / len(quality_scores)


def coherence(conflict_count: int, window_size: int,
              agent_cal_errors: list[float],
              quality_scores: list[float]) -> dict:
    """C(t) = (1/3)·[C_routing(t) + C_calib(t) + C_quality(t)]  (Eq. 11)

    Returns a dict with all three components and the composite score.
    All values ∈ [0, 1]; C(t) = 1 represents perfect coherence.

    Thresholds used in the UI:
        C ≥ 0.82 → green (healthy)
        C ≥ 0.70 → yellow (watchable)
        C < 0.70 → red (degraded)
    """
    c_rt = coherence_routing(conflict_count, window_size)
    c_ca = coherence_calib(agent_cal_errors)
    c_ql = coherence_quality(quality_scores)
    composite = (c_rt + c_ca + c_ql) / 3.0
    return {
        "C_routing": round(c_rt, 4),
        "C_calib":   round(c_ca, 4),
        "C_quality": round(c_ql, 4),
        "C":         round(composite, 4),
    }


# ────────────────────────────────────────────────────────────────
# § Routing entropy  (Paper §2.4)
# ────────────────────────────────────────────────────────────────

def routing_entropy(probs: dict[str, float]) -> float:
    """H(q) = −Σ_{a ∈ A} p(a|q) · log₂ p(a|q)

    Measures routing uncertainty over the agent set.
    H = 0        → deterministic routing (only one agent gets any probability)
    H = log₂|A| → maximum uncertainty (uniform over all agents)

    probs: dict mapping agent_name → probability ∈ [0, 1] (must sum to 1)
    """
    h = 0.0
    for p in probs.values():
        if p > 0.0:
            h -= p * math.log2(p)
    return round(h, 4)


def routing_entropy_from_scores(scores: dict[str, float]) -> float:
    """Routing entropy from raw keyword/confidence scores (normalised via L1).

    Converts raw scores to a probability simplex, then calls routing_entropy().
    scores: dict mapping agent_name → unnormalised score ≥ 0
    """
    total = sum(scores.values())
    if total == 0.0:
        n = len(scores)
        return round(math.log2(n) if n > 1 else 0.0, 4)
    probs = {k: v / total for k, v in scores.items()}
    return routing_entropy(probs)


def max_routing_entropy(n_agents: int) -> float:
    """H_max = log₂(|A|) — upper bound for uniform routing over n agents."""
    return math.log2(n_agents) if n_agents > 1 else 0.0


# ────────────────────────────────────────────────────────────────
# § Pass@k estimator  (Chen et al. 2021, used in benchmark_eval)
# ────────────────────────────────────────────────────────────────

def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased Pass@k estimator (Chen et al. 2021 / OpenAI Codex paper).

    P(@k) = 1 − ∏_{i=0}^{k−1} (n−c−i) / (n−i)

    n: total samples generated per problem
    c: number of those samples that pass all tests
    k: number of samples to pick from (k ≤ n)

    Edge cases:
        n = k  → degenerates to c/n (fraction correct)
        c = 0  → 0.0  (no correct sample exists)
        c ≥ k  → 1.0  (guaranteed to pick at least one correct)
        n < k  → ValueError

    Why this estimator?  Generating n samples and testing all of them is
    expensive.  This formula gives an unbiased estimate of the probability
    that at least one of k randomly chosen samples would pass, using all n
    test results rather than just c/n.
    """
    if k > n:
        raise ValueError(f"k ({k}) cannot exceed n ({n})")
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.prod((n - c - i) / (n - i) for i in range(k))


# ────────────────────────────────────────────────────────────────
# § Critic calibration  (ECE + Brier)
# ────────────────────────────────────────────────────────────────

def critic_calibration(scores: list[float], labels: list[bool],
                       n_bins: int = 5) -> dict:
    """Calibration analysis for the critic gate (grounded_evaluate scores).

    A well-calibrated critic has score ≈ P(code passes tests).
    Miscalibration means either:
      - High ECE: scores don't predict correctness (gate is unreliable)
      - High Brier: large average squared error between score and outcome

    scores: grounded_evaluate scores ∈ [0, 1] for each generated code sample
    labels: True if the sample passed all tests, False otherwise
    n_bins: number of equal-width bins for ECE (default 5: [0,.2), [.2,.4), ...)

    Returns:
        ece:            Expected Calibration Error ∈ [0, 1]  (lower = better)
        brier:          Brier score ∈ [0, 1]                 (lower = better)
        mean_score:     average critic score
        accuracy:       fraction of samples that actually passed
        overconfident:  True if mean_score > accuracy (critic overpredicts correctness)
        n:              sample count
        bins:           per-bin breakdown for debugging
    """
    if not scores or len(scores) != len(labels):
        return {"ece": None, "brier": None, "n": 0}

    n = len(scores)
    int_labels = [int(l) for l in labels]

    brier = sum((s - y) ** 2 for s, y in zip(scores, int_labels)) / n

    # ECE: partition [0,1] into n_bins equal-width intervals
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for s, y in zip(scores, int_labels):
        b = min(int(s * n_bins), n_bins - 1)
        bins[b].append((s, y))

    ece = 0.0
    bin_details = []
    for b, bdata in enumerate(bins):
        if not bdata:
            continue
        bin_conf = sum(s for s, _ in bdata) / len(bdata)
        bin_acc  = sum(y for _, y in bdata) / len(bdata)
        weight   = len(bdata) / n
        ece     += weight * abs(bin_conf - bin_acc)
        bin_details.append({
            "bin":      b,
            "lo":       round(b / n_bins, 2),
            "hi":       round((b + 1) / n_bins, 2),
            "count":    len(bdata),
            "mean_conf": round(bin_conf, 3),
            "accuracy": round(bin_acc, 3),
            "gap":      round(abs(bin_conf - bin_acc), 3),
        })

    mean_score = sum(scores) / n
    accuracy   = sum(int_labels) / n

    return {
        "ece":          round(ece, 4),
        "brier":        round(brier, 4),
        "mean_score":   round(mean_score, 4),
        "accuracy":     round(accuracy, 4),
        "overconfident": mean_score > accuracy,
        "n":            n,
        "n_bins":       n_bins,
        "bins":         bin_details,
    }


# ────────────────────────────────────────────────────────────────
# § OCAC stability bridge  (contraction fixed-point framing)
# ────────────────────────────────────────────────────────────────
# The learning update  w ← (1−α)·w + α·L  (learning.py) is an affine
# contraction toward the fixed point w* = L with Lipschitz modulus
# K = 1−α.  This is exactly the parametrised fixed-point family of the
# OCAC "H theorem" Lean development (Engine A, axiom A2 = uniform
# contraction).  The functions below expose the *proved* consequences of
# that structure as live, computable stability numbers.
#
# References (OCAC Lean source, ~/Desktop/lean):
#   A2 contraction        — OCAC/Basic.lean
#   resolvent bound       — OCAC/DerivativeRecursion.lean (norm_resolvent_le)
#   Lyapunov decrease     — OCAC/Dynamics.lean (lyap_strictDecrease)
#   curvature / 2nd-diff  — OCAC/Variational.lean (Delta_secondDiff)

def effective_contraction(alpha: float) -> float:
    """K = 1 − α  — Lipschitz modulus of the affine weight update.

    The update w ← (1−α)w + αL contracts toward w* = L iff K < 1, i.e.
    α > 0.  Stability is guaranteed precisely while this stays below 1
    (OCAC axiom A2).  α is the output of adaptive_alpha(); the freeze at
    α≈0 in learning.py is the boundary K→1 where contraction is lost.
    """
    return 1.0 - alpha


def resolvent_bound(alpha: float) -> float:
    """‖R‖ ≤ (1−K)⁻¹ = 1/α  — sensitivity of the converged weight.

    OCAC's Neumann resolvent bound (norm_resolvent_le): a perturbation δ
    in the learning signal L moves the converged weight w* by at most
    (1/α)·δ.  Large 1/α (small α) → the fixed point is stiff/insensitive
    (slow but stable); small 1/α (large α) → responsive but jumpy.
    Returns +inf when α = 0 (frozen: infinitely sensitive / no contraction).
    """
    if alpha <= 0.0:
        return float("inf")
    return 1.0 / alpha


def affine_lyapunov_decay(alpha: float) -> dict:
    """Exact Lyapunov decrease for the affine update (OCAC P1 analogue).

    With energy V(w) = (w − w*)², one step gives the *exact* increment
        V(w') − V(w) = −α(2−α)·V(w),
    so V decays by the factor (1−α)² each step.  Strictly negative for
    α ∈ (0, 2) → global contraction (basin = all of weight space), the
    affine counterpart of OCAC's lyap_strictDecrease (which gives a
    *bounded* basin x² < −2/c for the cubic normal form).

    Returns {decay_factor, delta_coeff, contracts}.
    """
    decay_factor = (1.0 - alpha) ** 2          # V' = decay_factor · V
    delta_coeff  = -alpha * (2.0 - alpha)      # ΔV = delta_coeff · V
    return {
        "decay_factor": round(decay_factor, 6),
        "delta_coeff":  round(delta_coeff, 6),
        "contracts":    0.0 < alpha < 2.0,
    }


def instability_conjunctive(r: float, cal_error: float,
                            weight_var: float) -> float:
    """Soft-OR instability  I = 1 − ∏(1 − tᵢ)  (OCAC A1∧A2∧A3 form).

    OCAC proves the three stability conditions A1 (smoothness ↔ regret),
    A2 (contraction ↔ weight variance) and A3 (bounded sensitivity ↔
    calibration error) are each *individually necessary* — each has its
    own counterexample.  They are therefore conjunctive: the system is
    stable only if all three hold.  A weighted average (instability_index)
    lets one healthy term mask a failing one; this soft-OR spikes to ~1 as
    soon as *any* single term degrades, matching the proved necessity.

    Drop-in alternative to instability_index() for the adaptive_alpha gate.
    """
    t_r  = min(max(r, 0.0), 1.0)
    t_c  = min(max(abs(cal_error), 0.0), 1.0)
    t_w  = min(max(weight_var, 0.0), 1.0)
    return 1.0 - (1.0 - t_r) * (1.0 - t_c) * (1.0 - t_w)


def series_curvature(series: list[float]) -> list[float]:
    """Discrete second difference  Δ²xₙ = xₙ₊₁ − 2xₙ + xₙ₋₁.

    OCAC's Delta_secondDiff: curvature is a second-order signal the flat
    level-and-rate metrics miss.  Applied to a coherence/UCI time series it
    measures the *acceleration* of change — a leading indicator of
    instability (a large negative Δ² while the level is still high warns of
    an incipient downturn before the level itself drops).

    Returns a list of length max(0, len(series) − 2), aligned to interior
    points (curvature[i] corresponds to series[i+1]).
    """
    if len(series) < 3:
        return []
    return [round(series[i + 1] - 2.0 * series[i] + series[i - 1], 6)
            for i in range(1, len(series) - 1)]


def max_abs_curvature(series: list[float]) -> float:
    """Peak |Δ²| over a series — single-number instability leading indicator.

    0.0 for a perfectly linear (constant-rate) trajectory; grows with how
    sharply the metric is bending.  Useful as a dashboard alarm threshold.

    NOTE: this folds away the sign of Δ², so an incipient downturn and a
    recovery overshoot collapse to the same number.  For the dashboard alarm
    use ``curvature_leading_indicator`` (the signed alarm of record); this
    magnitude form is retained for back-compat only.
    """
    curv = series_curvature(series)
    return round(max((abs(c) for c in curv), default=0.0), 6)


def curvature_leading_indicator(series: list[float]) -> dict:
    """Signed Δ² alarm — keeps the sign the OCAC cubic finding says is load-bearing.

    ``max_abs_curvature`` collapses the curvature through ``abs``, so a downturn
    and a rebound become indistinguishable.  This keeps the sign: the second
    difference is *negative* when a series is bending downward (concave) and
    *positive* when bending upward (convex).  A negative peak while the level is
    still high is the incipient-downturn alarm the OCAC bridge §4.1 wants;
    a positive peak is a self-correcting rebound (safe).

    Returns ``{signed_peak, regime, warn}`` where
    ``regime ∈ {downturn, rebound, linear, flat}`` and ``warn`` is True only
    when the series is bending down from a high level (``signed_peak < 0`` and
    the latest value > 0.7).

    Traces to: ``Delta_secondDiff`` (OCAC/Variational.lean) + the sign lesson of
    ``cubicCoeff_neg_iff`` — a norm erases the attractor/repeller distinction.
    """
    curv = series_curvature(series)
    if not curv:
        return {"signed_peak": 0.0, "regime": "flat", "warn": False}
    signed_peak = max(curv, key=abs)            # largest |Δ²|, sign preserved
    regime = ("downturn" if signed_peak < 0
              else "rebound" if signed_peak > 0
              else "linear")
    return {
        "signed_peak": round(signed_peak, 6),
        "regime": regime,
        "warn": signed_peak < 0 and series[-1] > 0.7,   # bending down from a high level
    }


def drift_status_v2(weight_history: dict, *, divergence_eps: float = 0.05) -> dict:
    """Signed lens-of-stability verdict on per-agent weight tracks.

    Replaces the sign-blind ``variance > 0.05`` cutoff in ``decision.weights``.
    Variance cannot tell a cluster *converging* to a new stable configuration
    from a cluster *diverging* — both can show the same spread. This asks two
    signed questions of each agent's weight track instead:

      1. **Direction** — is the weight diverging from where the track started by
         more than ``divergence_eps``? (Inside that radius it is in the recovery
         basin; nothing to flag.)
      2. **Curvature sign** — is the latest signed Δ² accelerating the excursion
         *away* from the start (same sign as the drift ⇒ runaway) or curving it
         *back* toward the start (opposite sign ⇒ self-correcting)?

    A track is ``runaway`` only when it is **both** diverging **and**
    accelerating away. Note this is sign-relative to the drift direction, so it
    catches downward divergence too — a plain ``Δ² > 0`` test would miss a weight
    collapsing toward the lower bound.

    Returns ``{status, regime, agent, signed_accel}`` where
    ``status ∈ {runaway, self_correcting}``, ``agent`` is the worst runaway agent
    (or None), and ``signed_accel`` is that agent's away-acceleration.

    Traces to: ``lyap_strictDecrease`` / basin ``x² < −2/c`` (OCAC/Dynamics.lean).
    """
    worst = None   # (agent, away_accel)
    for agent, track in weight_history.items():
        c2 = series_curvature(track)
        if not c2:
            continue                               # track too short
        drift = track[-1] - track[0]
        if abs(drift) <= divergence_eps:
            continue                               # inside basin — not diverging
        # away_accel > 0 ⇒ Δ² reinforces the drift direction (accelerating away)
        away_accel = c2[-1] * (1.0 if drift > 0 else -1.0)
        if away_accel > 0 and (worst is None or away_accel > worst[1]):
            worst = (agent, away_accel)
    return {
        "status": "runaway" if worst else "self_correcting",
        "regime": ("no recovery guarantee — diverging and accelerating away"
                   if worst else "inside basin — provably returns"),
        "agent":  worst[0] if worst else None,
        "signed_accel": round(worst[1], 6) if worst else 0.0,
    }


# ────────────────────────────────────────────────────────────────
# § Coordinate-invariant health  (OCAC Δ-invariant / 𝒞 = C/(det J)³)
# ────────────────────────────────────────────────────────────────
# UCI is a weighted arithmetic mean with hand-picked weights, so its numeric
# value is coordinate-dependent: rescale a component or re-pick the weights and
# the number shifts meaning. OCAC's lesson (normalizedCubic_invariant,
# Delta_secondDiff) is that a trustworthy structural metric should be invariant
# under admissible reparametrisation. The quantities below are weight-invariant
# (floor, spread) or scale-invariant (balance), so they mean the same thing
# across system versions and weighting choices.

def invariant_health(components: dict) -> dict:
    """Weight/scale-invariant health summary of the UCI component scores.

    components: {name: score} with each score ≥ 0 (e.g. reliability, capability,
                efficiency, learning).

    Returns:
      floor    — min component: the bottleneck. Weight-invariant (a system is
                 only as healthy as its weakest pillar; no weighting can hide it).
      spread   — max − min: imbalance across pillars. Weight-invariant.
      geomean  — geometric mean: collapses toward 0 if ANY pillar is near 0,
                 unlike the arithmetic mean which lets strong pillars mask a weak
                 one. Far more robust to the weight choice.
      balance  — geomean / arithmetic_mean ∈ (0, 1]. = 1 iff all pillars equal.
                 This is the OCAC-style invariant: scale a component by a and both
                 GM and AM pick up the same factor, so the ratio is unchanged. It
                 measures evenness independent of overall scale or units.
      weakest  — name of the floor pillar (where to spend effort).
    """
    if not components:
        return {"floor": 0.0, "spread": 0.0, "geomean": 0.0,
                "balance": 0.0, "weakest": None}
    items   = [(k, max(0.0, float(v))) for k, v in components.items()]
    vals    = [v for _, v in items]
    n       = len(vals)
    am      = sum(vals) / n
    prod    = 1.0
    for v in vals:
        prod *= v
    gm      = prod ** (1.0 / n)
    lo      = min(vals)
    hi      = max(vals)
    weakest = min(items, key=lambda kv: kv[1])[0]
    return {
        "floor":   round(lo, 4),
        "spread":  round(hi - lo, 4),
        "geomean": round(gm, 4),
        "balance": round(gm / am, 4) if am > 0 else 0.0,
        "weakest": weakest,
    }


# ────────────────────────────────────────────────────────────────
# § Error propagation through agent chains  (OCAC majorant engine)
# ────────────────────────────────────────────────────────────────
# OCAC's factorial-growth engine bounds how fast a perturbation compounds:
# aₙ₊₁ ≤ ρ(n+1)aₙ  ⟹  aₙ ≤ a₀·ρⁿ·n!  (factorial_majorant), and
# convolution_dominated composes per-step bounds. Each agent step has resolvent
# sensitivity (1−K)⁻¹ = 1/α (resolvent_bound); chaining N steps gives a provable
# worst-case on how a small mis-specification amplifies through deep recursion or
# multi-agent orchestration — a guarantee the orchestration layer currently lacks.

def chain_error_bound(eps0: float, step_factors: list[float]) -> float:
    """Worst-case output error after a chain of steps.

    eps0:         input perturbation / mis-specification magnitude
    step_factors: per-step amplification factors, e.g. resolvent_bound(αᵢ)=1/αᵢ
                  for each agent's learning loop, or any Lipschitz constant.

    Returns eps0·∏ factorsᵢ — the composed amplification. Factors < 1 are
    contractive (error shrinks); > 1 amplify. This is the OCAC resolvent-chain
    bound: a contraction at every step keeps the chain stable iff ∏ factors stays
    bounded.
    """
    out = eps0
    for f in step_factors:
        out *= f
    return out


def gevrey_majorant(a0: float, rho: float, n: int) -> float:
    """OCAC factorial ceiling  aₙ ≤ a₀·ρⁿ·n!  for depth-n recursion.

    The worst-case sensitivity bound when each recursion level multiplies the
    previous by ρ·(level): self-referential reasoning that accumulates context.
    Grows factorially — the formal warning that unbounded self-recursion is not
    free even under a per-step contraction.

    a0:  base (depth-0) sensitivity
    rho: per-level growth rate (ρ = B·M²/(M−L) in OCAC convolution_dominated)
    n:   recursion depth
    """
    return a0 * (rho ** n) * math.factorial(n)


def stable_recursion_depth(rho: float, ceiling: float = 100.0,
                           a0: float = 1.0, max_depth: int = 64) -> int:
    """Largest depth n with gevrey_majorant(a0, rho, n) ≤ ceiling.

    A practical "how deep can self-recursion go before the worst-case sensitivity
    bound blows past `ceiling`" — a budget for reflection / agent-chain depth.
    Returns 0 if even depth-0 already exceeds the ceiling.
    """
    depth = 0
    for n in range(0, max_depth + 1):
        if gevrey_majorant(a0, rho, n) <= ceiling:
            depth = n
        else:
            break
    return depth


# ────────────────────────────────────────────────────────────────
# § Self-tests
# ────────────────────────────────────────────────────────────────

def _run_tests():
    eps = 1e-9

    # Learning kernel
    assert abs(learning_signal(0.8, 0.1) - 0.75) < eps
    assert abs(learning_signal(0.5, 0.0) - 0.50) < eps
    assert abs(instability_index(0.0, 0.0, 0.0)) < eps
    assert abs(instability_index(1.0, 1.0, 1.0) - 1.0) < eps
    alpha_half = adaptive_alpha(0.5)
    assert abs(alpha_half - 0.15 / 2.0) < 1e-6, f"expected 0.075 got {alpha_half}"
    assert adaptive_alpha(0.0) > adaptive_alpha(1.0)
    assert abs(weight_delta(0.1, 0.0, 0.8, -0.02, 0.02) - (-0.02)) < eps   # clipped low
    assert abs(weight_delta(0.1, 1.0, 0.2, -0.02, 0.02) - 0.02)   < eps   # clipped high

    # Domain confidence
    assert domain_confidence(0) == 0.0
    c1 = domain_confidence(1)
    assert 0.30 < c1 < 0.35, f"one match should give ~0.33, got {c1}"
    assert domain_confidence(3) > domain_confidence(2) > domain_confidence(1)
    assert domain_confidence(90) < 1.0     # saturates to 1.0 at k=100 in IEEE-754
    assert domain_confidence(100) == 1.0   # confirm saturation point

    # Retrieval score
    s = retrieval_score(0.9, 0.8, "reflection", age_days=0)
    assert abs(s - 0.9 * 0.8 * 1.4) < 1e-6
    s30 = retrieval_score(1.0, 1.0, "code", age_days=30)
    assert abs(s30 - 0.5 * 1.2) < 1e-6    # 30-day half-life

    # Quality update — resistance property
    q_hi  = quality_update(0.9, -0.05)
    q_mid = quality_update(0.5, -0.05)
    assert q_hi > q_mid, "high-quality memory should resist negative feedback more"
    assert quality_update(0.5, +0.03) > 0.5
    assert quality_update(0.5, -0.05) < 0.5

    # Coherence
    ct = coherence(2, 10, [0.1, 0.0, 0.2], [0.8, 0.75, 0.9])
    assert 0.0 <= ct["C"] <= 1.0
    assert ct["C_routing"] == 0.8
    perfect = coherence(0, 10, [0.0]*6, [1.0]*10)
    assert perfect["C"] == 1.0

    # Routing entropy
    assert routing_entropy({"a": 1.0}) == 0.0
    h_uniform = routing_entropy({"a": 0.5, "b": 0.5})
    assert abs(h_uniform - 1.0) < eps
    h6 = max_routing_entropy(6)
    assert abs(h6 - math.log2(6)) < eps

    # Pass@k
    assert pass_at_k(10, 0, 1) == 0.0
    assert pass_at_k(10, 10, 1) == 1.0
    assert pass_at_k(10, 5, 1) == 0.5
    p1  = pass_at_k(10, 3, 1)
    p10 = pass_at_k(10, 3, 10)
    assert p10 > p1, "Pass@10 > Pass@1 when multiple correct samples exist"
    assert abs(pass_at_k(5, 5, 5) - 1.0) < eps

    # Critic calibration
    scores  = [0.9, 0.85, 0.3, 0.2, 0.8, 0.4]
    labels  = [True, True, False, False, True, False]
    cal = critic_calibration(scores, labels)
    assert cal["n"] == 6
    assert 0.0 <= cal["ece"] <= 1.0
    assert 0.0 <= cal["brier"] <= 1.0
    perfect_cal = critic_calibration([1.0, 0.0], [True, False])
    assert perfect_cal["ece"] == 0.0
    assert perfect_cal["brier"] == 0.0

    # OCAC stability bridge
    assert abs(effective_contraction(0.05) - 0.95) < eps
    assert resolvent_bound(0.05) == 20.0
    assert resolvent_bound(0.0) == float("inf")
    assert resolvent_bound(0.01) > resolvent_bound(0.05)   # smaller α → stiffer
    decay = affine_lyapunov_decay(0.05)
    assert decay["contracts"] is True
    assert 0.0 < decay["decay_factor"] < 1.0               # energy strictly shrinks
    assert decay["delta_coeff"] < 0.0                       # ΔV negative
    assert affine_lyapunov_decay(0.0)["delta_coeff"] == 0.0 # frozen → no decrease
    # soft-OR is conjunctive: one bad term dominates, unlike the weighted mean
    i_or  = instability_conjunctive(0.9, 0.0, 0.0)
    i_avg = instability_index(0.9, 0.0, 0.0)
    assert i_or > i_avg, "soft-OR should not let healthy terms mask a failure"
    assert abs(instability_conjunctive(0.0, 0.0, 0.0)) < eps
    assert abs(instability_conjunctive(1.0, 1.0, 1.0) - 1.0) < eps
    # curvature: zero on a straight line, nonzero on a bend
    assert series_curvature([1.0, 2.0, 3.0, 4.0]) == [0.0, 0.0]
    assert max_abs_curvature([1.0, 2.0, 3.0, 4.0]) == 0.0
    assert max_abs_curvature([0.9, 0.9, 0.9, 0.6]) > 0.0    # downturn detected
    assert series_curvature([1.0, 2.0]) == []              # too short
    # signed curvature alarm: sign is load-bearing (the OCAC "put the sign back")
    down = curvature_leading_indicator([0.9, 0.9, 0.9, 0.6])
    assert down["signed_peak"] < 0 and down["regime"] == "downturn"
    up = curvature_leading_indicator([0.6, 0.6, 0.6, 0.9])
    assert up["signed_peak"] > 0 and up["regime"] == "rebound"
    assert up["warn"] is False                             # rebound never warns
    # warn requires BOTH a downturn AND a still-high level (last > 0.7)
    high_down = curvature_leading_indicator([0.9, 0.9, 0.9, 0.8])
    assert high_down["regime"] == "downturn" and high_down["warn"] is True
    low_down = curvature_leading_indicator([0.9, 0.9, 0.9, 0.6])
    assert low_down["regime"] == "downturn" and low_down["warn"] is False  # last 0.6 ≤ 0.7
    flat = curvature_leading_indicator([1.0, 2.0])         # too short → safe default
    assert flat == {"signed_peak": 0.0, "regime": "flat", "warn": False}

    # signed drift_status: basin not threshold (the OCAC lens of stability)
    # self-correcting: diverged but the latest Δ² curves back toward neutral
    sc = drift_status_v2({"planner": [1.0, 1.1, 1.18, 1.20]})
    assert sc["status"] == "self_correcting" and sc["agent"] is None
    # runaway up: diverging AND accelerating away from start
    ru = drift_status_v2({"coder": [1.0, 1.05, 1.12, 1.22]})
    assert ru["status"] == "runaway" and ru["agent"] == "coder" and ru["signed_accel"] > 0
    # runaway down: sign-relative test catches a weight collapsing toward the floor
    rd = drift_status_v2({"critic": [1.0, 0.95, 0.88, 0.78]})
    assert rd["status"] == "runaway" and rd["agent"] == "critic"
    # not diverging: excursion inside the basin ⇒ no flag even with curvature
    nd = drift_status_v2({"a": [1.0, 1.01, 1.02, 1.03]})
    assert nd["status"] == "self_correcting"
    # empty / short tracks are safe
    assert drift_status_v2({})["status"] == "self_correcting"
    assert drift_status_v2({"a": [1.0, 1.0]})["status"] == "self_correcting"
    # picks the worst among multiple runaways
    worst = drift_status_v2({
        "mild":  [1.0, 1.03, 1.07, 1.12],   # smaller away-accel
        "sharp": [1.0, 1.02, 1.08, 1.20],   # larger away-accel
    })
    assert worst["status"] == "runaway" and worst["agent"] == "sharp"

    # cubic basin: the nonlinear quality update has a bounded (not global) basin
    mid = quality_update_basin(0.5)
    assert mid["in_basin"] and not mid["warn"] and mid["regime"] == "inflection"
    assert abs(mid["responsiveness"] - 0.25) < 1e-9   # σ' peaks at q=0.5
    # near the upper corner, corrective (negative) feedback is suppressed → warn
    corner = quality_update_basin(0.98, delta_f=-0.05)
    assert corner["warn"] and not corner["in_basin"]
    assert corner["corrective_feedback"] is True       # δ<0 tries to pull q down
    # lower corner is symmetric
    low = quality_update_basin(0.02, delta_f=0.03)
    assert low["warn"] and low["corrective_feedback"] is True
    # corner_distance is monotonic toward the saturated ends
    assert (quality_update_basin(0.5)["corner_distance"]
            > quality_update_basin(0.8)["corner_distance"]
            > quality_update_basin(0.95)["corner_distance"])
    # σ'' sign flip across the inflection
    assert quality_update_basin(0.3)["regime"] == "convex"
    assert quality_update_basin(0.7)["regime"] == "concave"
    # basin boundary is inclusive at the saturation threshold
    assert quality_update_basin(0.9)["in_basin"] is True       # corner_dist 0.1 ≥ 0.1
    assert quality_update_basin(0.91)["in_basin"] is False

    # Invariant health — balance is scale-invariant
    perfect = invariant_health({"a": 0.8, "b": 0.8, "c": 0.8})
    assert abs(perfect["balance"] - 1.0) < eps      # all equal → balance 1
    assert perfect["spread"] == 0.0
    h  = invariant_health({"a": 0.9, "b": 0.9, "c": 0.3})
    h2 = invariant_health({"a": 1.8, "b": 1.8, "c": 0.6})  # all ×2
    assert abs(h["balance"] - h2["balance"]) < 1e-6, "balance must be scale-invariant"
    assert h["floor"] == 0.3 and h["weakest"] == "c"
    assert h["geomean"] < (0.9 + 0.9 + 0.3) / 3      # GM penalises the weak pillar
    assert invariant_health({})["weakest"] is None

    # Chain error propagation
    assert chain_error_bound(1.0, []) == 1.0
    assert abs(chain_error_bound(0.1, [2.0, 3.0]) - 0.6) < 1e-9
    assert abs(chain_error_bound(1.0, [0.5, 0.5, 0.5]) - 0.125) < 1e-9  # contractive
    # Gevrey factorial ceiling
    assert gevrey_majorant(1.0, 1.0, 0) == 1.0
    assert gevrey_majorant(1.0, 1.0, 3) == 6.0               # 1·1·3!
    assert gevrey_majorant(2.0, 0.5, 4) == 2.0 * 0.5**4 * 24
    assert gevrey_majorant(1.0, 2.0, 5) > gevrey_majorant(1.0, 2.0, 4)  # grows
    # Stable depth budget
    assert stable_recursion_depth(2.0, ceiling=100.0) >= 1
    assert stable_recursion_depth(10.0, ceiling=1.0) == 0    # blows past immediately
    d_small = stable_recursion_depth(0.5, ceiling=100.0)
    d_big   = stable_recursion_depth(3.0, ceiling=100.0)
    assert d_small > d_big, "slower growth → deeper safe recursion"

    print("math_metrics: all tests passed ✓")


if __name__ == "__main__":
    _run_tests()

    # Demo: key values at a glance
    print()
    print("─── Key values ───────────────────────────────────────")
    for k in [1, 2, 3, 5]:
        print(f"  domain_confidence(k={k}): {domain_confidence(k):.4f}")
    print()
    for I in [0.0, 0.25, 0.5, 0.75, 1.0]:
        print(f"  adaptive_alpha(I={I}):   {adaptive_alpha(I):.5f}")
    print()
    for n, c, k in [(10, 5, 1), (10, 5, 2), (10, 5, 5), (10, 5, 10)]:
        print(f"  pass_at_k(n={n}, c={c}, k={k}):  {pass_at_k(n,c,k):.4f}")
    print()
    qs = [0.1, 0.5, 0.9]
    print("  quality_update resistance (δ = −0.05, γ = 4.0):")
    for q in qs:
        print(f"    q={q:.1f} → {quality_update(q, -0.05):.4f}  (Δ = {quality_update(q,-0.05)-q:+.4f})")
