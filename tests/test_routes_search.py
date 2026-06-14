"""
Route tests for /search/* — graceful when no backend is configured, results when
the provider is mocked.
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
import tools.web as web
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="search-test@test.com", tier="developer")}


def teardown_module(module):
    for k in ("WEB_SEARCH_PROVIDER", "SEARXNG_URL", "BRAVE_API_KEY", "TAVILY_API_KEY"):
        os.environ.pop(k, None)


def test_status_default_unconfigured():
    for k in ("WEB_SEARCH_PROVIDER", "SEARXNG_URL", "BRAVE_API_KEY", "TAVILY_API_KEY"):
        os.environ.pop(k, None)
    r = client.get("/search/status", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "searxng"
    assert body["configured"] is False


def test_web_unconfigured_returns_503():
    for k in ("SEARXNG_URL", "BRAVE_API_KEY", "TAVILY_API_KEY"):
        os.environ.pop(k, None)
    r = client.get("/search/web", params={"q": "python"}, headers=HEADERS)
    assert r.status_code == 503


def test_web_returns_results_when_configured(monkeypatch):
    os.environ["SEARXNG_URL"] = "http://localhost:8888"

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"results": [{"title": "Doc", "url": "http://d", "content": "c"}]}

    monkeypatch.setattr(web.requests, "get", lambda *a, **k: _Resp())
    r = client.get("/search/web", params={"q": "python"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "searxng"
    assert body["results"][0]["title"] == "Doc"
    os.environ.pop("SEARXNG_URL", None)
