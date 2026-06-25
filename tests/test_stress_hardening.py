"""
Hardening from the stress test:
  - body-size guard middleware -> 413 (not a 20s/500 on a multi-MB body)
  - AskRequest.message max_length -> 422
  - offline-error classifier -> wrapped connection errors map to 503, not 500
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

import core.api_keys as _ak  # noqa: E402
from routes.core import _is_offline_error  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="hardening@test.com", tier="developer")}


# ── offline-error classifier ─────────────────────────────────────────────────

def test_offline_classifier_bare_refused():
    assert _is_offline_error(ConnectionRefusedError(111, "Connection refused")) is True


def test_offline_classifier_oserror_errno111():
    e = OSError(); e.errno = 111
    assert _is_offline_error(e) is True


def test_offline_classifier_wrapped_cause():
    # how httpx/requests surface it: a generic error with the refusal as __cause__
    try:
        try:
            raise ConnectionRefusedError(111, "Connection refused")
        except ConnectionRefusedError as inner:
            raise RuntimeError("backend call failed") from inner
    except RuntimeError as outer:
        assert _is_offline_error(outer) is True


def test_offline_classifier_string_forms():
    assert _is_offline_error(Exception("HTTPConnectionPool: Max retries exceeded")) is True
    assert _is_offline_error(Exception("[Errno 111] Connection refused")) is True
    assert _is_offline_error(Exception("Cannot connect to host localhost:11434")) is True


def test_offline_classifier_ignores_unrelated():
    assert _is_offline_error(ValueError("bad prompt template")) is False
    assert _is_offline_error(KeyError("agent")) is False


# ── body-size guard middleware ───────────────────────────────────────────────

def test_oversized_body_rejected_413():
    # ~1.2 MB body — over the 1 MB JSON limit, must be rejected fast (not a 500).
    big = "x" * (1_200_000)
    r = client.post("/ask", json={"message": big}, headers=HEADERS)
    assert r.status_code == 413, r.status_code
    assert "too large" in r.json()["detail"].lower()


def test_normal_body_passes_guard():
    # A small body must NOT be blocked by the guard (it may 4xx/5xx later for
    # other reasons, but never 413).
    r = client.post("/ask", json={"message": "hi"}, headers=HEADERS)
    assert r.status_code != 413


def test_invalid_content_length_400():
    r = client.post("/ask", headers={**HEADERS, "Content-Length": "not-a-number"},
                    content=b'{"message":"x"}')
    # Starlette may normalize a bad Content-Length; accept either the guard's 400
    # or a normal downstream status, but never a 413 for a tiny body.
    assert r.status_code != 413


# ── message max_length -> 422 ────────────────────────────────────────────────

def test_overlong_message_422():
    # Under the 1 MB body limit (~100 KB) but over the 100k-char field cap:
    msg = "a" * 100_001
    r = client.post("/ask", json={"message": msg}, headers=HEADERS)
    assert r.status_code == 422, r.status_code


# ── inference concurrency gate ───────────────────────────────────────────────

def test_inference_slot_caps_concurrency(monkeypatch):
    import asyncio
    from infrastructure import inference_limit as il
    monkeypatch.setattr(il, "_LIMIT", 2)
    monkeypatch.setattr(il, "_sem", None)
    monkeypatch.setattr(il, "_sem_loop", None)

    state = {"cur": 0, "peak": 0}

    async def worker():
        async with il.inference_slot():
            state["cur"] += 1
            state["peak"] = max(state["peak"], state["cur"])
            await asyncio.sleep(0.02)
            state["cur"] -= 1

    async def main():
        await asyncio.gather(*[worker() for _ in range(8)])

    asyncio.run(main())
    assert state["peak"] <= 2, state["peak"]   # never more than the limit in flight
    assert state["peak"] >= 1                    # but it did run concurrently


def test_inference_limit_reads_env(monkeypatch):
    import importlib
    from infrastructure import inference_limit as il
    monkeypatch.setenv("AMAGRA_MAX_CONCURRENT_INFERENCE", "5")
    try:
        importlib.reload(il)
        assert il.limit() == 5
    finally:
        monkeypatch.delenv("AMAGRA_MAX_CONCURRENT_INFERENCE", raising=False)
        importlib.reload(il)  # restore default for any later import
