"""
Setup/onboarding route tests: GET /setup/status, POST /setup/pull.

No Ollama or network required — `_installed_models` is monkeypatched and the
pull route's httpx.stream is faked with an NDJSON byte stream.

Run: python3 -m pytest tests/test_routes_setup.py -v
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
import routes.setup as setup
from fastapi.testclient import TestClient
from api import app

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="setup-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── /setup/status ─────────────────────────────────────────────────────────────

def test_status_offline_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(setup, "_installed_models", lambda: None)
    body = client.get("/setup/status").json()
    assert body["ollama"] == "offline"
    assert body["ready"] is False
    assert body["missing"] == body["required"]
    assert "ollama serve" in body["hint"]


def test_status_ready_when_all_models_present(monkeypatch):
    monkeypatch.setattr(
        setup, "_installed_models",
        lambda: ["phi4-mini:latest", "nomic-embed-text:latest"],
    )
    body = client.get("/setup/status").json()
    assert body["ollama"] == "online"
    assert body["ready"] is True
    assert body["missing"] == []


def test_status_reports_missing_model(monkeypatch):
    monkeypatch.setattr(setup, "_installed_models", lambda: ["phi4-mini:latest"])
    body = client.get("/setup/status").json()
    assert body["ready"] is False
    assert "nomic-embed-text" in body["missing"]
    assert "phi4-mini:latest" not in body["missing"]


def test_status_base_name_match(monkeypatch):
    # A bare "nomic-embed-text" install satisfies the required name regardless
    # of the :latest tag, and vice versa.
    monkeypatch.setattr(
        setup, "_installed_models",
        lambda: ["phi4-mini:latest", "nomic-embed-text"],
    )
    assert client.get("/setup/status").json()["ready"] is True


def test_status_is_public_no_auth_needed(monkeypatch):
    monkeypatch.setattr(setup, "_installed_models", lambda: None)
    # No X-API-Key header — must still succeed.
    assert client.get("/setup/status").status_code == 200


# ── /setup/pull ───────────────────────────────────────────────────────────────

def test_pull_rejects_non_required_model():
    r = client.post("/setup/pull", json={"model": "llama3:70b"})
    assert r.status_code == 400
    assert "Refusing to pull" in r.json()["detail"]


class _FakeStream:
    """Mimics the httpx.stream(...) context manager + iter_lines()."""
    def __init__(self, lines, status_code=200):
        self._lines = lines
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        yield from self._lines


def test_pull_streams_progress_and_done(monkeypatch):
    lines = [
        '{"status": "pulling manifest"}',
        '{"status": "downloading", "total": 100, "completed": 50}',
        '{"status": "success"}',
    ]
    monkeypatch.setattr(
        "httpx.stream",
        lambda *a, **k: _FakeStream(lines),
    )
    with client.stream("POST", "/setup/pull", json={"model": "phi4-mini:latest"}) as r:
        assert r.status_code == 200
        text = "".join(r.iter_text())
    assert "pulling manifest" in text
    assert '"percent": 50.0' in text
    assert '"type": "done"' in text


def test_pull_surfaces_ollama_error(monkeypatch):
    monkeypatch.setattr(
        "httpx.stream",
        lambda *a, **k: _FakeStream(['{"error": "no space left on device"}']),
    )
    with client.stream("POST", "/setup/pull", json={"model": "nomic-embed-text"}) as r:
        text = "".join(r.iter_text())
    assert '"type": "error"' in text
    assert "no space left" in text
