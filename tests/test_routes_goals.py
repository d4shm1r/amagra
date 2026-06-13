"""
Tests for routes/goals.py — task graph CRUD endpoints.
Uses TestClient with mocked infrastructure.task_graph functions.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest.mock as mock
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="goals-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── POST /goals/create ────────────────────────────────────────────────────────

def test_goal_create_valid():
    with mock.patch("routes.goals.create_graph", return_value=42):
        r = client.post("/goals/create", json={"goal": "Deploy app", "steps": ["build", "push", "deploy"]}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["goal_id"] == 42
    assert data["status"] == "pending"
    assert data["steps"] == 3

def test_goal_create_missing_goal():
    r = client.post("/goals/create", json={"steps": ["a"]}, headers=HEADERS)
    assert r.status_code == 400

def test_goal_create_empty_goal():
    r = client.post("/goals/create", json={"goal": "  ", "steps": ["a"]}, headers=HEADERS)
    assert r.status_code == 400

def test_goal_create_missing_steps():
    r = client.post("/goals/create", json={"goal": "Deploy app"}, headers=HEADERS)
    assert r.status_code == 400

def test_goal_create_empty_steps():
    r = client.post("/goals/create", json={"goal": "Deploy app", "steps": []}, headers=HEADERS)
    assert r.status_code == 400

def test_goal_create_value_error():
    with mock.patch("routes.goals.create_graph", side_effect=ValueError("bad steps")):
        r = client.post("/goals/create", json={"goal": "Deploy app", "steps": ["a"]}, headers=HEADERS)
    assert r.status_code == 400
    assert "bad steps" in r.json()["detail"]


# ── GET /goals ────────────────────────────────────────────────────────────────

def test_goals_list():
    with mock.patch("routes.goals.list_graphs", return_value=[]):
        r = client.get("/goals", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["goals"] == []

def test_goals_list_returns_items():
    fake = [{"id": 1, "goal": "Deploy", "status": "pending"}]
    with mock.patch("routes.goals.list_graphs", return_value=fake):
        r = client.get("/goals", headers=HEADERS)
    assert r.status_code == 200
    assert len(r.json()["goals"]) == 1


# ── GET /goals/{goal_id} ──────────────────────────────────────────────────────

def test_goal_get_not_found():
    with mock.patch("routes.goals.get_graph", return_value=None):
        r = client.get("/goals/999", headers=HEADERS)
    assert r.status_code == 404

def test_goal_get_found():
    fake = {"id": 1, "goal": "Deploy app", "status": "pending", "steps": []}
    with mock.patch("routes.goals.get_graph", return_value=fake):
        r = client.get("/goals/1", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["goal"] == "Deploy app"


# ── POST /goals/{goal_id}/run ─────────────────────────────────────────────────

def test_goal_run_not_found():
    with mock.patch("routes.goals.get_graph", return_value=None):
        r = client.post("/goals/999/run", headers=HEADERS)
    assert r.status_code == 404

def test_goal_run_already_running():
    fake = {"id": 1, "goal": "Deploy", "status": "running"}
    with mock.patch("routes.goals.get_graph", return_value=fake):
        r = client.post("/goals/1/run", headers=HEADERS)
    assert r.status_code == 200
    assert "already running" in r.json()["message"]

def test_goal_run_already_completed():
    fake = {"id": 1, "goal": "Deploy", "status": "completed"}
    with mock.patch("routes.goals.get_graph", return_value=fake):
        r = client.post("/goals/1/run", headers=HEADERS)
    assert r.status_code == 200
    assert "already completed" in r.json()["message"]


# ── DELETE /goals/{goal_id} ───────────────────────────────────────────────────

def test_goal_delete_not_found():
    with mock.patch("routes.goals.get_graph", return_value=None):
        r = client.delete("/goals/999", headers=HEADERS)
    assert r.status_code == 404

def test_goal_delete_running():
    fake = {"id": 1, "goal": "Deploy", "status": "running"}
    with mock.patch("routes.goals.get_graph", return_value=fake):
        r = client.delete("/goals/1", headers=HEADERS)
    assert r.status_code == 400


# ── POST /goals/{goal_id}/retry/{step_id} ────────────────────────────────────

def test_goal_retry_step_not_failed():
    with mock.patch("routes.goals.retry_step", return_value=False):
        r = client.post("/goals/1/retry/step-1", headers=HEADERS)
    assert r.status_code == 400
