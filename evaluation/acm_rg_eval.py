"""
ACM-RG Critical Structure Evaluation
======================================
Tests whether the routing system exhibits critical behavior near V ≈ 1.5,
as predicted by the ACM Renormalization Group theory.

The routing system's KEYWORD_MAP produces a score distribution over N agents
for every query. This gives a genuine probability distribution whose entropy
we can measure, bin, and use to extract critical exponents.

Measurements:
  1. V distribution   — routing entropy parameter per query and domain
  2. β exponent       — accuracy ~ |V - V_c|^β near the decision boundary
  3. G(Δℓ) and η      — two-point correlation across 4 routing scale levels
  4. Hyperscaling     — consistency check γ = ν(2 - η)

Scale levels:
  ℓ=0  max keyword fraction  (microscopic: which fraction of keywords fire?)
  ℓ=1  soft probability      (routing distribution: how confident is the router?)
  ℓ=2  domain_conf           (QuerySignal: signal-level confidence)
  ℓ=3  binary correctness    (macroscopic: right or wrong?)

Run:
    PYTHONPATH=. python3 acm_rg_eval.py
"""

import sys
import math
import re
from collections import defaultdict

import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestration.query_normalizer import normalize, DOMAIN_TO_AGENT
from orchestration.router import KEYWORD_MAP
from training.auto_train import PROMPTS


# ── Core routing utilities ────────────────────────────────────

def keyword_scores(query: str) -> dict:
    """Keyword match count per agent — the microscopic routing state."""
    q = query.lower()
    scores = {agent: 0 for agent in KEYWORD_MAP}
    for agent, patterns in KEYWORD_MAP.items():
        for pattern in patterns:
            if re.search(pattern, q, re.IGNORECASE):
                scores[agent] += 1
    return scores


def softmax(scores: dict, temperature: float = 1.0) -> dict:
    """Convert integer scores to a probability distribution."""
    agents = list(scores.keys())
    vals   = [scores[a] for a in agents]
    max_v  = max(vals) if vals else 0
    exps   = [math.exp((v - max_v) / temperature) for v in vals]
    Z      = sum(exps)
    return {a: e / Z for a, e in zip(agents, exps)}


def compute_V(scores: dict, temperature: float = 1.0) -> float:
    """
    Order-chaos parameter V ∈ [1, 2].

    V = 1 + H / H_max   where H = Shannon entropy (nats), H_max = log N.

    V = 1.0: deterministic routing (fully ordered)
    V = 1.5: half-maximal entropy (critical hypothesis)
    V = 2.0: uniform over all agents (maximally chaotic)
    """
    N     = len(scores)
    probs = softmax(scores, temperature)
    H     = -sum(p * math.log(p) for p in probs.values() if p > 1e-15)
    H_max = math.log(N)
    return 1.0 + H / H_max


def signal_route(query: str) -> str:
    """Signal-only routing — mirrors core_brain fast path, no LLM."""
    sig = normalize(query)
    if sig.answer_shape == "factual":
        return "terse"
    if sig.verbosity == "terse":
        return "terse"
    if sig.domain_conf > 0.3:
        return DOMAIN_TO_AGENT.get(sig.domain, "knowledge_learning")
    return "knowledge_learning"


def confidence_margin(scores: dict) -> float:
    """max_score - second_score: proxy for distance from decision boundary."""
    vals = sorted(scores.values(), reverse=True)
    return vals[0] - vals[1] if len(vals) >= 2 else float(vals[0])


# ── Scale representations for G(Δℓ) ─────────────────────────

_SHAPE_DISORDER = {
    "factual":     0.0,   # single concrete answer — fully determined
    "code":        0.2,   # well-defined output format
    "debug":       0.4,   # constrained by error context
    "procedural":  0.6,   # steps known but length uncertain
    "comparison":  0.7,   # structure known, content open
    "explanation": 1.0,   # most open-ended
}


