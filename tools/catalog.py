"""
tools/catalog.py — the set of tools an agent can call, behind one execute().

Wraps the existing read-only file tool, the sandbox, and web search into a
uniform name → callable interface for the tool loop (tools/tool_loop.py). Tools
that require configuration (sandbox opt-in, a search backend) only appear in
`available_tools()` when they're actually usable, so the model is never offered
a tool that will 403.
"""

import os

import tools.sandbox as sbx
import tools.web as web
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
