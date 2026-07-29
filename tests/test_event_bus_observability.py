"""
#181 — routing conflicts and contradictions as *real* events.

The old CognitiveOSTab built a "Live Cognitive Events" feed in the browser by
walking /decisions, /contradictions and /coherence/dynamics and inventing rows.
#178 deleted that synthesized feed on the principle that if a moment belongs in
the event log, the runtime should emit it. This test pins the contract for the
two signals we decided are genuine runtime moments and now emit from
orchestration/coordinator.py:

  - contradiction.detected  — the contradiction gate escalated to full reflection
  - reflection.triggered    — reflection actually ran

Both must flow through the event bus and be visible to GET /cos/events (which
reads recent_events). The other three candidate signals (routing.conflict,
coherence.shifted, regret.high) are deliberately NOT events — see
docs/records/FINDINGS.md; routing.conflict in particular is structurally dead
(the keyword-router path was removed, so final_agent is always the brain's pick
and `conflict` is always False).

Imports only infrastructure.event_bus so it runs without the langgraph runtime.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.event_bus import (
    emit, recent_events, EventType, subscribe, unsubscribe,
)


def test_signal_event_types_exist():
    # The wire keys the UI and analytics consume are the dotted .value form.
    assert EventType.CONTRADICTION_DETECTED.value == "contradiction.detected"
    assert EventType.REFLECTION_TRIGGERED.value == "reflection.triggered"


def test_contradiction_event_reaches_the_stream():
    """Emitting the signal the coordinator now fires must appear in /cos/events."""
    emit(EventType.CONTRADICTION_DETECTED, {
        "run_id": "r-contra-1", "agent": "python_dev",
        "action": "code", "escalated_to": "full_reflection",
    })
    rows = recent_events(n=50, event_type="contradiction.detected")
    assert rows, "contradiction.detected did not reach the event store"
    hit = next((e for e in rows if e["payload"].get("run_id") == "r-contra-1"), None)
    assert hit is not None
    assert hit["type"] == "contradiction.detected"
    assert hit["payload"]["agent"] == "python_dev"
    assert hit["payload"]["escalated_to"] == "full_reflection"


def test_reflection_event_reaches_the_stream():
    emit(EventType.REFLECTION_TRIGGERED, {
        "run_id": "r-reflect-1", "agent": "ai_ml",
        "mode": "full", "reflect_type": "general", "contradiction": True,
    })
    rows = recent_events(n=50, event_type="reflection.triggered")
    assert rows, "reflection.triggered did not reach the event store"
    hit = next((e for e in rows if e["payload"].get("run_id") == "r-reflect-1"), None)
    assert hit is not None
    assert hit["type"] == "reflection.triggered"
    assert hit["payload"]["mode"] == "full"
    assert hit["payload"]["contradiction"] is True


def test_subscribers_receive_the_new_signals():
    """A live consumer (e.g. metrics/transparency) sees the typed signal too."""
    seen = []
    handler = lambda key, payload, ts: seen.append((key, payload))
    subscribe(EventType.CONTRADICTION_DETECTED, handler)
    try:
        emit(EventType.CONTRADICTION_DETECTED, {"run_id": "r-sub-1", "agent": "terse"})
    finally:
        unsubscribe(EventType.CONTRADICTION_DETECTED, handler)
    assert ("contradiction.detected", {"run_id": "r-sub-1", "agent": "terse"}) in seen
