"""
Tests for tools/tool_loop.py and tools/catalog.py.

The loop's LLM is a scripted fake, and catalog.execute is monkeypatched, so the
control flow is exercised with no model and no real tool side effects.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.catalog as catalog
import tools.tool_loop as tool_loop


def _scripted(responses):
    """An invoke() that returns the next canned response on each call."""
    it = iter(responses)
    seen = []

    def invoke(transcript):
        seen.append(transcript)
        return next(it)

    invoke.seen = seen
    return invoke


# ── extract_call parsing ──────────────────────────────────────────────────────

def test_extract_call_basic():
    text = 'Sure.\n```tool\n{"tool": "read_file", "args": {"path": "a.py"}}\n```'
    assert tool_loop.extract_call(text) == ("read_file", {"path": "a.py"})


def test_extract_call_plain_json_fence():
    assert tool_loop.extract_call('```json\n{"tool":"list_dir"}\n```') == ("list_dir", {})


def test_extract_call_none_when_no_block():
    assert tool_loop.extract_call("just a normal answer") is None


def test_extract_call_none_on_malformed_json():
    assert tool_loop.extract_call("```tool\n{not valid json}\n```") is None


# ── loop control flow ─────────────────────────────────────────────────────────

def test_direct_answer_no_tools(monkeypatch):
    monkeypatch.setattr(catalog, "available_tools", lambda: {})
    out = tool_loop.run_tool_loop(_scripted(["The answer is 4."]), "what is 2+2?")
    assert out["answer"] == "The answer is 4."
    assert out["iterations"] == 0
    assert out["stopped"] == "answer"
    assert out["calls"] == []


def test_one_tool_then_answer(monkeypatch):
    monkeypatch.setattr(catalog, "available_tools", lambda: {
        "read_file": {"args": ["path"], "desc": "read"}})
    monkeypatch.setattr(catalog, "execute", lambda n, a: {"content": "print(1)"})
    invoke = _scripted([
        '```tool\n{"tool": "read_file", "args": {"path": "a.py"}}\n```',
        "The file prints 1.",
    ])
    out = tool_loop.run_tool_loop(invoke, "what does a.py do?", log=False)
    assert out["answer"] == "The file prints 1."
    assert out["stopped"] == "answer"
    assert out["calls"] == [{"tool": "read_file", "args": {"path": "a.py"}, "ok": True}]


def test_tool_error_becomes_observation(monkeypatch):
    monkeypatch.setattr(catalog, "available_tools", lambda: {
        "read_file": {"args": ["path"], "desc": "read"}})

    def _boom(n, a):
        raise KeyError("nope")

    monkeypatch.setattr(catalog, "execute", _boom)
    invoke = _scripted([
        '```tool\n{"tool": "read_file", "args": {"path": "x"}}\n```',
        "Could not read it.",
    ])
    out = tool_loop.run_tool_loop(invoke, "read x", log=False)
    assert out["calls"][0]["ok"] is False
    assert out["answer"] == "Could not read it."


def test_max_iters_forces_final_answer(monkeypatch):
    monkeypatch.setattr(catalog, "available_tools", lambda: {
        "search_files": {"args": ["query"], "desc": "search"}})
    monkeypatch.setattr(catalog, "execute", lambda n, a: {"matches": []})
    # Always emits a tool call; loop must stop after max_iters and ask for an answer.
    always_call = '```tool\n{"tool": "search_files", "args": {"query": "x"}}\n```'
    invoke = _scripted([always_call, always_call, always_call, "Final synthesized answer."])
    out = tool_loop.run_tool_loop(invoke, "find x", max_iters=3, log=False)
    assert out["stopped"] == "max_iters"
    assert out["iterations"] == 3
    assert len(out["calls"]) == 3
    assert out["answer"] == "Final synthesized answer."


def test_empty_prompt_raises():
    with pytest.raises(ValueError):
        tool_loop.run_tool_loop(_scripted(["x"]), "   ")


# ── catalog gating ────────────────────────────────────────────────────────────

def test_gated_tools_hidden_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AMAGRA_SANDBOX", raising=False)
    monkeypatch.setattr(catalog.web, "is_configured", lambda *a, **k: False)
    names = set(catalog.available_tools())
    assert "run_python" not in names      # sandbox opt-in off
    assert "web_search" not in names      # no search backend
    assert {"read_file", "list_dir", "search_files"} <= names  # always-on read tools


def test_gated_tools_appear_when_enabled(monkeypatch):
    monkeypatch.setenv("AMAGRA_SANDBOX", "1")
    monkeypatch.setattr(catalog.web, "is_configured", lambda *a, **k: True)
    names = set(catalog.available_tools())
    assert "run_python" in names
    assert "web_search" in names


def test_execute_unknown_tool_raises():
    with pytest.raises(KeyError):
        catalog.execute("does_not_exist", {})
