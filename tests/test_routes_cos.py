"""
Tests for Cognitive OS routes (routes/cos.py).
Most endpoints return 503 when CognitiveState is unavailable (test environment),
which is the expected behaviour — we verify the fallback contract, not the live COS state.
"""

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="cos-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def _ok_or_503(r):
    assert r.status_code in (200, 503), f"Unexpected status {r.status_code}: {r.text}"


# ── /plan/graph ───────────────────────────────────────────────────────────────

def test_plan_graph_no_cos():
    r = client.get("/plan/graph", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
    else:
        assert r.status_code == 503


def test_plan_graph_returns_empty_when_no_plan():
    r = client.get("/plan/graph", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        # No plan active in tests
        assert data["nodes"] == []
        assert data["edges"] == []


# ── /cos/state ────────────────────────────────────────────────────────────────

def test_cos_state():
    r = client.get("/cos/state", headers=HEADERS)
    _ok_or_503(r)


# ── /cos/world ────────────────────────────────────────────────────────────────

def test_cos_world():
    r = client.get("/cos/world", headers=HEADERS)
    _ok_or_503(r)

def test_cos_world_with_org_param():
    r = client.get("/cos/world?org=org-testid", headers=HEADERS)
    _ok_or_503(r)


# ── /cos/events ───────────────────────────────────────────────────────────────

def test_cos_events():
    r = client.get("/cos/events", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        assert "events" in r.json()

def test_cos_events_with_n_param():
    r = client.get("/cos/events?n=5", headers=HEADERS)
    _ok_or_503(r)


# ── /cos/events/stream ───────────────────────────────────────────────────────
# `max_seconds` bounds the connection so the test client (which reads the
# response to completion, it doesn't do half-duplex streaming) gets a
# terminating body instead of hanging on an endpoint designed to stay open.

def _frames(text):
    return [json.loads(line[len("data: "):])
            for line in text.splitlines() if line.startswith("data: ")]


def test_cos_events_stream_opens_and_closes():
    r = client.get(
        "/cos/events/stream?max_seconds=0.05&health_interval=0&backlog=0",
        headers=HEADERS,
    )
    assert r.status_code == 200
    types = [f["type"] for f in _frames(r.text)]
    assert types[0] == "stream.connected"
    assert types[-1] == "stream.closed"


def test_cos_events_stream_sends_backlog():
    from infrastructure.event_bus import emit, EventType
    emit(EventType.SESSION_STARTED, {"note": "backlog-probe"})

    r = client.get(
        "/cos/events/stream?max_seconds=0.05&health_interval=0&backlog=5",
        headers=HEADERS,
    )
    frames = _frames(r.text)
    backlog = next(f for f in frames if f["type"] == "stream.backlog")
    assert isinstance(backlog["events"], list)


def test_cos_events_stream_forwards_live_bus_event():
    from infrastructure.event_bus import emit, EventType

    def _emit_soon():
        time.sleep(0.15)
        emit(EventType.SESSION_STARTED, {"note": "live-probe-xyz"}, persist=False)

    threading.Thread(target=_emit_soon, daemon=True).start()
    r = client.get(
        "/cos/events/stream?max_seconds=0.6&health_interval=0&backlog=0",
        headers=HEADERS,
    )
    frames = _frames(r.text)
    matches = [f for f in frames
               if f.get("payload", {}).get("note") == "live-probe-xyz"]
    assert matches, frames


def test_cos_events_stream_health_tick():
    # The poll loop sleeps in 0.3s ticks, so max_seconds must span at least
    # one full tick past health_interval for a tick to have a chance to fire.
    r = client.get(
        "/cos/events/stream?max_seconds=1.0&health_interval=0.05&backlog=0",
        headers=HEADERS,
    )
    types = [f["type"] for f in _frames(r.text)]
    assert "health.tick" in types


# ── /cos/uci ─────────────────────────────────────────────────────────────────

def test_cos_uci():
    r = client.get("/cos/uci", headers=HEADERS)
    _ok_or_503(r)

def test_cos_uci_hierarchical():
    r = client.get("/cos/uci/hierarchical", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        # routing accuracy must disclose whether it is measured or assumed
        rel = r.json()["layers"]["reliability"]
        assert rel["routing_accuracy_source"] in ("measured", "assumed_constant")

def test_cos_uci_trajectory():
    r = client.get("/cos/uci/trajectory?n=50", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        data = r.json()
        assert "history" in data and "curvature" in data
        assert "peak_abs_curvature" in data["curvature"]
        assert "bending" in data["curvature"]


# ── /cos/skills ───────────────────────────────────────────────────────────────

def test_cos_skills_all():
    r = client.get("/cos/skills", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        data = r.json()
        assert "skills" in data
        assert "total" in data

def test_cos_skills_with_query():
    r = client.get("/cos/skills?query=python", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        data = r.json()
        assert "query" in data
        assert "matches" in data


# ── /verify/stats ─────────────────────────────────────────────────────────────

def test_verify_stats():
    r = client.get("/verify/stats", headers=HEADERS)
    _ok_or_503(r)


# ── /verify/recent ────────────────────────────────────────────────────────────

def test_verify_recent():
    r = client.get("/verify/recent", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        assert "verifications" in r.json()

def test_verify_recent_with_n():
    r = client.get("/verify/recent?n=5", headers=HEADERS)
    _ok_or_503(r)


# ── /cos/suggestions ─────────────────────────────────────────────────────────

def test_cos_suggestions():
    r = client.get("/cos/suggestions", headers=HEADERS)
    _ok_or_503(r)


# ── /agents/status ────────────────────────────────────────────────────────────

def test_agents_status():
    r = client.get("/agents/status", headers=HEADERS)
    _ok_or_503(r)
    if r.status_code == 200:
        data = r.json()
        assert "agents" in data
        assert "ts" in data
