"""
Feedback route tests: POST /feedback and GET /feedback.

No LLM required. Exercises the full DB write → read cycle.

Run: python3 -m pytest tests/test_routes_feedback.py -v
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

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="feedback-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


_SAMPLE_FEEDBACK = {
    "query":    "What is a neural network?",
    "response": "A neural network is a system of interconnected nodes.",
    "agent":    "ai_ml",
    "rating":   1,
    "note":     "Great explanation",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_submit_positive_feedback():
    r = client.post("/feedback", json=_SAMPLE_FEEDBACK, headers=HEADERS)
    assert r.status_code == 200


def test_submit_negative_feedback():
    r = client.post("/feedback", json={**_SAMPLE_FEEDBACK, "rating": -1, "note": "Too vague"}, headers=HEADERS)
    assert r.status_code == 200


def test_invalid_rating_returns_400():
    r = client.post("/feedback", json={**_SAMPLE_FEEDBACK, "rating": 0}, headers=HEADERS)
    assert r.status_code == 400


def test_get_feedback_returns_list():
    r = client.get("/feedback", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    # Response is a list or has a "feedback" / "items" key
    assert isinstance(body, (list, dict))


def test_submitted_feedback_appears_in_list():
    unique_query = "Unique query for feedback retrieval test XYZ789"
    client.post("/feedback", json={**_SAMPLE_FEEDBACK, "query": unique_query}, headers=HEADERS)
    r = client.get("/feedback", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    records = body if isinstance(body, list) else body.get("feedback", body.get("items", []))
    queries = [rec.get("query", "") for rec in records]
    assert any(unique_query in q for q in queries), "Submitted feedback not found in GET /feedback"


def test_get_feedback_limit_param():
    r = client.get("/feedback?limit=3", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    records = body if isinstance(body, list) else body.get("feedback", body.get("items", []))
    assert len(records) <= 3


def test_feedback_record_has_expected_fields():
    client.post("/feedback", json=_SAMPLE_FEEDBACK, headers=HEADERS)
    r = client.get("/feedback?limit=1", headers=HEADERS)
    body = r.json()
    records = body if isinstance(body, list) else body.get("feedback", body.get("items", []))
    if records:
        rec = records[0]
        for field in ("query", "agent", "rating"):
            assert field in rec, f"Missing field '{field}' in feedback record"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [
        test_submit_positive_feedback,
        test_submit_negative_feedback,
        test_invalid_rating_returns_400,
        test_get_feedback_returns_list,
        test_submitted_feedback_appears_in_list,
        test_get_feedback_limit_param,
        test_feedback_record_has_expected_fields,
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