def compute_V_combined(query: str) -> float:
    """
    Combined V using both routing channels.

    Keyword entropy (compute_V) is a poor proxy when most agents score 0:
    the softmax spreads uniformly even on confident queries, pushing V → 2.

    Combined V uses:
      - answer_shape disorder: how open-ended is the expected response?
      - domain_conf: how strongly does the query signal a single domain?

    V_combined = 1 + (w_shape * shape_disorder + w_domain * (1 - domain_conf))
    with w_shape = w_domain = 0.5, so V_combined ∈ [1.0, 2.0].
    """
    sig           = normalize(query)
    shape_disorder = _SHAPE_DISORDER.get(sig.answer_shape, 0.5)
    domain_uncert  = 1.0 - sig.domain_conf   # 1 = no signal, 0 = full confidence
    return 1.0 + 0.5 * shape_disorder + 0.5 * domain_uncert


def scale_repr(query: str, expected: str) -> dict:
    """
    Scalar field φ^ℓ at each of 4 routing scale levels.

    All values normalised to [0, 1] so Pearson correlations are comparable.

    ℓ=0  max keyword fraction   = max_score / total_keywords_fired
         (how dominant is the winning agent in raw keyword space?)
    ℓ=1  soft prob of top agent = max of softmax(scores)
         (routing confidence after smoothing)
    ℓ=2  domain_conf            from QuerySignal (signal-layer confidence)
    ℓ=3  routing correctness    1.0 = routed correctly, 0.0 = wrong
    """
    scores = keyword_scores(query)
    sig    = normalize(query)
    probs  = softmax(scores)

    total     = sum(scores.values())
    max_score = max(scores.values())
    phi_0 = max_score / total if total > 0 else 1.0 / len(scores)

    phi_1 = max(probs.values())

    phi_2 = sig.domain_conf

    routed = signal_route(query)
    phi_3  = 1.0 if routed == expected else 0.0

    return {0: phi_0, 1: phi_1, 2: phi_2, 3: phi_3}


# ── Statistical helpers ───────────────────────────────────────

def pearson(xs: list, ys: list) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy  = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-12 or dy < 1e-12:
        return 0.0
    return num / (dx * dy)


def linfit(xs: list, ys: list):
    """Linear regression y = a·x + b. Returns (slope, intercept, R²)."""
    n   = len(xs)
    sx  = sum(xs);  sy  = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return 0.0, sum(ys) / n, 0.0
    a  = (n * sxy - sx * sy) / den
    b  = (sy - a * sx) / n
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - sy / n) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    return a, b, r2


def powerlaw_fit(xs: list, ys: list):
    """
    Fit y = C · x^α in log-log space.
    Returns (α, C, R²).  Skips non-positive entries.
    """
    pairs = [(x, y) for x, y in zip(xs, ys) if x > 0 and y > 0]
    if len(pairs) < 2:
        return 0.0, 1.0, 0.0
    lx = [math.log(x) for x, _ in pairs]
    ly = [math.log(y) for _, y in pairs]
    alpha, logC, r2 = linfit(lx, ly)
    return alpha, math.exp(logC), r2


# ── Main evaluation ───────────────────────────────────────────

