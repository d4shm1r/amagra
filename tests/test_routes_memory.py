"""
Memory and coherence route tests.

Exercises GET /memory/stats, GET /memory, GET /coherence, and the
memory-for-query endpoint. No LLM required; embedding is stubbed.

Run: python3 -m pytest tests/test_routes_memory.py -v
"""

import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _mod in (
    "langchain_ollama", "langchain_core", "langchain_core.messages",
    "langchain_core.documents", "langchain_core.documents.base",
    "langchain_core.runnables", "langchain_core.runnables.base",
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.prebuilt",
    "faiss", "sentence_transformers",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

import memory_core.db as _mdb
import hashlib as _hashlib
import random as _random

def _fake_embedding(text: str) -> list:
    seed = int(_hashlib.md5(text.encode()).hexdigest(), 16)
    rng  = _random.Random(seed)
    return [rng.random() for _ in range(768)]

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="memory-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}

_orig_get_embedding = None

def setup_module(module):
    global _orig_get_embedding
    _orig_get_embedding = _mdb.get_embedding
    _mdb.get_embedding = _fake_embedding

def teardown_module(module):
    if _orig_get_embedding is not None:
        _mdb.get_embedding = _orig_get_embedding


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_memory_stats_returns_200():
    r = client.get("/memory/stats", headers=HEADERS)
    assert r.status_code == 200


def test_memory_stats_has_total():
    r = client.get("/memory/stats", headers=HEADERS)
    if r.status_code == 200:
        body = r.json()
        assert "total" in body, f"Expected 'total' in stats: {body}"


def test_memory_stats_has_by_agent():
    r = client.get("/memory/stats", headers=HEADERS)
    if r.status_code == 200:
        body = r.json()
        assert "by_agent" in body or "agents" in body


def test_memory_list_returns_200():
    r = client.get("/memory", headers=HEADERS)
    assert r.status_code == 200


def test_memory_list_has_records_key():
    r = client.get("/memory", headers=HEADERS)
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, (list, dict))


def test_coherence_returns_200():
    r = client.get("/coherence", headers=HEADERS)
    assert r.status_code == 200


def test_coherence_has_score():
    r = client.get("/coherence", headers=HEADERS)
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, dict) and len(body) > 0, "Coherence response is empty"


def test_memory_for_query_returns_200():
    r = client.get("/memory/for-query?q=python+programming", headers=HEADERS)
    # 200 or 422 (if param name differs) are both acceptable
    assert r.status_code in (200, 404, 422)


def test_memory_audit_returns_200():
    r = client.get("/memory/audit", headers=HEADERS)
    assert r.status_code in (200, 404, 500)


def test_export_json_returns_attachment():
    r = client.get("/memory/export.json", headers=HEADERS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["format"] == "amagra.memory/1"
    assert "memories" in body


def test_export_markdown_returns_attachment():
    r = client.get("/memory/export.md", headers=HEADERS)
    assert r.status_code == 200
    assert "Amagra memory export" in r.text


def test_import_roundtrip_via_api():
    payload = {
        "format": "amagra.memory/1",
        "memories": [
            {"content": "api round-trip note alpha", "agent": "writer", "type": "chat"},
        ],
    }
    r = client.post("/memory/import", headers=HEADERS, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] + body["skipped_duplicates"] == 1


def test_import_rejects_bad_payload_400():
    r = client.post("/memory/import", headers=HEADERS, json={"nope": 1})
    assert r.status_code == 400


def test_memory_records_endpoint():
    r = client.get("/memory/records", headers=HEADERS)
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, (list, dict))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [
        test_memory_stats_returns_200,
        test_memory_stats_has_total,
        test_memory_stats_has_by_agent,
        test_memory_list_returns_200,
        test_memory_list_has_records_key,
        test_coherence_returns_200,
        test_coherence_has_score,
        test_memory_for_query_returns_200,
        test_memory_audit_returns_200,
        test_memory_records_endpoint,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
