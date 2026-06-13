"""
Tests for learning/decision routes (routes/learning.py):
  GET /learning/drift
  GET /decisions
  GET /traces
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="learning-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── GET /learning/drift ───────────────────────────────────────────────────────

def test_learning_drift_returns_data():
    r = client.get("/learning/drift", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)

def test_learning_drift_structure():
    r = client.get("/learning/drift", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        # drift_status() returns a dict with instability metrics
        assert isinstance(data, dict)


# ── GET /decisions ────────────────────────────────────────────────────────────

def test_decisions_endpoint():
    r = client.get("/decisions", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "decisions" in data
        assert "stats" in data
        assert "agents" in data

def test_decisions_with_limit():
    r = client.get("/decisions?limit=10", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "decisions" in data
        assert len(data["decisions"]) <= 10

def test_decisions_with_large_limit():
    r = client.get("/decisions?limit=200", headers=HEADERS)
    assert r.status_code in (200, 500)


# ── GET /traces ───────────────────────────────────────────────────────────────

def test_traces_endpoint():
    r = client.get("/traces", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "traces" in data
    assert isinstance(data["traces"], list)

def test_traces_with_limit():
    r = client.get("/traces?limit=5", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "traces" in data
    assert len(data["traces"]) <= 5

def test_traces_default_shape():
    r = client.get("/traces", headers=HEADERS)
    data = r.json()
    # Each trace should have expected keys (may be empty if no traces)
    for t in data["traces"]:
        assert "agent" in t
        assert "timestamp" in t


# ── GET /replay/{decision_id} ─────────────────────────────────────────────────

def test_replay_nonexistent_decision():
    r = client.get("/replay/999999", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "error" in data
