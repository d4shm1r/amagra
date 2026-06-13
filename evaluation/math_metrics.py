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
