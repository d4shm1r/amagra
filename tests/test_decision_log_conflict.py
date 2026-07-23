"""
O7 — the `conflict` column is a live signal again.

Since issue #20 removed the keyword router, `orchestration/coordinator.py` wrote
`conflict = False` unconditionally, so `decision.log.conflict_rate()` was pinned
at 0 and its consumers (the maintenance auto-rebuild trigger, report_generator /
specialization scores, failure_miner clusters, coherence C_routing) had silently
gone inert. The source now writes `conflict = decision.confidence < 0.5` — routing
indecision. This test pins the consumer contract: `conflict_rate()` reflects the
logged flag rather than reading a constant zero.

Pollution-tolerant (the session shares one temp brain_decisions via
AMAGRA_DATA_DIR): it asserts monotonic deltas around fresh writes, not absolutes.
Imports only decision.log — runs without the LangGraph runtime.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision.log as dl

dl.init()


def _log(conflict: bool, confidence: float):
    dl.log(
        task="o7 probe", action="answer", complexity="simple",
        brain_agent="python_dev", router_agent="none", final_agent="python_dev",
        conflict=conflict, reflect=False, reflect_type="general",
        confidence=confidence,
    )


def test_conflict_rate_counts_an_indecisive_route():
    before = dl.conflict_rate()
    _log(conflict=True, confidence=0.30)   # below the 0.5 floor → indecisive
    after = dl.conflict_rate()
    assert after["total"] == before["total"] + 1
    assert after["conflicts"] == before["conflicts"] + 1


def test_conflict_rate_ignores_a_confident_route():
    before = dl.conflict_rate()
    _log(conflict=False, confidence=0.82)  # decisive route → not a conflict
    after = dl.conflict_rate()
    assert after["total"] == before["total"] + 1
    assert after["conflicts"] == before["conflicts"]


def test_conflict_rate_is_not_structurally_zero():
    """The whole point of O7: after logging indecisive routes, the rate moves."""
    for _ in range(5):
        _log(conflict=True, confidence=0.2)
    stats = dl.conflict_rate()
    assert stats["conflicts"] > 0
    assert stats["conflict_rate"] > 0.0


def test_conflict_rate_window_is_honored():
    """O7 residual: `LIMIT ?` on a bare COUNT(*) was a no-op, so the 'last N'
    window silently spanned the whole table. The windowed subquery must cap
    `total` at last_n even when the table holds more rows."""
    for _ in range(6):
        _log(conflict=False, confidence=0.9)
    stats = dl.conflict_rate(last_n=3)
    assert stats["total"] == 3, (
        f"window not honored: total={stats['total']} for last_n=3 "
        "(the COUNT+LIMIT no-op would return the whole table)"
    )


def test_conflict_rate_window_reflects_recent_rows():
    """The window takes the *most recent* rows: after 4 fresh indecisive routes,
    a last_n=4 view is entirely conflicts regardless of older history."""
    for _ in range(4):
        _log(conflict=True, confidence=0.1)
    stats = dl.conflict_rate(last_n=4)
    assert stats["total"] == 4
    assert stats["conflicts"] == 4
    assert stats["conflict_rate"] == 1.0
