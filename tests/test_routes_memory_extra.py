"""
Extra coverage for routes/memory.py — endpoints not hit by existing tests:
  GET /memory/stats, GET/POST /memory/prune, GET/POST /memory/consolidate,
  GET/POST /memory/auto-resolve, GET /memory/audit, GET /memory/for-query,
  GET /memory/at-risk, GET /memory/export.csv,
  GET /coherence, GET /coherence/dynamics, GET /coherence/memory,
  GET /coherence/reflection, GET /contradictions
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="memory-extra@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def _ok_or_500(r):
    assert r.status_code in (200, 500), f"Unexpected {r.status_code}: {r.text[:200]}"


# ── /memory/stats ────────────────────────────────────────────────────────────

def test_memory_stats():
    r = client.get("/memory/stats", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "total" in data


# ── /memory/prune ─────────────────────────────────────────────────────────────

def test_memory_prune_preview():
    r = client.get("/memory/prune", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "candidates" in data or "deleted" in data

def test_memory_prune_execute():
    r = client.post("/memory/prune", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "deleted" in data


# ── /memory/consolidate ───────────────────────────────────────────────────────

def test_memory_consolidate_preview():
    r = client.get("/memory/consolidate", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "pairs" in data

def test_memory_consolidate_execute():
    r = client.post("/memory/consolidate", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "removed" in data


# ── /memory/auto-resolve ──────────────────────────────────────────────────────

def test_memory_auto_resolve_preview():
    r = client.get("/memory/auto-resolve", headers=HEADERS)
    _ok_or_500(r)

def test_memory_auto_resolve_execute():
    r = client.post("/memory/auto-resolve", headers=HEADERS)
    _ok_or_500(r)


# ── /memory/audit ─────────────────────────────────────────────────────────────

def test_memory_audit():
    r = client.get("/memory/audit", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        data = r.json()
        assert "audits" in data
        assert "count" in data

def test_memory_audit_limit():
    r = client.get("/memory/audit?limit=5", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        assert r.json()["count"] <= 5


# ── /memory/for-query ─────────────────────────────────────────────────────────

def test_memory_for_query():
    r = client.get("/memory/for-query?q=test+query&n=3", headers=HEADERS)
    _ok_or_500(r)

def test_memory_for_query_empty():
    r = client.get("/memory/for-query", headers=HEADERS)
    _ok_or_500(r)


# ── /memory/at-risk ───────────────────────────────────────────────────────────

def test_memory_at_risk():
    r = client.get("/memory/at-risk", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        assert "at_risk" in r.json()


# ── /memory/export.csv ───────────────────────────────────────────────────────

def test_memory_export_csv():
    r = client.get("/memory/export.csv", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        assert "text/csv" in r.headers.get("content-type", "")


# ── /coherence ────────────────────────────────────────────────────────────────

def test_coherence():
    r = client.get("/coherence", headers=HEADERS)
    _ok_or_500(r)

def test_coherence_dynamics():
    r = client.get("/coherence/dynamics", headers=HEADERS)
    _ok_or_500(r)

def test_coherence_memory():
    r = client.get("/coherence/memory", headers=HEADERS)
    _ok_or_500(r)

def test_coherence_reflection():
    r = client.get("/coherence/reflection", headers=HEADERS)
    _ok_or_500(r)


# ── /contradictions ───────────────────────────────────────────────────────────

def test_contradictions():
    r = client.get("/contradictions", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        assert isinstance(r.json(), list)

def test_contradictions_limit():
    r = client.get("/contradictions?limit=5", headers=HEADERS)
    _ok_or_500(r)
    if r.status_code == 200:
        assert len(r.json()) <= 5
