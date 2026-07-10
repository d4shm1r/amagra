"""
tools/catalog.py — the set of tools an agent can call, behind one execute().

Wraps the existing read-only file tool, the sandbox, and web search into a
uniform name → callable interface for the tool loop (tools/tool_loop.py). Tools
that require configuration (sandbox opt-in, a search backend) only appear in
`available_tools()` when they're actually usable, so the model is never offered
a tool that will 403.
"""

import os

import tools.browser as browser
import tools.sandbox as sbx
import tools.web as web
import tools.web_fetch as web_fetch
import tools.workspace as ws


def _read_file(args: dict):
    return ws.read_file(args["path"])


def _list_dir(args: dict):
    return ws.list_dir(args.get("path", ""))


def _search_files(args: dict):
    return ws.search(args["query"])


def _run_python(args: dict):
    return sbx.run_python(args["code"], timeout=sbx.DEFAULT_TIMEOUT)


def _web_search(args: dict):
    return web.search_web(args["query"], count=int(args.get("count", 5)))


def _fetch_page(args: dict):
    return web_fetch.fetch_page(args["url"])


def _browser_open(args: dict):
    return browser.browser_open(args["url"])


def _browser_read(args: dict):
    return browser.browser_read()


def _browser_click(args: dict):
    return browser.browser_click(args["target"])


def _browser_fill(args: dict):
    return browser.browser_fill(args["selector"], args.get("value", ""))


def _write_file(args: dict):
    return ws.write_file(args["path"], args.get("content", ""))


def _make_dir(args: dict):
    return ws.make_dir(args["path"])


def _move(args: dict):
    return ws.move(args["src"], args["dst"], overwrite=bool(args.get("overwrite", False)))


def _writes_enabled() -> bool:
    """Workspace mutation is opt-in — the same owner-gate posture the HTTP write
    routes use, mirrored here so an agent's tool loop can only mutate the jail
    when the operator has explicitly enabled it."""
    return os.environ.get("AMAGRA_WORKSPACE_WRITE", "0") == "1"


# name -> {fn, args (display), desc, available?}
TOOLS: dict[str, dict] = {
    "read_file": {
        "fn": _read_file, "args": ["path"],
        "desc": "Read a UTF-8 text file from the workspace.",
    },
    "list_dir": {
        "fn": _list_dir, "args": ["path?"],
        "desc": "List a workspace directory (path defaults to the root).",
    },
    "search_files": {
        "fn": _search_files, "args": ["query"],
        "desc": "Substring search over workspace text files.",
    },
    "run_python": {
        "fn": _run_python, "args": ["code"],
        "desc": "Run a short Python snippet in the sandbox and return its output.",
        "available": lambda: os.environ.get("AMAGRA_SANDBOX", "0") == "1",
    },
    "web_search": {
        "fn": _web_search, "args": ["query"],
        "desc": "Search the web for up-to-date information.",
        "available": lambda: web.is_configured(),
    },
    "fetch_page": {
        "fn": _fetch_page, "args": ["url"],
        "desc": "Fetch a web page and return its readable text (untrusted content).",
        "available": web_fetch.available,
    },
    "browser_open": {
        "fn": _browser_open, "args": ["url"],
        "desc": "Open a URL in a headless browser; returns a text snapshot (untrusted).",
        "available": browser.available,
    },
    "browser_read": {
        "fn": _browser_read, "args": [],
        "desc": "Re-read the current browser page as a text snapshot (untrusted).",
        "available": browser.available,
    },
    "browser_click": {
        "fn": _browser_click, "args": ["target"],
        "desc": "Click an element by selector or text= label, then read the page.",
        "available": browser.available,
    },
    "browser_fill": {
        "fn": _browser_fill, "args": ["selector", "value"],
        "desc": "Type a value into a form field by selector, then read the page.",
        "available": browser.available,
    },
    "write_file": {
        "fn": _write_file, "args": ["path", "content"],
        "desc": "Write a UTF-8 text file in the workspace (creates parent dirs, overwrites).",
        "available": _writes_enabled,
    },
    "make_dir": {
        "fn": _make_dir, "args": ["path"],
        "desc": "Create a directory (and parents) in the workspace.",
        "available": _writes_enabled,
    },
    "move": {
        "fn": _move, "args": ["src", "dst"],
        "desc": "Move or rename a file/directory within the workspace.",
        "available": _writes_enabled,
    },
}


def available_tools() -> dict[str, dict]:
    """Only the tools usable right now (config/opt-in gates applied)."""
    return {n: t for n, t in TOOLS.items()
            if "available" not in t or t["available"]()}


def execute(name: str, args: dict | None):
    """Run a tool by name. Raises KeyError (unknown), PermissionError (gated off),
    or the tool's own typed error (PathEscape, NotConfigured, …)."""
    tool = TOOLS.get(name)
    if tool is None:
        raise KeyError(f"unknown tool: {name!r}")
    if "available" in tool and not tool["available"]():
        raise PermissionError(f"tool not available: {name!r}")
    return tool["fn"](args or {})
