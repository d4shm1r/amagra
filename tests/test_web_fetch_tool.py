"""
Tests for tools/web_fetch.py — the guarded page-fetch tool.

Fully offline: DNS (_resolve_ips) and HTTP (_http_get) are monkeypatched, so no
network or name resolution is touched. Covers extraction, the SSRF guard, the
allowlist, redirect re-validation, the untrusted-content marker, and the catalog
gate.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.web_fetch as wf
import tools.catalog as catalog


class _FakeResp:
    def __init__(self, text="", url="http://example.com", status=200):
        self.text = text
        self.url = url
        self.status_code = status

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("AMAGRA_WEB_FETCH", "AMAGRA_FETCH_ALLOWLIST"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def _public_dns(monkeypatch):
    """Resolve every host to a public IP so the SSRF guard passes by default."""
    monkeypatch.setattr(wf, "_resolve_ips", lambda host: ["93.184.216.34"])


def _enable(monkeypatch):
    monkeypatch.setenv("AMAGRA_WEB_FETCH", "1")


HTML = """
<html><head><title>  Hello Title </title></head>
<body>
  <nav>menu one two</nav>
  <h1>Main Heading</h1>
  <p>First paragraph of real content.</p>
  <script>tracking();</script>
  <footer>copyright junk</footer>
</body></html>
"""


def test_disabled_by_default(monkeypatch, _public_dns):
    with pytest.raises(wf.NotConfigured):
        wf.fetch_page("http://example.com")


def test_extracts_readable_text_and_marks_untrusted(monkeypatch, _public_dns):
    _enable(monkeypatch)
    monkeypatch.setattr(wf, "_http_get", lambda url, timeout: _FakeResp(HTML, url))

    out = wf.fetch_page("http://example.com/page")

    assert out["title"] == "Hello Title"
    assert "Main Heading" in out["text"]
    assert "First paragraph of real content." in out["text"]
    # Chrome / scripts / footer are stripped
    assert "tracking()" not in out["text"]
    assert "copyright junk" not in out["text"]
    assert "menu one two" not in out["text"]
    # Quarantine marker is always present
    assert out["untrusted"] is True
    assert "UNTRUSTED" in out["warning"]


def test_ssrf_blocks_private_address(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(wf, "_resolve_ips", lambda host: ["10.0.0.5"])
    with pytest.raises(wf.BlockedURL):
        wf.fetch_page("http://internal.corp/secret")


def test_ssrf_blocks_loopback_literal(monkeypatch):
    _enable(monkeypatch)
    with pytest.raises(wf.BlockedURL):
        wf.fetch_page("http://127.0.0.1:8000/admin")


def test_rejects_non_http_scheme(monkeypatch):
    _enable(monkeypatch)
    with pytest.raises(wf.BlockedURL):
        wf.fetch_page("file:///etc/passwd")


def test_allowlist_enforced(monkeypatch, _public_dns):
    _enable(monkeypatch)
    monkeypatch.setenv("AMAGRA_FETCH_ALLOWLIST", "docs.python.org")
    monkeypatch.setattr(wf, "_http_get", lambda url, timeout: _FakeResp(HTML, url))

    # subdomain of an allowed domain passes
    assert wf.fetch_page("https://docs.python.org/3/library").get("title")
    # an off-list domain is refused
    with pytest.raises(wf.BlockedURL):
        wf.fetch_page("https://evil.example.com/x")


def test_redirect_to_private_is_revalidated(monkeypatch):
    _enable(monkeypatch)
    # First validation passes (public), but the response redirected to loopback.
    monkeypatch.setattr(wf, "_resolve_ips", lambda host: ["93.184.216.34"]
                        if host == "example.com" else ["127.0.0.1"])
    monkeypatch.setattr(wf, "_http_get",
                        lambda url, timeout: _FakeResp(HTML, "http://localhost/x"))
    with pytest.raises(wf.BlockedURL):
        wf.fetch_page("http://example.com/redir")


def test_transport_error_wrapped(monkeypatch, _public_dns):
    _enable(monkeypatch)
    import requests

    def boom(url, timeout):
        raise requests.RequestException("connection reset")

    monkeypatch.setattr(wf, "_http_get", boom)
    with pytest.raises(wf.FetchError):
        wf.fetch_page("http://example.com")


def test_catalog_gate(monkeypatch, _public_dns):
    monkeypatch.delenv("AMAGRA_WEB_FETCH", raising=False)
    assert "fetch_page" not in catalog.available_tools()
    monkeypatch.setenv("AMAGRA_WEB_FETCH", "1")
    assert "fetch_page" in catalog.available_tools()
    monkeypatch.setattr(wf, "_http_get", lambda url, timeout: _FakeResp(HTML, url))
    out = catalog.execute("fetch_page", {"url": "http://example.com"})
    assert out["untrusted"] is True
