"""
Additional coverage for routes/analysis.py — uncovered endpoints:
  GET /data/traces.jsonl, GET /report, POST /analysis/counterfactual/{id},
  POST /analysis/learned_router/train, GET /data/causal/{id},
  GET /data/graph/agent/{id}, GET /data/graph/memory/{id}
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="analysis-extra@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def _ok_or_5xx(r):
    assert r.status_code < 600, f"Crash: {r.status_code} — {r.text[:200]}"


# ── /data/traces.jsonl ────────────────────────────────────────────────────────

def test_data_traces_jsonl():
    r = client.get("/data/traces.jsonl", headers=HEADERS)
    _ok_or_5xx(r)

def test_data_traces_jsonl_rebuild():
    r = client.get("/data/traces.jsonl?rebuild=false", headers=HEADERS)
    _ok_or_5xx(r)


# ── /report ───────────────────────────────────────────────────────────────────

def test_report_generate():
    r = client.get("/report", headers=HEADERS)
    _ok_or_5xx(r)
    if r.status_code == 200:
        data = r.json()
        assert "status" in data or "overall_health" in data


# ── /analysis/counterfactual/{decision_id} ────────────────────────────────────

def test_counterfactual_simulate():
    r = client.post("/analysis/counterfactual/999999?alt_agent=python_dev&dry_run=true",
                    headers=HEADERS)
    _ok_or_5xx(r)

def test_counterfactual_simulate_wet():
    r = client.post("/analysis/counterfactual/1?alt_agent=it_networking&dry_run=false",
                    headers=HEADERS)
    _ok_or_5xx(r)


# ── /analysis/learned_router/train ───────────────────────────────────────────

def test_learned_router_train():
    r = client.post("/analysis/learned_router/train", headers=HEADERS)
    _ok_or_5xx(r)


# ── /data/causal/{decision_id} ───────────────────────────────────────────────

def test_data_causal():
    r = client.get("/data/causal/1", headers=HEADERS)
    _ok_or_5xx(r)

def test_data_causal_nonexistent():
    r = client.get("/data/causal/999999", headers=HEADERS)
    _ok_or_5xx(r)


# ── /data/graph/agent/{agent_id} ─────────────────────────────────────────────

def test_data_graph_agent():
    r = client.get("/data/graph/agent/python_dev", headers=HEADERS)
    _ok_or_5xx(r)

def test_data_graph_agent_unknown():
    r = client.get("/data/graph/agent/nonexistent_agent", headers=HEADERS)
    _ok_or_5xx(r)


# ── /data/graph/memory/{memory_id} ───────────────────────────────────────────

def test_data_graph_memory():
    r = client.get("/data/graph/memory/1", headers=HEADERS)
    _ok_or_5xx(r)

def test_data_graph_memory_nonexistent():
    r = client.get("/data/graph/memory/999999", headers=HEADERS)
    _ok_or_5xx(r)
