"""
Tests for tools/browser.py — the headless interactive browser tools.

Fully offline: Playwright is never imported. A fake page is injected via
_get_page, and DNS is stubbed in web_fetch (whose _validate the browser reuses),
so the navigation guard, accessibility-tree flattening, actions, untrusted
marker, and catalog gate are all exercised with no browser at all.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.browser as br
import tools.web_fetch as wf
import tools.catalog as catalog


_AXTREE = {
    "role": "WebArea", "name": "Example Domain",
    "children": [
        {"role": "heading", "name": "Main Heading"},
        {"role": "textbox", "name": "Search"},
        {"role": "button", "name": "Go"},
        {"role": "generic", "name": "", "children": [
            {"role": "link", "name": "More info"},
        ]},
    ],
}


class _FakeAx:
    def __init__(self, tree):
        self._tree = tree

    def snapshot(self):
        return self._tree


class _FakePage:
    def __init__(self, url="http://example.com", tree=None, title="Example"):
        self.url = url
        self._title = title
        self.accessibility = _FakeAx(tree or _AXTREE)
        self.actions = []

    def goto(self, url):
        self.actions.append(("goto", url))

    def title(self):
        return self._title

    def click(self, target):
        self.actions.append(("click", target))

    def fill(self, selector, value):
        self.actions.append(("fill", selector, value))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for k in ("AMAGRA_BROWSER", "AMAGRA_FETCH_ALLOWLIST"):
        monkeypatch.delenv(k, raising=False)
    br._SESSION.update(playwright=None, browser=None, page=None)


@pytest.fixture
def _public_dns(monkeypatch):
    monkeypatch.setattr(wf, "_resolve_ips", lambda host: ["93.184.216.34"])


def _inject(monkeypatch, page):
    monkeypatch.setattr(br, "_get_page", lambda: page)


def test_disabled_by_default(monkeypatch, _public_dns):
    with pytest.raises(br.NotAvailable):
        br.browser_open("http://example.com")


def test_open_navigates_and_snapshots(monkeypatch, _public_dns):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    page = _FakePage()
    _inject(monkeypatch, page)

    out = br.browser_open("http://example.com/page")

    assert ("goto", "http://example.com/page") in page.actions
    assert out["untrusted"] is True and "UNTRUSTED" in out["warning"]
    # Accessibility tree flattened into readable [role] name lines
    assert "[heading] Main Heading" in out["snapshot"]
    assert "[button] Go" in out["snapshot"]
    assert "[link] More info" in out["snapshot"]


def test_open_blocks_private_target(monkeypatch):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    monkeypatch.setattr(wf, "_resolve_ips", lambda host: ["10.1.2.3"])
    _inject(monkeypatch, _FakePage())
    with pytest.raises(wf.BlockedURL):
        br.browser_open("http://internal.corp/")


def test_open_revalidates_after_redirect(monkeypatch):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    monkeypatch.setattr(wf, "_resolve_ips",
                        lambda host: ["93.184.216.34"] if host == "example.com"
                        else ["127.0.0.1"])
    # The page ends up on a loopback host after navigation.
    _inject(monkeypatch, _FakePage(url="http://localhost/admin"))
    with pytest.raises(wf.BlockedURL):
        br.browser_open("http://example.com/redir")


def test_click_and_fill_then_read(monkeypatch, _public_dns):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    page = _FakePage()
    _inject(monkeypatch, page)

    br.browser_fill("input[name=q]", "hello")
    out = br.browser_click("text=Go")

    assert ("fill", "input[name=q]", "hello") in page.actions
    assert ("click", "text=Go") in page.actions
    assert out["untrusted"] is True


def test_read_without_navigation(monkeypatch, _public_dns):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    _inject(monkeypatch, _FakePage())
    out = br.browser_read()
    assert "[heading] Main Heading" in out["snapshot"]


def test_available_requires_enabled_and_playwright(monkeypatch):
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    monkeypatch.setattr(br, "_playwright_installed", lambda: False)
    assert br.available() is False
    monkeypatch.setattr(br, "_playwright_installed", lambda: True)
    assert br.available() is True


def test_catalog_gate(monkeypatch, _public_dns):
    # Enabled but Playwright present → tools offered; execute() drives injected page.
    monkeypatch.setenv("AMAGRA_BROWSER", "1")
    monkeypatch.setattr(br, "_playwright_installed", lambda: True)
    _inject(monkeypatch, _FakePage())
    tools = catalog.available_tools()
    assert {"browser_open", "browser_read", "browser_click", "browser_fill"} <= set(tools)
    out = catalog.execute("browser_open", {"url": "http://example.com"})
    assert out["untrusted"] is True


def test_close_is_idempotent():
    assert br.close()["closed"] is True
    assert br.close()["closed"] is True