def run():
    print("=" * 65)
    print("  ACM-RG Critical Structure Evaluation")
    print("=" * 65)

    # ── Collect data ─────────────────────────────────────────
    records = []
    for pid, expected, domain, prompt in PROMPTS:
        scores = keyword_scores(prompt)
        sig    = normalize(prompt)
        probs  = softmax(scores)
        V      = compute_V(scores)
        margin = confidence_margin(scores)
        routed = signal_route(prompt)
        correct = (routed == expected)
        phi    = scale_repr(prompt, expected)

        records.append({
            "id":         pid,
            "expected":   expected,
            "domain":     domain,
            "prompt":     prompt,
            "scores":     scores,
            "probs":      probs,
            "V":          V,
            "margin":     margin,
            "correct":    correct,
            "domain_conf": sig.domain_conf,
            "phi":        phi,
        })

    n             = len(records)
    correct_count = sum(r["correct"] for r in records)

    # Augment each record with combined V
    for r in records:
        r["V_combined"] = compute_V_combined(r["prompt"])

    # ─────────────────────────────────────────────────────────
    # 1. V DISTRIBUTION
    # ─────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print("  1. V DISTRIBUTION  (routing entropy parameter)")
    print(f"{'─'*65}")

    all_V  = [r["V"] for r in records]
    mean_V = sum(all_V) / n
    std_V  = math.sqrt(sum((v - mean_V) ** 2 for v in all_V) / n)

    print(f"  Queries:  {n}")
    print(f"  Accuracy: {correct_count}/{n} ({100*correct_count/n:.1f}%)")
    print(f"  Mean V:   {mean_V:.4f}  (theory critical: 1.5)")
    print(f"  Std V:    {std_V:.4f}")
    print(f"  Range:    [{min(all_V):.4f}, {max(all_V):.4f}]")

    # ASCII histogram 1.0 → 2.0 in 10 bins
    bins = [0] * 10
    for v in all_V:
        b = min(int((v - 1.0) * 10), 9)
        bins[b] += 1

    print("\n  V histogram  (1.0 → 2.0):")
    for i, count in enumerate(bins):
        lo     = 1.0 + i * 0.1
        bar    = "█" * count
        marker = " ← V_c (theory)" if 4 <= i <= 5 else ""
        print(f"    [{lo:.1f}–{lo+0.1:.1f}]  {bar:<25s} {count:3d}{marker}")

    # V stats by domain
    by_domain = defaultdict(list)
    for r in records:
        by_domain[r["domain"]].append(r)

    print("\n  Mean V (keyword) and accuracy by domain:")
    for dom in sorted(by_domain.keys()):
        rs  = by_domain[dom]
        mv  = sum(r["V"] for r in rs) / len(rs)
        acc = sum(r["correct"] for r in rs) / len(rs)
        print(f"    {dom:15s}: V={mv:.3f}  acc={acc:.0%}  n={len(rs)}")

    # ─────────────────────────────────────────────────────────
    # 1b. COMBINED V  (shape + domain signal)
    # ─────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print("  1b. COMBINED V  (answer_shape disorder + domain uncertainty)")
    print(f"{'─'*65}")
    print("  Keyword entropy overestimates disorder: sparse matches → V≈2")
    print("  Combined V uses both routing channels for a fair V estimate.")

    all_Vc   = [r["V_combined"] for r in records]
    mean_Vc  = sum(all_Vc) / n
    std_Vc   = math.sqrt(sum((v - mean_Vc) ** 2 for v in all_Vc) / n)
    print(f"\n  Mean V_combined: {mean_Vc:.4f}  (keyword V was: {sum(all_V)/n:.4f})")
    print(f"  Std  V_combined: {std_Vc:.4f}")
    print(f"  Range:           [{min(all_Vc):.4f}, {max(all_Vc):.4f}]")

    # Histogram
    binsC = [0] * 10
    for v in all_Vc:
        b = min(int((v - 1.0) * 10), 9)
        binsC[b] += 1

    print("\n  V_combined histogram  (1.0 → 2.0):")
    for i, count in enumerate(binsC):
        lo     = 1.0 + i * 0.1
        bar    = "█" * count
        marker = " ← V_c (theory)" if 4 <= i <= 5 else ""
        print(f"    [{lo:.1f}–{lo+0.1:.1f}]  {bar:<25s} {count:3d}{marker}")

    print("\n  Mean V_combined and accuracy by domain:")
    for dom in sorted(by_domain.keys()):
        rs  = by_domain[dom]
        mv  = sum(r["V_combined"] for r in rs) / len(rs)
        acc = sum(r["correct"] for r in rs) / len(rs)
        print(f"    {dom:15s}: V_combined={mv:.3f}  acc={acc:.0%}  n={len(rs)}")

    # ─────────────────────────────────────────────────────────
    # 2. CRITICAL POINT + β EXPONENT
    # ─────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print("  2. CRITICAL POINT  +  β EXPONENT")
    print(f"{'─'*65}")
    print("  Theory: |accuracy - 0.5| ~ |V - V_c|^β")
    print("  Mean-field prediction: β = 0.5")

    def fit_beta(records_list, v_key, label):
        """Bin by V and fit β. Returns (V_c, β, R²)."""
        bin_acc_loc: dict = defaultdict(lambda: {"c": 0, "t": 0})
        for r in records_list:
            b = round(r[v_key] * 10) / 10
            bin_acc_loc[b]["c"] += int(r["correct"])
            bin_acc_loc[b]["t"] += 1

        print(f"\n  Accuracy by {label} bin:")
        loc_accs = []
        for bv in sorted(bin_acc_loc.keys()):
            bd = bin_acc_loc[bv]
            if bd["t"] < 1:
                continue
            acc = bd["c"] / bd["t"]
            loc_accs.append((bv, acc, bd["t"]))
            filled = "█" * bd["c"] + "░" * (bd["t"] - bd["c"])
            print(f"    {label}≈{bv:.1f}: {acc:4.0%}  {filled:<15s}  n={bd['t']}")

        if not loc_accs:
            return 1.5, 0.5, 0.0

        # V_c = bin closest to 0.5 accuracy
        Vc_emp = min(loc_accs, key=lambda x: abs(x[1] - 0.5))[0]
        print(f"    Empirical {label}_c = {Vc_emp:.2f}  (theory: 1.5)")

        fx, fy = [], []
        for bv, acc, _ in loc_accs:
            dV = abs(bv - Vc_emp)
            dA = abs(acc - 0.5)
            if dV > 0.05 and dA > 1e-6:
                fx.append(dV)
                fy.append(dA)

        if len(fx) >= 2:
            b_exp, C_b, r2_b = powerlaw_fit(fx, fy)
            print(f"    Fit: |acc - 0.5| = {C_b:.3f} · |{label} - {label}_c|^β")
            print(f"    β = {b_exp:.3f}  (mean-field: 0.5)   R² = {r2_b:.3f}")
            return Vc_emp, b_exp, r2_b
        else:
            print(f"    (insufficient variance for β fit with {label})")
            return Vc_emp, 0.5, 0.0

    print("\n  ── Using keyword V ──")
    V_c,   beta,   r2_beta   = fit_beta(records, "V",          "V")
    print("\n  ── Using combined V ──")
    V_c_c, beta_c, r2_beta_c = fit_beta(records, "V_combined", "V_combined")

    # Use whichever gives a better-conditioned fit
    if r2_beta_c >= r2_beta:
        beta, V_c = beta_c, V_c_c
        print(f"\n  Using combined-V result (better R²={r2_beta_c:.3f} vs {r2_beta:.3f})")
    else:
        print(f"\n  Using keyword-V result (better R²={r2_beta:.3f} vs {r2_beta_c:.3f})")

    if abs(beta - 0.5) < 0.15:
        uc = "mean-field / Gaussian"
    elif beta < 0.5:
        uc = "sub-mean-field (softer transition)"
    else:
        uc = "super-mean-field (sharper — non-trivial universality)"
    print(f"  Universality class: {uc}")

    # ─────────────────────────────────────────────────────────
    # 3. TWO-POINT CORRELATION  G(Δℓ)  AND  η
    # ─────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print("  3. TWO-POINT CORRELATION  G(Δℓ)  AND  ANOMALOUS DIMENSION η")
    print(f"{'─'*65}")
    print("  Theory: G(Δℓ) ~ Δℓ^{-η}  (η=0: Gaussian fixed point)")

    phi_by_scale: dict = {ell: [] for ell in range(4)}
    for r in records:
        for ell, val in r["phi"].items():
            phi_by_scale[ell].append(val)

    scale_labels = {
        0: "ℓ=0  max keyword fraction",
        1: "ℓ=1  soft prob of top agent",
        2: "ℓ=2  domain_conf (QuerySignal)",
        3: "ℓ=3  routing correctness",
    }
    print("\n  Scale summary  (mean ± std):")
    for ell in range(4):
        vals = phi_by_scale[ell]
        mv   = sum(vals) / len(vals)
        sv   = math.sqrt(sum((v - mv) ** 2 for v in vals) / len(vals))
        print(f"    {scale_labels[ell]}: {mv:.3f} ± {sv:.3f}")

    # Pearson correlation between every pair of scale levels
    print("\n  Pairwise correlations |r(ℓ₁, ℓ₂)|:")
    G_by_delta: dict = defaultdict(list)
    for ell_a in range(4):
        for ell_b in range(ell_a + 1, 4):
            delta = ell_b - ell_a
            r     = pearson(phi_by_scale[ell_a], phi_by_scale[ell_b])
            G_by_delta[delta].append(abs(r))
            print(f"    G(ℓ={ell_a}, ℓ={ell_b})  Δℓ={delta}  |r| = {abs(r):.4f}")

    print("\n  Mean G by Δℓ (used for power-law fit):")
    delta_xs, delta_ys = [], []
    for delta in sorted(G_by_delta.keys()):
        g = sum(G_by_delta[delta]) / len(G_by_delta[delta])
        print(f"    G(Δℓ={delta}) = {g:.4f}")
        delta_xs.append(delta)
        delta_ys.append(g)

    alpha_G, C_G, r2_G = powerlaw_fit(delta_xs, delta_ys)
    eta = -alpha_G   # G ~ Δℓ^{-η}  →  log-log slope = -η

    print(f"\n  Power-law fit: G(Δℓ) = {C_G:.4f} · Δℓ^{{{alpha_G:+.3f}}}")
    print(f"    η  = {eta:.3f}   (Gaussian: 0,  non-trivial: ≠ 0)")
    print(f"    R² = {r2_G:.3f}")
    if eta > 0.05:
        g_verdict = "non-zero — anomalous dimension present, non-Gaussian critical point"
    elif eta < -0.05:
        g_verdict = "η < 0 — correlations grow with scale (unusual, check signal coverage)"
    else:
        g_verdict = "η ≈ 0 — consistent with Gaussian (mean-field) fixed point"
    print(f"    Verdict: {g_verdict}")

    # ─────────────────────────────────────────────────────────
    # 4. HYPERSCALING CHECK
    # ─────────────────────────────────────────────────────────
    print(f"\n{'─'*65}")
    print("  4. HYPERSCALING CHECK:  γ = ν(2 − η)")
    print(f"{'─'*65}")
    print("  (If RG structure is real, exponents must satisfy this relation.)")

    # Estimate ν from spread of V around V_c for correct vs incorrect queries
    V_correct = [r["V"] for r in records if r["correct"]]
    V_wrong   = [r["V"] for r in records if not r["correct"]]

    nu_proxy = 0.5   # mean-field default if insufficient data

    if len(V_correct) >= 2 and len(V_wrong) >= 2:
        var_c = sum((v - V_c) ** 2 for v in V_correct) / len(V_correct)
        var_w = sum((v - V_c) ** 2 for v in V_wrong)   / len(V_wrong)
        # Larger spread in wrong queries → correlation length longer there
        # ν estimated from ratio: spread_wrong / spread_correct ~ L^{1/ν}
        if var_c > 1e-6 and var_w > 1e-6:
            spread_ratio = math.sqrt(var_w / var_c)
            log_L        = math.log(max(len(records), 2))
            nu_proxy     = abs(math.log(spread_ratio)) / log_L
            nu_proxy     = max(0.1, min(2.0, nu_proxy))

    gamma_predicted = nu_proxy * (2.0 - eta)

    # Susceptibility proxy: variance of routing probability distribution
    def routing_var(recs):
        if not recs:
            return 0.0
        total = 0.0
        for r in recs:
            ps    = list(r["probs"].values())
            mp    = sum(ps) / len(ps)
            total += sum((p - mp) ** 2 for p in ps) / len(ps)
        return total / len(recs)

    near_Vc = [r for r in records if abs(r["V"] - V_c) < 0.2]
    far_Vc  = [r for r in records if abs(r["V"] - V_c) > 0.4]

    chi_near = routing_var(near_Vc)
    chi_far  = routing_var(far_Vc)

    print(f"\n  Estimated exponents:")
    print(f"    β = {beta:.3f}   (order parameter)")
    print(f"    η = {eta:.3f}   (anomalous dimension)")
    print(f"    ν = {nu_proxy:.3f}   (correlation length, spread-ratio estimate)")
    print(f"\n  Hyperscaling prediction:")
    print(f"    γ = ν(2 − η) = {nu_proxy:.3f} × {2-eta:.3f} = {gamma_predicted:.3f}")

    print(f"\n  Susceptibility proxy  χ = Var(routing probabilities):")
    print(f"    χ near V_c  (|V−V_c| < 0.2): {chi_near:.5f}  n={len(near_Vc)}")
    print(f"    χ far  V_c  (|V−V_c| > 0.4): {chi_far:.5f}  n={len(far_Vc)}")

    if chi_far > 1e-9:
        chi_ratio = chi_near / chi_far
        direction = "enhanced fluctuations near V_c ✓" if chi_ratio > 1 else "no enhancement (V_c may not be critical)"
        print(f"    χ_near / χ_far = {chi_ratio:.3f}  → {direction}")

    # Cross-check: β = ν·η/2 when d=2 (mean-field: β = 0.5, ν = 0.5, η = 0)
    if abs(eta) > 0.01:
        nu_from_beta = 2 * beta / eta
        print(f"\n  Cross-check (d=2 hyperscaling: ν = 2β/η):")
        print(f"    ν = 2×{beta:.3f}/{eta:.3f} = {nu_from_beta:.3f}")
        consistency = 1.0 - min(abs(nu_from_beta - nu_proxy) / max(nu_proxy, 0.01), 1.0)
        print(f"    Consistency with spread estimate: {100*consistency:.0f}%")

    # ─────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print("  SUMMARY")
    print(f"{'═'*65}")
    print(f"\n  System:    {n} queries,  {correct_count} correct  ({100*correct_count/n:.1f}% accuracy)")
    print(f"  Mean V:    {mean_V:.4f}  (theory V_c = 1.5)")
    print(f"  Empir V_c: {V_c:.2f}")
    print(f"\n  Critical exponents:")
    print(f"    β = {beta:.3f}   order parameter exponent  (mean-field: 0.50)")
    print(f"    η = {eta:.3f}   anomalous dimension       (Gaussian:   0.00)")
    print(f"    ν = {nu_proxy:.3f}   correlation length        (mean-field: 0.50)")
    print(f"    γ = {gamma_predicted:.3f}   susceptibility (predicted via hyperscaling)")

    mf_consistent = abs(beta - 0.5) < 0.15 and abs(eta) < 0.1
    print(f"\n  Universality class:")
    if mf_consistent:
        print("    Mean-field / Gaussian: routing transition is linear near V_c.")
        print("    Exponents consistent with β=0.5, η=0 (no operator renormalization).")
    else:
        print(f"    Non-trivial: β={beta:.2f}, η={eta:.2f} depart from Gaussian predictions.")
        print(f"    Keyword signal interactions generate anomalous scaling — the routing")
        print(f"    system is NOT reducible to independent keyword-counting at the critical point.")

    print(f"\n  Note on terse queries:")
    print(f"    Factual-shape queries (te_*) are routed via answer_shape, not keywords.")
    print(f"    Their keyword scores are near-uniform → V ≈ 2.0 even when correctly routed.")
    print(f"    This means keyword-V underestimates routing confidence for factual queries.")
    print(f"    A 'combined V' using shape + domain_conf would give a more accurate estimate.")
    print()


if __name__ == "__main__":
    run()
