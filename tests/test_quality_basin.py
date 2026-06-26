"""Phase 4 — cubic basin advisory for the nonlinear quality update.

The memory quality update is the logistic log-odds map q ← σ(σ⁻¹(q)+γδ), whose
basin near the saturated ends is *bounded*, not global. The advisory warns (never
blocks) when an update lands a memory in that corner, so noisy feedback can't
silently push quality into a non-recoverable region.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from evaluation.math_metrics import quality_update_basin
from infrastructure.event_bus import subscribe, unsubscribe, EventType
import memory_core.db as mdb


def test_basin_warns_only_in_the_corner():
    assert quality_update_basin(0.5)["warn"] is False        # interior — safe
    assert quality_update_basin(0.985, delta_f=-0.05)["warn"] is True   # corner
    # corrective feedback is suppressed in the corner (the bounded-basin trap)
    assert quality_update_basin(0.985, delta_f=-0.05)["corrective_feedback"] is True


def test_advisory_emits_event_in_corner_only():
    seen = []
    handler = lambda key, payload, ts: seen.append(payload)
    subscribe(EventType.MEMORY_QUALITY_SATURATED, handler)
    try:
        # interior update — no warning event
        mdb._advise_quality_basin(101, 0.55, 0.03)
        assert seen == []
        # corner update — exactly one warning event with the memory id
        mdb._advise_quality_basin(202, 0.985, -0.05)
        assert len(seen) == 1
        assert seen[0]["memory_id"] == 202
        assert seen[0]["corner_distance"] < 0.1
    finally:
        unsubscribe(EventType.MEMORY_QUALITY_SATURATED, handler)


def test_advisory_never_raises():
    # bad inputs must be swallowed — advisory can never break a quality write
    mdb._advise_quality_basin(None, None, None)  # should not raise
