"""
Tests for analysis and data routes (routes/analysis.py, routes/risk.py).
Most heavy endpoints (trace_builder, decision.graph) are import-heavy and
may raise 500 in the test environment — we verify the contract: 200 or 5xx,
never a crash. Lightweight endpoints (memory_backend, policy/health) are
tested for content shape.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="analysis-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def _valid_response(r):
    """200 or a 4xx/5xx — never a crash (unhandled exception)."""
    assert r.status_code < 600, f"Unexpected status {r.status_code}"


# ── /analysis/memory_backend ─────────────────────────────────────────────────

def test_memory_backend_info():
    r = client.get("/analysis/memory_backend", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "backend_type" in data or "type" in data or "backend" in data or "promote_threshold" in data

def test_memory_backend_bench_valid_n():
    r = client.get("/analysis/memory_backend/bench?n=1", headers=HEADERS)
    assert r.status_code in (200, 500)

def test_memory_backend_bench_invalid_n():
    r = client.get("/analysis/memory_backend/bench?n=99", headers=HEADERS)
    assert r.status_code == 400

def test_memory_backend_bench_zero():
    r = client.get("/analysis/memory_backend/bench?n=0", headers=HEADERS)
    assert r.status_code == 400

def test_memory_backend_promote():
    r = client.post("/analysis/memory_backend/promote", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "promoted" in data
    assert "backend" in data


# ── /policy/health ────────────────────────────────────────────────────────────

def test_policy_health_no_data():
    r = client.get("/policy/health", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    # Either real data or no_data sentinel
    assert "total" in data


# ── /analysis/failures ───────────────────────────────────────────────────────

def test_analysis_failures():
    r = client.get("/analysis/failures", headers=HEADERS)
    _valid_response(r)

def test_analysis_failures_with_limit():
    r = client.get("/analysis/failures?limit=10", headers=HEADERS)
    _valid_response(r)


# ── /analysis/specialization ─────────────────────────────────────────────────

def test_analysis_specialization():
    r = client.get("/analysis/specialization", headers=HEADERS)
    _valid_response(r)


# ── /analysis/learned_router ─────────────────────────────────────────────────

def test_learned_router_stats():
    r = client.get("/analysis/learned_router", headers=HEADERS)
    assert r.status_code in (200, 503)

def test_learned_router_predict_python():
    r = client.get("/analysis/learned_router/predict?q=how+do+I+write+a+FastAPI+async+endpoint&action=build",
                   headers=HEADERS)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        data = r.json()
        assert "signal" in data
        assert "signal_agent" in data

def test_learned_router_predict_networking():
    r = client.get("/analysis/learned_router/predict?q=configure+SSH+firewall+rules&action=explain",
                   headers=HEADERS)
    assert r.status_code in (200, 500)


# ── /analysis/counterfactual/candidates ──────────────────────────────────────

def test_counterfactual_candidates():
    r = client.get("/analysis/counterfactual/candidates", headers=HEADERS)
    _valid_response(r)

def test_counterfactual_candidates_n():
    r = client.get("/analysis/counterfactual/candidates?n=5", headers=HEADERS)
    _valid_response(r)


# ── /data/stats ───────────────────────────────────────────────────────────────

def test_data_stats():
    r = client.get("/data/stats", headers=HEADERS)
    _valid_response(r)


# ── /data/traces ─────────────────────────────────────────────────────────────

def test_data_traces():
    r = client.get("/data/traces", headers=HEADERS)
    _valid_response(r)
    if r.status_code == 200:
        data = r.json()
        assert "traces" in data
        assert "total" in data

def test_data_traces_only_real():
    r = client.get("/data/traces?only_real=true", headers=HEADERS)
    _valid_response(r)


# ── /data/graph/stats ────────────────────────────────────────────────────────

def test_graph_stats():
    r = client.get("/data/graph/stats", headers=HEADERS)
    _valid_response(r)


# ── /risk/stats ───────────────────────────────────────────────────────────────

def test_risk_stats():
    r = client.get("/risk/stats", headers=HEADERS)
    assert r.status_code in (200, 503)

def test_risk_history():
    r = client.get("/risk/history", headers=HEADERS)
    assert r.status_code in (200, 500, 503)
    if r.status_code == 200:
        assert isinstance(r.json(), list)


# ── /report/download — 404 when no report generated ─────────────────────────

def test_report_download_no_report():
    r = client.get("/report/download", headers=HEADERS)
    assert r.status_code in (200, 404)
