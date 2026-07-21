"""Tests for decision/strategy_selector.py — EV math, shrinkage, abstention."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decision.strategy_memory import StrategyMemory, StrategyRecord, StrategyStat
from decision.strategy_selector import StrategySelector, expected_value, _smoothed_p


def _mem():
    return StrategyMemory(path=os.path.join(tempfile.mkdtemp(), "s.db"))


def test_shrinkage_pulls_small_samples_toward_prior():
    assert _smoothed_p(1, 1) == 2/3          # a lucky 1/1 is NOT 1.0
    assert _smoothed_p(0, 0) == 0.5          # no evidence → prior mean
    # 90/100 stays close to 0.9 with lots of evidence
    assert abs(_smoothed_p(90, 100) - 0.892) < 0.01


def test_expected_value_penalizes_latency():
    fast = StrategyStat("t", "fast", 4, 4, 4, 1.0, 0.0, 1000)
    slow = StrategyStat("t", "slow", 4, 4, 4, 1.0, 0.0, 60000)
    ev_fast = expected_value(fast).expected_value
    ev_slow = expected_value(slow).expected_value
    assert ev_fast > ev_slow          # same success, faster wins
    assert expected_value(slow).breakdown["latency_penalty"] == 0.30  # capped at budget


def test_rank_prefers_cheaper_proven_strategy():
    m = _mem()
    tc = "python/code"
    for _ in range(4): m.record(StrategyRecord(tc, "python_dev", True, latency_ms=47000))
    m.record(StrategyRecord(tc, "pipeline+reflect:light", None, latency_ms=104000))
    ranked = StrategySelector(m).rank(tc)
    assert ranked[0].strategy == "python_dev"       # proven + cheaper on top
    # the ungraded expensive strategy sits at the prior (0.5) minus full latency
    assert ranked[-1].p_success == 0.5


def test_select_abstains_without_enough_attempts():
    m = _mem()
    m.record(StrategyRecord("net/proc", "lucky", True, latency_ms=1000))
    sel = StrategySelector(m)
    assert sel.select("net/proc", min_attempts=3) is None      # 1 attempt → abstain
    for _ in range(3): m.record(StrategyRecord("net/proc", "lucky", True, latency_ms=1000))
    assert sel.select("net/proc", min_attempts=3).strategy == "lucky"


def test_select_abstains_on_unknown_class_and_thin_margin():
    m = _mem()
    sel = StrategySelector(m)
    assert sel.select("never/seen") is None
    # two near-identical strategies → abstain when a margin is required
    for _ in range(4): m.record(StrategyRecord("a/b", "X", True, latency_ms=1000))
    for _ in range(4): m.record(StrategyRecord("a/b", "Y", True, latency_ms=1000))
    assert sel.select("a/b", min_attempts=3, margin=0.05) is None
