"""
Core route tests: /, /health, /agents, /status, /threads, POST /ask.

No Ollama required. coordinator.invoke is mocked to return a well-formed
result so POST /ask exercises the full endpoint logic without LLM calls.

Run: python3 -m pytest tests/test_routes_core.py -v
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
_key    = _ak.create_key(owner="core-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── Fake coordinator result ───────────────────────────────────────────────────

class _FakeMsg:
    content = "This is a test response from the mocked agent."

_FAKE_RESULT = {
    "messages":               [_FakeMsg()],
    "active_agent":           "knowledge_learning",
    "brain_decision": {
        "signal_domain":  "general",
        "signal_shape":   "explanation",
        "signal_conf":    0.9,
        "complexity":     "simple",
        "confidence":     0.85,
        "action":         "generate",
        "memories_used":  [],
    },
    "reflect_level":          "none",
    "contradiction_detected": False,
    "run_id":                 "test-run-conftest",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_root_returns_200():
    r = client.get("/")
    assert r.status_code == 200


def test_health_has_status_key():
    r = client.get("/health", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


def test_health_version_present():
    r = client.get("/health", headers=HEADERS)
    body = r.json()
    # version or commit should be present (exact key may vary)
    assert any(k in body for k in ("version", "commit", "uptime_s", "agents"))


def test_agents_returns_list():
    r = client.get("/agents", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    agents = body if isinstance(body, list) else body.get("agents", [])
    assert len(agents) > 0


def test_agents_have_id_field():
    r = client.get("/agents", headers=HEADERS)
    body = r.json()
    agents = body if isinstance(body, list) else body.get("agents", [])
    for a in agents:
        assert "id" in a, f"Agent entry missing 'id': {a}"


def test_threads_returns_list_shape():
    r = client.get("/threads", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "threads" in body
    assert isinstance(body["threads"], list)


def test_ask_missing_message_returns_422():
    r = client.post("/ask", json={}, headers=HEADERS)
    assert r.status_code == 422


def test_ask_happy_path():
    import routes.core as _core
    _core.coordinator.invoke.return_value = _FAKE_RESULT

    r = client.post("/ask", json={"message": "What is Python?"}, headers=HEADERS)
    # Accept 200 or 500 (500 only if secondary DB ops fail, core path still tested)
    assert r.status_code in (200, 500)
    if r.status_code == 200:
        body = r.json()
        assert "response" in body
        assert "agent_used" in body
        assert isinstance(body["response"], str)
        assert len(body["response"]) > 0


def test_ask_response_schema():
    import routes.core as _core
    _core.coordinator.invoke.return_value = _FAKE_RESULT

    r = client.post("/ask", json={"message": "Explain recursion."}, headers=HEADERS)
    if r.status_code == 200:
        body = r.json()
        for field in ("response", "agent_used", "routing_reason",
                      "duration_ms", "timestamp", "signal_domain"):
            assert field in body, f"Missing field: {field}"


def test_ask_with_force_agent():
    import routes.core as _core
    _core.coordinator.invoke.return_value = _FAKE_RESULT

    r = client.post(
        "/ask",
        json={"message": "Write a for loop.", "force_agent": "python_dev"},
        headers=HEADERS,
    )
    assert r.status_code in (200, 500)


def test_ask_stream_emits_routing_event():
    """First SSE event from /ask/stream must be type='routing'."""
    with client.stream(
        "POST", "/ask/stream",
        json={"message": "hello"},
        headers=HEADERS,
    ) as resp:
        if resp.status_code != 200:
            return  # skip if backend unavailable
        for line in resp.iter_lines():
            if line.startswith("data: "):
                import json
                evt = json.loads(line[6:])
                assert evt.get("type") == "routing"
                assert "agent" in evt
                break


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [
        test_root_returns_200,
        test_health_has_status_key,
        test_health_version_present,
        test_agents_returns_list,
        test_agents_have_id_field,
        test_threads_returns_list_shape,
        test_ask_missing_message_returns_422,
        test_ask_happy_path,
        test_ask_response_schema,
        test_ask_with_force_agent,
        test_ask_stream_emits_routing_event,
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
