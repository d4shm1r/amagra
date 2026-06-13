"""
Tests for task queue routes (routes/tasks.py).
Tests task CRUD without triggering the async worker (which calls Ollama).
"""

import os, sys
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
