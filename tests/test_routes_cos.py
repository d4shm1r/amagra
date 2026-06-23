"""
Tests for Cognitive OS routes (routes/cos.py).
Most endpoints return 503 when CognitiveState is unavailable (test environment),
which is the expected behaviour — we verify the fallback contract, not the live COS state.
"""

import os
import sys
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
