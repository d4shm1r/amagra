"""
Tests for maintenance routes:
  GET  /maintenance/status
  POST /maintenance/run

The background maintenance loop is not tested (requires asyncio). We test:
- status endpoint returns expected structure before any run
- run endpoint returns trigger confirmation
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="maint-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def test_maintenance_status_structure():
    r = client.get("/maintenance/status", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "interval_s" in data
    assert "runs_total" in data
    assert "last_run" in data
    assert "last_actions" in data
    assert isinstance(data["last_actions"], list)
    assert data["interval_s"] == 300


def test_maintenance_status_initial_state():
    r = client.get("/maintenance/status", headers=HEADERS)
    data = r.json()
    # Before any manual run, runs_total is 0 (or already incremented by background task)
    assert isinstance(data["runs_total"], int)
    assert data["runs_total"] >= 0


def test_maintenance_run_triggers():
    r = client.post("/maintenance/run", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "triggered"
    assert "maintenance/status" in data["message"]


def test_maintenance_status_after_run():
    client.post("/maintenance/run", headers=HEADERS)
    # Check the status endpoint again — structure should still be valid
    r = client.get("/maintenance/status", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "runs_total" in data
    assert "last_actions" in data
