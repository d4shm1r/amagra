"""Tests for the decision-economics loop (v1.9.0, closes OPEN_PROBLEMS O2).

Covers the three newly-connected edges:
  * parse_strategy round-trips canonical_strategy      (selector ↔ memory contract)
  * record_counterfactual feeds BOTH arms into memory  (the missing O2 edge)
  * recommend() abstains on thin evidence, acts on strong evidence + margin
  * selectable_classes reflects populated alternatives  (the "did exploration help" metric)

Everything runs on injected temp DBs — no LLM, no run log, no real traffic.
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision.strategy_memory import (
    StrategyMemory, StrategyRecord, canonical_strategy, task_class_of,
)
from decision.strategy_selector import StrategySelector, parse_strategy
from decision.experience import record_counterfactual, selectable_classes


def _mem():
    return StrategyMemory(path=os.path.join(tempfile.mkdtemp(), "s.db"))


# ── parse_strategy is the exact inverse of canonical_strategy ─────────

def test_parse_strategy_round_trips_canonical():
    cases = [
        ("python_dev", "none", False, False),
        ("python_dev", "light", False, False),
        ("web_dev", "full", True, False),
        ("devops", "light", True, True),
    ]
    for agent, reflect, mem_used, tool_used in cases:
        s = canonical_strategy(agent, reflect, mem_used, tool_used)
        assert parse_strategy(s) == (agent, reflect, mem_used, tool_used)


def test_parse_strategy_ignores_unknown_parts():
    assert parse_strategy("python_dev+garbage+reflect:full") == ("python_dev", "full", False, False)


# ── record_counterfactual: the edge that was missing ─────────────────

def test_record_counterfactual_writes_both_arms():
    m = _mem()
    tc = task_class_of("it_networking", "procedure")
    cf = {
        "is_real_run": True, "decision_id": 42,
        "original_agent": "it_networking", "original_quality_proxy": 0.72,
        "original_duration_s": 12.0,
        "alt_agent": "knowledge_learning", "alt_quality_proxy": 0.50,
        "alt_duration_s": 8.0,
    }
    written = record_counterfactual(cf, task_class=tc, memory=m)
    assert written == 2                                   # both arms recorded
    strategies = {s.strategy for s in m.stats_for(tc)}
    assert canonical_strategy("it_networking", "none") in strategies
    assert canonical_strategy("knowledge_learning", "none") in strategies


def test_record_counterfactual_is_idempotent():
    m = _mem()
    tc = task_class_of("python", "code")
    cf = {
        "is_real_run": True, "decision_id": 7,
        "original_agent": "python_dev", "original_quality_proxy": 0.80, "original_duration_s": 5.0,
        "alt_agent": "web_dev", "alt_quality_proxy": 0.40, "alt_duration_s": 6.0,
    }
    assert record_counterfactual(cf, task_class=tc, memory=m) == 2
    assert record_counterfactual(cf, task_class=tc, memory=m) == 0   # re-run = no dupes


def test_dry_run_counterfactual_records_nothing():
    m = _mem()
    cf = {"is_real_run": False, "verdict": "insufficient_data"}
    assert record_counterfactual(cf, task_class="a/b", memory=m) == 0


def test_counterfactual_populates_selectable_alternatives():
    """The O2 payoff: before the feed the class has 0 strategies and the selector
    can only abstain; after, it has ≥2 and becomes selectable."""
    m = _mem()
    tc = task_class_of("it_networking", "procedure")
    assert selectable_classes(m) == []                   # nothing yet
    cf = {
        "is_real_run": True, "decision_id": 99,
        "original_agent": "it_networking", "original_quality_proxy": 0.75, "original_duration_s": 10.0,
        "alt_agent": "devops", "alt_quality_proxy": 0.65, "alt_duration_s": 9.0,
    }
    record_counterfactual(cf, task_class=tc, memory=m)
    assert (tc, 2) in selectable_classes(m)              # now selectable


# ── recommend(): the router-facing decision, with its safety abstentions ─

def test_recommend_abstains_on_thin_evidence():
    m = _mem()
    sel = StrategySelector(m)
    # unknown class → abstain (keep current router)
    assert sel.recommend("python", "code") is None
    # one attempt → still abstain (below min_attempts)
    m.record(StrategyRecord(task_class_of("python", "code"), "python_dev", True, latency_ms=5000))
    assert sel.recommend("python", "code") is None


def test_recommend_acts_on_strong_evidence():
    m = _mem()
    tc = task_class_of("python", "code")
    # a proven fast strategy vs a proven-but-much-slower one → clear EV winner
    for _ in range(5):
        m.record(StrategyRecord(tc, "python_dev", True, latency_ms=5000))
    for _ in range(5):
        m.record(StrategyRecord(tc, "web_dev+reflect:full", True, latency_ms=60000))
    pref = StrategySelector(m).recommend("python", "code")
    assert pref is not None
    assert pref.agent == "python_dev"
    assert pref.reflect_level == "none"
    assert pref.runner_up_ev is not None                 # it beat something, logged for regret


def test_live_and_backfill_dedup_on_shared_run_id():
    """The coordinator's live recorder and ingest_run_log() both key on the real
    run_id, so a run recorded live is a no-op when later backfilled — never double
    counted. This guards the design of orchestration.coordinator._record_strategy_live."""
    m = _mem()
    tc = task_class_of("python", "code")
    live = StrategyRecord(tc, "python_dev", True, latency_ms=5000, run_id="run-abc")
    assert m.record(live) is True                        # live write lands
    backfill = StrategyRecord(tc, "python_dev", True, latency_ms=5000, run_id="run-abc")
    assert m.record(backfill) is False                   # same run_id → ignored
    assert m.stats_for(tc)[0].attempts == 1              # exactly one row, not two


def test_null_run_ids_do_not_collide():
    """Ad-hoc rows with no run_id must not dedup against each other (NULL is distinct
    in SQLite) — otherwise distinct live runs missing an id would collapse into one."""
    m = _mem()
    tc = task_class_of("web", "code")
    assert m.record(StrategyRecord(tc, "web_dev", True, latency_ms=1000, run_id=None)) is True
    assert m.record(StrategyRecord(tc, "web_dev", True, latency_ms=1000, run_id=None)) is True
    assert m.stats_for(tc)[0].attempts == 2


def test_recommend_abstains_on_thin_margin():
    m = _mem()
    tc = task_class_of("web", "code")
    for _ in range(5): m.record(StrategyRecord(tc, "web_dev", True, latency_ms=5000))
    for _ in range(5): m.record(StrategyRecord(tc, "python_dev", True, latency_ms=5100))
    # two near-identical winners → default margin keeps the current router
    assert StrategySelector(m).recommend("web", "code") is None
