"""
Tests for task queue routes (routes/tasks.py).
Tests task CRUD without triggering the async worker (which calls Ollama).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="tasks-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── POST /tasks/create ────────────────────────────────────────────────────────

def test_create_task_basic():
    r = client.post("/tasks/create", json={"title": "Test Task", "prompt": "Explain Python asyncio"},
                    headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert data["title"] == "Test Task"

def test_create_task_no_prompt():
    r = client.post("/tasks/create", json={"title": "Empty"}, headers=HEADERS)
    assert r.status_code == 200
    assert "error" in r.json()

def test_create_task_with_agents():
    r = client.post("/tasks/create",
                    json={"title": "Agent Task", "prompt": "Write a FastAPI handler",
                          "agents": ["python_dev"]},
                    headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data

def test_create_task_default_title():
    r = client.post("/tasks/create", json={"prompt": "Some task prompt here"}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Untitled"

def test_create_multiple_tasks():
    ids = []
    for i in range(3):
        r = client.post("/tasks/create",
                        json={"title": f"Task {i}", "prompt": f"Prompt number {i}"},
                        headers=HEADERS)
        assert r.status_code == 200
        ids.append(r.json()["task_id"])
    assert len(set(ids)) == 3  # all unique IDs


# ── GET /tasks/status ─────────────────────────────────────────────────────────

def test_task_status_list():
    r = client.get("/tasks/status", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)

def test_task_status_shows_created_task():
    client.post("/tasks/create", json={"title": "Visible Task", "prompt": "visible prompt"},
                headers=HEADERS)
    r = client.get("/tasks/status", headers=HEADERS)
    tasks = r.json()["tasks"]
    titles = [t["title"] for t in tasks]
    assert "Visible Task" in titles


# ── GET /tasks/results/{task_id} ──────────────────────────────────────────────

def test_task_results_existing():
    r = client.post("/tasks/create", json={"title": "Result Task", "prompt": "result prompt"},
                    headers=HEADERS)
    task_id = r.json()["task_id"]

    r = client.get(f"/tasks/results/{task_id}", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == task_id
    assert data["status"] == "pending"
    assert data["title"] == "Result Task"

def test_task_results_not_found():
    r = client.get("/tasks/results/999999", headers=HEADERS)
    assert r.status_code == 200
    assert "error" in r.json()


# ── DELETE /tasks/{task_id} ───────────────────────────────────────────────────

def test_delete_pending_task():
    r = client.post("/tasks/create", json={"title": "Delete Me", "prompt": "to delete"},
                    headers=HEADERS)
    task_id = r.json()["task_id"]

    r = client.delete(f"/tasks/{task_id}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["deleted"] == task_id

def test_delete_nonexistent_task():
    r = client.delete("/tasks/999999", headers=HEADERS)
    assert r.status_code == 200
    assert "error" in r.json()


# ── POST /tasks/run ───────────────────────────────────────────────────────────

def test_tasks_run_trigger():
    r = client.post("/tasks/run", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "message" in data


# ── Backpressure + queue-depth observability (#198) ───────────────────────────

def test_status_reports_queue_depth():
    data = client.get("/tasks/status", headers=HEADERS).json()
    assert isinstance(data.get("queue_depth"), int)
    assert "queue_limit" in data
    assert "worker_running" in data


def test_queue_backpressure_returns_429(monkeypatch):
    import routes.tasks as t
    # Cap exactly one above the current pending depth: the next create fills the
    # queue, the one after is shed with 429.
    depth0 = client.get("/tasks/status", headers=HEADERS).json()["queue_depth"]
    monkeypatch.setattr(t, "MAX_PENDING_TASKS", depth0 + 1)

    r1 = client.post("/tasks/create", json={"prompt": "fits exactly"}, headers=HEADERS)
    assert r1.status_code == 200

    r2 = client.post("/tasks/create", json={"prompt": "overflow"}, headers=HEADERS)
    assert r2.status_code == 429
    assert "queue full" in r2.json()["error"]


def test_backpressure_disabled_when_zero(monkeypatch):
    import routes.tasks as t
    monkeypatch.setattr(t, "MAX_PENDING_TASKS", 0)  # 0 disables the cap
    r = client.post("/tasks/create", json={"prompt": "always allowed"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
