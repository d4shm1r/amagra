"""
tools/browser.py — interactive, local, headless browsing for a tool-using agent.

Phase C step 2. Where `web_fetch.fetch_page` reads one static URL, this drives a
real (headless Chromium via Playwright) session an agent can navigate, read, and
act on: open → read → click → fill → read. Two deliberate design choices make it
usable by a *small local model* and safe:

  * **Text snapshots, not screenshots.** `browser_read` returns a flattened
    accessibility tree ([role] name, one per line) — the same structure a screen
    reader sees. A 3.8B local model can operate on that; it cannot operate on
    pixels. Selectors accept Playwright's `text=...` engine so the model can click
    by visible label, not brittle CSS.
  * **One shared policy with fetch.** URL navigation reuses `web_fetch._validate`
    (SSRF guard, redirect re-validation, `AMAGRA_FETCH_ALLOWLIST`), and every
    snapshot carries the same `untrusted=True` + `WARNING` injection posture. Page
    content is data, never instructions.

Optional + gated. Playwright is a heavy dependency (a browser download), so it is
imported lazily: this module imports fine without it, the tools only appear in the
catalog when `AMAGRA_BROWSER=1` *and* Playwright is installed, and the core
functions accept an injected page so the logic is testable with no browser at all.

Install (one time, on a machine that will actually browse):
    pip install playwright && playwright install chromium
"""

import os

from tools.web_fetch import _validate, WARNING  # single shared URL policy

MAX_SNAPSHOT_CHARS = 12_000

# Lazily-populated Playwright session: {playwright, browser, page}.
_SESSION: dict = {"playwright": None, "browser": None, "page": None}


class BrowserError(Exception):
    """Base for browser-tool errors."""


class NotAvailable(BrowserError):
    """The browser is disabled (AMAGRA_BROWSER≠1) or Playwright isn't installed."""


def is_enabled() -> bool:
    return os.environ.get("AMAGRA_BROWSER", "0") == "1"


def _playwright_installed() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def available() -> bool:
    """Catalog gate: only offer the tools when switched on AND drivable."""
    return is_enabled() and _playwright_installed()


def _launch():
    """Start a headless Chromium and return its page. Real path; not hit in tests."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    _SESSION.update(playwright=pw, browser=browser, page=page)
    return page


def _get_page():
    """The current page, launching a session on first use. Indirected for tests."""
    if _SESSION["page"] is None:
        return _launch()
    return _SESSION["page"]


def close() -> dict:
    """Tear down the browser session if one is open. Idempotent."""
    browser, pw = _SESSION.get("browser"), _SESSION.get("playwright")
    for obj, meth in ((browser, "close"), (pw, "stop")):
        if obj is not None:
            try:
                getattr(obj, meth)()
            except Exception:
                pass
    _SESSION.update(playwright=None, browser=None, page=None)
    return {"closed": True}


def _guard() -> None:
    if not is_enabled():
        raise NotAvailable("browser is disabled — set AMAGRA_BROWSER=1")


def _flatten_axtree(node: dict, depth: int = 0, out: list | None = None) -> list:
    """Flatten a Playwright accessibility snapshot into '[role] name' lines."""
    out = [] if out is None else out
    if node:
        role = node.get("role", "") or ""
        name = (node.get("name", "") or "").strip()
        if name or role not in ("", "generic", "none"):
            label = f"[{role}] {name}".rstrip()
            out.append(("  " * depth) + label)
        for child in node.get("children", []) or []:
            _flatten_axtree(child, depth + 1, out)
    return out


def _snapshot(page) -> dict:
    """Build the untrusted text snapshot the agent reads after any action."""
    try:
        tree = page.accessibility.snapshot() or {}
    except Exception:
        tree = {}
    lines = _flatten_axtree(tree)
    text = "\n".join(lines)
    truncated = len(text) > MAX_SNAPSHOT_CHARS
    if truncated:
        text = text[:MAX_SNAPSHOT_CHARS]
    return {
        "url": getattr(page, "url", ""),
        "title": page.title() if hasattr(page, "title") else "",
        "untrusted": True,
        "warning": WARNING,
        "chars": len(text),
        "truncated": truncated,
        "snapshot": text,
    }


def browser_open(url: str) -> dict:
    """Navigate to a URL (SSRF/allowlist-guarded) and return a text snapshot."""
    _guard()
    if not url or not url.strip():
        raise BrowserError("url must not be empty")
    _validate(url)                    # scheme + SSRF + allowlist, before navigating
    page = _get_page()
    page.goto(url)
    _validate(getattr(page, "url", url) or url)   # re-validate post-redirect host
    return _snapshot(page)


def browser_read() -> dict:
    """Return the current page's text snapshot without navigating."""
    _guard()
    return _snapshot(_get_page())


def browser_click(target: str) -> dict:
    """Click an element by selector (CSS or Playwright `text=Label`), then read."""
    _guard()
    if not target or not target.strip():
        raise BrowserError("target must not be empty")
    page = _get_page()
    page.click(target)
    return _snapshot(page)


def browser_fill(selector: str, value: str) -> dict:
    """Type `value` into the field matched by `selector`, then read."""
    _guard()
    if not selector or not selector.strip():
        raise BrowserError("selector must not be empty")
    page = _get_page()
    page.fill(selector, value)
    return _snapshot(page)
