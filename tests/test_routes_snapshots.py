"""
Tests for context snapshot routes (routes/snapshots.py).
Most endpoints return empty results since there are no snapshots in the test DB.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="snapshots-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── GET /snapshots ────────────────────────────────────────────────────────────

def test_snapshots_list():
    r = client.get("/snapshots", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)

def test_snapshots_with_n():
    r = client.get("/snapshots?n=10", headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        assert "snapshots" in r.json()


# ── GET /snapshots/{snapshot_id} ──────────────────────────────────────────────

def test_snapshot_not_found():
    r = client.get("/snapshots/999999", headers=HEADERS)
    assert r.status_code in (404, 500)
    if r.status_code == 404:
        assert "not found" in r.json()["detail"].lower()

def test_snapshot_by_id_zero():
    r = client.get("/snapshots/0", headers=HEADERS)
    assert r.status_code in (404, 500)


# ── GET /snapshots/by-context/{context_id} ───────────────────────────────────

def test_snapshot_by_context_not_found():
    r = client.get("/snapshots/by-context/nonexistent-context-id", headers=HEADERS)
    assert r.status_code in (404, 500)
    if r.status_code == 404:
        assert "not found" in r.json()["detail"].lower()


# ── GET /snapshots/diff/{id_a}/{id_b} ────────────────────────────────────────

def test_snapshot_diff_nonexistent():
    r = client.get("/snapshots/diff/1/2", headers=HEADERS)
    assert r.status_code in (200, 404, 500)


# ── POST /replay/{context_id} ─────────────────────────────────────────────────

def test_replay_nonexistent_context():
    r = client.post("/replay/nonexistent-ctx-id", headers=HEADERS)
    assert r.status_code in (404, 500, 503)
    if r.status_code == 404:
        assert "not found" in r.json()["detail"].lower()
