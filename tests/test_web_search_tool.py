"""
Tests for tools/web.py — the web-search provider abstraction.

Fully offline: requests.get/post are monkeypatched, so no network is touched.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.web as web


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("WEB_SEARCH_PROVIDER", "SEARXNG_URL", "BRAVE_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_default_provider_is_searxng(monkeypatch):
    assert web.active_provider() == "searxng"


def test_searxng_parsing(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    captured = {}

    def _get(url, params=None, timeout=None, **kw):
        captured["url"] = url
        captured["q"] = params.get("q")
        return _FakeResp({"results": [
            {"title": "A", "url": "http://a", "content": "snippet a"},
            {"title": "B", "url": "http://b", "content": "snippet b"},
        ]})

    monkeypatch.setattr(web.requests, "get", _get)
    out = web.search_web("python asyncio", count=5)
    assert out["provider"] == "searxng"
    assert captured["url"].endswith("/search")
    assert captured["q"] == "python asyncio"
    assert out["count"] == 2
    assert out["results"][0] == {"title": "A", "url": "http://a", "snippet": "snippet a"}


def test_searxng_not_configured_raises():
    with pytest.raises(web.NotConfigured):
        web.search_web("x", provider="searxng")


def test_brave_parsing(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "k")
    headers_seen = {}

    def _get(url, params=None, headers=None, timeout=None, **kw):
        headers_seen.update(headers or {})
        return _FakeResp({"web": {"results": [
            {"title": "T", "url": "http://t", "description": "desc"},
        ]}})

    monkeypatch.setattr(web.requests, "get", _get)
    out = web.search_web("q", provider="brave")
    assert out["results"][0]["snippet"] == "desc"
    assert headers_seen.get("X-Subscription-Token") == "k"


def test_tavily_parsing(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tk")

    def _post(url, json=None, timeout=None, **kw):
        assert json["api_key"] == "tk"
        return _FakeResp({"results": [
            {"title": "X", "url": "http://x", "content": "c"},
        ]})

    monkeypatch.setattr(web.requests, "post", _post)
    out = web.search_web("q", provider="tavily")
    assert out["provider"] == "tavily"
    assert out["results"][0]["url"] == "http://x"


def test_count_is_capped(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")
    big = [{"title": str(i), "url": f"http://{i}", "content": ""} for i in range(50)]
    monkeypatch.setattr(web.requests, "get", lambda *a, **k: _FakeResp({"results": big}))
    out = web.search_web("q", count=999)  # clamped to MAX_COUNT
    assert out["count"] == web.MAX_COUNT


def test_empty_query_raises():
    with pytest.raises(web.WebSearchError):
        web.search_web("  ")


def test_unknown_provider_raises():
    with pytest.raises(web.WebSearchError):
        web.search_web("q", provider="doesnotexist")


def test_transport_error_wrapped(monkeypatch):
    monkeypatch.setenv("SEARXNG_URL", "http://localhost:8888")

    def _boom(*a, **k):
        raise web.requests.RequestException("connrefused")

    monkeypatch.setattr(web.requests, "get", _boom)
    with pytest.raises(web.WebSearchError):
        web.search_web("q")
