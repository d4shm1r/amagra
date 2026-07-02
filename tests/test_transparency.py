"""
Tests for infrastructure/transparency.py — the component transparency
classifier — covering GitHub issues #47 (Responder discloses quality +
kept-response) and #48 (Dispatch recategorized as mechanical).

recent_events is monkeypatched so no events.db is touched.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import infrastructure.transparency as tp


def _classify_with(monkeypatch, events):
    monkeypatch.setattr(tp, "recent_events", lambda n=2000: events)
    return tp.classify_components(window=len(events) or 1)


def _row(result, component):
    return next(r for r in result["components"] if r["component"] == component)


# ── Issue #47: Responder transparency ─────────────────────────────────────────

def test_responder_transparent_with_quality_and_kept(monkeypatch):
    # Payload shape emitted by cognitive_state.end_request after #47:
    # confidence = critic-gate score, evidence = which response was kept.
    events = [{
        "type": "response.generated",
        "payload": {"agent": "python_dev", "outcome": "completed",
                    "latency_ms": 812, "confidence": 0.82,
                    "evidence": "first_attempt"},
    }]
    row = _row(_classify_with(monkeypatch, events), "Responder")
    assert row["status"] == "transparent"
    assert "confidence" in row["confidence_keys"]
    assert "evidence" in row["evidence_keys"]


def test_responder_stays_honest_when_gate_did_not_run(monkeypatch):
    # No critic score → keys absent → Responder must NOT classify transparent.
    events = [{
        "type": "response.generated",
        "payload": {"agent": "python_dev", "outcome": "completed",
                    "latency_ms": 812},
    }]
    row = _row(_classify_with(monkeypatch, events), "Responder")
    assert row["status"] == "opaque"


# ── Issue #48: Dispatch is mechanical, not opaque ─────────────────────────────

def test_dispatch_classified_mechanical_with_rationale(monkeypatch):
    events = [{
        "type": "delta.dispatched",
        "payload": {"event_type": "route.query",
                    "base": {"a": 0.5, "b": 0.5},
                    "deltas": [{"hook_id": "h1", "tier": 1}]},
    }]
    row = _row(_classify_with(monkeypatch, events), "Dispatch")
    assert row["status"] == "mechanical"
    assert row["rationale"]
    # Its inputs ARE disclosed — deltas count as evidence.
    assert row["has_evidence"]


def test_mechanical_excluded_from_score_denominator(monkeypatch):
    # If every non-mechanical cataloged component were transparent, the score
    # must reach 1.0 — Dispatch must not permanently cap it.
    events = []
    for comp_prefix, comp in tp.CATALOG.items():
        if comp in tp.MECHANICAL:
            continue
        events.append({
            "type": f"{comp_prefix}.test",
            "payload": {"confidence": 0.9, "evidence": "x"},
        })
    result = _classify_with(monkeypatch, events)
    assert result["transparency_score"] == 1.0


def test_summary_includes_mechanical_bucket(monkeypatch):
    events = [{
        "type": "delta.dispatched",
        "payload": {"deltas": [{"hook_id": "h1"}], "base": {}},
    }]
    result = _classify_with(monkeypatch, events)
    assert result["summary"]["mechanical"] == 1


# ── cognitive_state.end_request payload (emitter side of #47) ─────────────────

def _fresh_state(monkeypatch, captured):
    from models.cognitive_state import CognitiveState

    def fake_emit(event_type, payload):
        captured["type"] = str(getattr(event_type, "value", event_type))
        captured["payload"] = payload

    import infrastructure.event_bus as bus
    monkeypatch.setattr(bus, "emit", fake_emit)
    # keep the test hermetic — no world-model file I/O
    monkeypatch.setattr(CognitiveState, "_load_world", lambda self: None)
    return CognitiveState(session_id="t")


def test_end_request_payload_discloses_quality_and_kept(monkeypatch):
    captured = {}
    cs = _fresh_state(monkeypatch, captured)
    cs.begin_request("test query", run_id="r1")
    cs.end_request("python_dev", outcome="completed",
                   quality=0.8234, kept="retry")

    assert captured["payload"]["confidence"] == 0.823
    assert captured["payload"]["evidence"] == "retry"


def test_end_request_payload_omits_keys_when_absent(monkeypatch):
    captured = {}
    cs = _fresh_state(monkeypatch, captured)
    cs.begin_request("test query", run_id="r1")
    cs.end_request("python_dev", outcome="completed")

    assert "confidence" not in captured["payload"]
    assert "evidence" not in captured["payload"]
