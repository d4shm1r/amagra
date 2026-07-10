"""
Additional routes/core.py coverage — tests for non-LLM endpoints:
  GET /          root
  GET /health    health check (Ollama offline in CI → degraded, not a failure)
  GET /agents    static agent list
  GET /runs      run tracer
  GET /runs/{run_id}  404 on unknown
  GET /threads   thread list
  DELETE /threads/{id}  delete thread
  GET /telemetry/routing  routing telemetry
  GET /history   session history
  DELETE /history  clear history
  GET /logs      log reader
  GET /status    system status
  GET /metrics   full metrics
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="core-extra@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_root():
    # "/" now serves the bundled UI (single-origin desktop mode). When a build
    # is present it returns the HTML shell; with no build, api.py falls back to a
    # JSON status. Either way the root must answer 200 — machine clients use
    # /health or /status for structured data.
    r = client.get("/", headers=HEADERS)
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    if "application/json" in ctype:
        assert r.json()["status"] == "online"
    else:
        assert "html" in ctype


# ── GET /health ───────────────────────────────────────────────────────────────

def test_health_returns_dict():
    r = client.get("/health", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "model" in data
    assert "agents" in data
    assert "ollama" in data
    # Ollama is offline in tests — degraded is expected
    assert data["status"] in ("online", "degraded")

def test_health_memory_key():
    r = client.get("/health", headers=HEADERS)
    data = r.json()
    assert "memory" in data

def test_health_intelligence_block():
    r = client.get("/health", headers=HEADERS)
    data = r.json()
    assert "intelligence" in data
    intel = data["intelligence"]
    assert "brain_provider" in intel
    assert "claude_available" in intel


# ── GET /agents ───────────────────────────────────────────────────────────────

def test_agents_list():
    r = client.get("/agents", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "agents" in data
    agents = {a["id"]: a for a in data["agents"]}
    assert "python_dev" in agents
    assert "it_networking" in agents
    assert "ai_ml" in agents

def test_agents_have_required_fields():
    r = client.get("/agents", headers=HEADERS)
    for agent in r.json()["agents"]:
        assert "id" in agent
        assert "label" in agent
        assert "role" in agent


# ── GET /runs ─────────────────────────────────────────────────────────────────

def test_runs_list():
    r = client.get("/runs", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "runs" in data
    assert isinstance(data["runs"], list)

def test_runs_with_limit():
    r = client.get("/runs?limit=5", headers=HEADERS)
    assert r.status_code == 200

def test_runs_similar_by_cause():
    r = client.get("/runs/similar/connection_refused", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "root_cause" in data
    assert "runs" in data

def test_runs_get_nonexistent():
    r = client.get("/runs/nonexistent-run-id-xyz", headers=HEADERS)
    assert r.status_code == 404


# ── GET /threads ──────────────────────────────────────────────────────────────

def test_threads_list():
    r = client.get("/threads", headers=HEADERS)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "threads" in data

def test_threads_get_turns():
    r = client.get("/threads/nonexistent-thread/turns", headers=HEADERS)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "turns" in data
        assert data["turns"] == []

def test_threads_delete():
    r = client.delete("/threads/nonexistent-thread-id", headers=HEADERS)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert "deleted" in r.json()


# ── GET /telemetry/routing ────────────────────────────────────────────────────

def test_telemetry_routing():
    r = client.get("/telemetry/routing", headers=HEADERS)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "total" in data
        # Signed, mode-resolved stability field (#74 task 5.3): always present
        # and well-formed. 'flat' until the log carries adaptive-α; a live
        # neutral mode names an agent with regime in the signed set.
        assert "neutral_mode" in data
        nm = data["neutral_mode"]
        assert set(nm) == {"agent", "K", "signed_drift", "regime"}
        assert nm["regime"] in {
            "stabilizing", "destabilizing", "neutral", "flat"
        }
        if nm["agent"] is None:
            assert nm["regime"] == "flat"


# ── GET /history ──────────────────────────────────────────────────────────────

def test_history():
    r = client.get("/history", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "history" in data
    assert isinstance(data["history"], list)


# ── DELETE /history ───────────────────────────────────────────────────────────

def test_clear_history():
    r = client.delete("/history", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"


# ── GET /logs ─────────────────────────────────────────────────────────────────

def test_logs():
    r = client.get("/logs", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data


# ── GET /status ───────────────────────────────────────────────────────────────

def test_status():
    r = client.get("/status", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "memories" in data
    assert "tasks" in data
    assert "model" in data
    task_data = data["tasks"]
    assert "done" in task_data
    assert "pending" in task_data


# ── GET /metrics ──────────────────────────────────────────────────────────────

def test_metrics():
    r = client.get("/metrics", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "memory" in data
    assert "tasks" in data
    assert "traces" in data
    assert "learning" in data

def test_metrics_memory_keys():
    r = client.get("/metrics", headers=HEADERS)
    mem = r.json()["memory"]
    assert "total" in mem
    assert "by_agent" in mem
    assert "prune_candidates" in mem
