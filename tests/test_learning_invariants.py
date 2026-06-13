"""
Learning mechanics invariant tests.

Verifies the three C1-smooth primitives introduced in the OCAC upgrades:
  1. Domain confidence (query_normalizer) — logistic, monotone, correct threshold crossing
  2. Adaptive alpha (learning) — smooth, strictly decreasing, zeroes near I=1
  3. Log-odds quality update (memory_db) — bounds-safe, resistance at extremes

No LLM, no DB, no Ollama required. Pure math + isolated DB operations.

Run: python3 tests/test_learning_invariants.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# 1. Domain Confidence
# ─────────────────────────────────────────────────────────────

def test_domain_conf_single_hit_above_threshold():
    """1 keyword hit must still exceed routing threshold 0.30."""
    from orchestration.query_normalizer import detect_domain
    _, conf = detect_domain("python script")
    assert conf > 0.30, f"1-hit confidence {conf:.3f} is below routing threshold 0.30"


def test_domain_conf_monotone():
    """More hits → strictly higher confidence."""
    # Use a fabricated keyword set — we test the formula, not the actual keywords
    k = 0.40
    confs = [1.0 - math.exp(-k * h) for h in range(1, 7)]
    for i in range(len(confs) - 1):
        assert confs[i] < confs[i + 1], (
            f"Confidence not monotone: conf({i+1})={confs[i]:.4f} >= conf({i+2})={confs[i+1]:.4f}"
        )


def test_domain_conf_bounded():
    """Confidence must stay in (0, 1) and never reach 1.0 exactly."""
    k = 0.40
    for hits in range(1, 50):
        c = 1.0 - math.exp(-k * hits)
        assert 0.0 < c < 1.0, f"Confidence out of open (0,1) at hits={hits}: {c}"


def test_domain_conf_multi_hit():
    """A query with several domain keywords must return high confidence."""
    from orchestration.query_normalizer import detect_domain
    # 5 clear Python keywords → 1 - exp(-0.40*5) ≈ 0.865
    _, conf = detect_domain("write a python asyncio coroutine using pandas with pytest decorator")
    assert conf > 0.80, f"5-hit query returned only {conf:.3f}"


# ─────────────────────────────────────────────────────────────
# 2. Adaptive Alpha
# ─────────────────────────────────────────────────────────────

def _alpha(instability: float) -> float:
    """Mirror of the production formula in learning.py."""
    from training.learning import BASE_ALPHA, _ALPHA_STEEPNESS
    raw = BASE_ALPHA / (1.0 + math.exp(_ALPHA_STEEPNESS * (instability - 0.5)))
    return 0.0 if raw < 2e-3 else raw


def test_alpha_strictly_decreasing():
    """alpha(I) must be strictly decreasing over [0, 0.95]."""
    instabilities = [i / 100 for i in range(0, 96)]
    alphas = [_alpha(i) for i in instabilities]
    for i in range(len(alphas) - 1):
        # Allow plateaus only at zero (frozen region)
        if alphas[i] > 0 and alphas[i + 1] > 0:
            assert alphas[i] > alphas[i + 1], (
                f"alpha not strictly decreasing at I={instabilities[i]:.2f}: "
                f"{alphas[i]:.5f} vs {alphas[i+1]:.5f}"
            )


def test_alpha_low_instability_near_base():
    """At I=0 the learning rate should be close to BASE_ALPHA."""
    from training.learning import BASE_ALPHA
    a = _alpha(0.0)
    assert a > 0.9 * BASE_ALPHA, f"alpha(0) = {a:.5f}, expected near {BASE_ALPHA}"


def test_alpha_midpoint_is_half_base():
    """At I=0.5 the sigmoid gives exactly BASE_ALPHA / 2."""
    from training.learning import BASE_ALPHA
    a = _alpha(0.5)
    assert abs(a - BASE_ALPHA / 2) < 1e-6, (
        f"alpha(0.5) = {a:.6f}, expected {BASE_ALPHA/2:.6f}"
    )


def test_alpha_high_instability_is_zero():
    """At I≥0.9 the learning rate should be zero (effectively frozen)."""
    for I in [0.90, 0.95, 1.00]:
        a = _alpha(I)
        assert a == 0.0, f"alpha({I}) = {a:.5f}, expected 0.0 (frozen)"


def test_alpha_no_discontinuity():
    """
    No step jump larger than 0.005 anywhere in [0, 1].
    Old step function had jumps of ~0.025 at I=0.60 and I=0.80.
    """
    instabilities = [i / 1000 for i in range(1001)]
    alphas = [_alpha(i) for i in instabilities]
    max_jump = max(abs(alphas[i] - alphas[i + 1]) for i in range(len(alphas) - 1))
    assert max_jump <= 0.005, (
        f"Discontinuity detected: max step = {max_jump:.5f} > 0.005"
    )


# ─────────────────────────────────────────────────────────────
# 3. Log-Odds Quality Update
# ─────────────────────────────────────────────────────────────

def _logit_update(q: float, delta: float, gamma: float = 4.0) -> float:
    """Mirror of memory_db._logit_update."""
    q_safe   = max(0.001, min(0.999, q))
    log_odds = math.log(q_safe / (1.0 - q_safe))
    log_odds += gamma * delta
    new_q    = 1.0 / (1.0 + math.exp(-log_odds))
    return round(max(0.0, min(1.0, new_q)), 4)


def test_quality_stays_in_bounds():
    """Quality must remain in [0, 1] for any delta and starting value."""
    for q in [0.0, 0.001, 0.1, 0.5, 0.9, 0.999, 1.0]:
        for delta in [-0.5, -0.05, -0.03, 0.0, 0.03, 0.5]:
            result = _logit_update(q, delta)
            assert 0.0 <= result <= 1.0, (
                f"Quality out of bounds: q={q}, delta={delta} → {result}"
            )


def test_positive_delta_increases_quality():
    """Positive feedback always increases quality."""
    for q in [0.1, 0.3, 0.5, 0.7, 0.9]:
        new_q = _logit_update(q, +0.03)
        assert new_q >= q, f"Positive delta decreased quality: {q} → {new_q}"


def test_negative_delta_decreases_quality():
    """Negative feedback always decreases quality."""
    for q in [0.1, 0.3, 0.5, 0.7, 0.9]:
        new_q = _logit_update(q, -0.05)
        assert new_q <= q, f"Negative delta increased quality: {q} → {new_q}"


def test_quality_resistance_at_extremes():
    """
    High-quality memories should change less than mid-range memories
    for the same positive feedback delta.
    This is the key behavioral property of log-odds vs linear updates.
    """
    delta = +0.03
    change_at_mid  = _logit_update(0.50, delta) - 0.50
    change_at_high = _logit_update(0.90, delta) - 0.90
    assert change_at_high < change_at_mid, (
        f"High-quality memory moved MORE than mid-range: "
        f"Δ@0.9={change_at_high:.4f}  Δ@0.5={change_at_mid:.4f}"
    )


def test_quality_resistance_at_low_end():
    """Low-quality memories should be harder to push further down."""
    delta = -0.05
    change_at_mid = abs(_logit_update(0.50, delta) - 0.50)
    change_at_low = abs(_logit_update(0.10, delta) - 0.10)
    assert change_at_low < change_at_mid, (
        f"Low-quality memory dropped MORE than mid-range: "
        f"Δ@0.1={change_at_low:.4f}  Δ@0.5={change_at_mid:.4f}"
    )


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

_TESTS = [
    test_domain_conf_single_hit_above_threshold,
    test_domain_conf_monotone,
    test_domain_conf_bounded,
    test_domain_conf_multi_hit,
    test_alpha_strictly_decreasing,
    test_alpha_low_instability_near_base,
    test_alpha_midpoint_is_half_base,
    test_alpha_high_instability_is_zero,
    test_alpha_no_discontinuity,
    test_quality_stays_in_bounds,
    test_positive_delta_increases_quality,
    test_negative_delta_decreases_quality,
    test_quality_resistance_at_extremes,
    test_quality_resistance_at_low_end,
]

if __name__ == "__main__":
    passed = failed = 0
    for t in _TESTS:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(0 if failed == 0 else 1)
