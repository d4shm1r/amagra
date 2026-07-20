"""
Tests for tools/agent_runtime.py — the gated in-agent tool loop (#8, #5).

The LLM invoke is scripted (no model) and AMAGRA_AGENT_TOOLS is toggled via env,
so we exercise the gate, the fallback, and the persona-preamble wiring without
any real model or tool side effects.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.agent_runtime as ar
import tools.tool_loop as tool_loop


def _scripted(*responses):
    it = iter(responses)
    seen = []

    def invoke(transcript):
        seen.append(transcript)
        return next(it)

    invoke.seen = seen
    return invoke


# ── gate ──────────────────────────────────────────────────────────────────────

def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AMAGRA_AGENT_TOOLS", raising=False)
    assert ar.agent_tools_enabled() is False
    assert ar.run_with_tools("persona", "do the thing") is None


def test_enabled_runs_loop_and_returns_answer(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    inv = _scripted("The answer is 42.")  # no tool block → answers immediately
    out = ar.run_with_tools("You are a helper.", "what is the answer?", invoke=inv)
    assert out == "The answer is 42."


def test_persona_preamble_leads_system_message(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    inv = _scripted("done")
    ar.run_with_tools("PERSONA-MARKER", "task", invoke=inv)
    system_msg = inv.seen[0][0]            # (role, content) of first turn
    assert system_msg[0] == "system"
    assert system_msg[1].startswith("PERSONA-MARKER")
    assert "tool-using assistant" in system_msg[1]   # tool protocol still appended


def test_empty_task_returns_none(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    assert ar.run_with_tools("persona", "   ", invoke=_scripted("x")) is None


def test_no_tools_available_returns_none(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    monkeypatch.setattr(ar.catalog, "available_tools", lambda: {})
    assert ar.run_with_tools("persona", "task", invoke=_scripted("x")) is None


def test_loop_failure_falls_back_to_none(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")

    def _boom(*a, **k):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(tool_loop, "run_tool_loop", _boom)
    assert ar.run_with_tools("persona", "task", invoke=_scripted("x")) is None


def test_blank_answer_returns_none(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    monkeypatch.setattr(tool_loop, "run_tool_loop",
                        lambda *a, **k: {"answer": "   "})
    assert ar.run_with_tools("persona", "task", invoke=_scripted("x")) is None


# ── compute steering: exact-computation queries → run_python (#186) ───────────

_COMPUTE_TASK = "Compute the first 12 terms of the sequence a1=1, a2=2. Do not guess."


def test_compute_directive_injected_when_run_python_available(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    # Pretend the sandbox is on: run_python is offered.
    monkeypatch.setattr(ar.catalog, "available_tools",
                        lambda: {"run_python": {"args": ["code"], "desc": "run"}, "read_file": {"args": ["path"], "desc": "read"}})
    inv = _scripted("done")                       # answers without a tool call
    ar.run_with_tools("PERSONA", _COMPUTE_TASK, invoke=inv)
    system_msg = inv.seen[0][0][1]
    assert system_msg.startswith("PERSONA")       # persona still leads
    assert "run_python" in system_msg             # directive steers to the sandbox
    assert "EXACT computed result" in system_msg


def test_compute_directive_absent_without_run_python(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    # Sandbox off: only read tools. Directive would be a dead instruction → omit.
    monkeypatch.setattr(ar.catalog, "available_tools", lambda: {"read_file": {"args": ["path"], "desc": "read"}})
    inv = _scripted("done")
    ar.run_with_tools("PERSONA", _COMPUTE_TASK, invoke=inv)
    assert "EXACT computed result" not in inv.seen[0][0][1]


def test_compute_directive_absent_for_non_compute_task(monkeypatch):
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    monkeypatch.setattr(ar.catalog, "available_tools",
                        lambda: {"run_python": {"args": ["code"], "desc": "run"}, "read_file": {"args": ["path"], "desc": "read"}})
    inv = _scripted("done")
    ar.run_with_tools("PERSONA", "Explain how DNS resolution works", invoke=inv)
    assert "EXACT computed result" not in inv.seen[0][0][1]


# ── respond_with_optional_tools: drop-in for llm.invoke ───────────────────────

def test_respond_falls_back_to_plain_invoke_when_disabled(monkeypatch):
    monkeypatch.delenv("AMAGRA_AGENT_TOOLS", raising=False)
    called = {}

    class _FakeLLM:
        def invoke(self, messages):
            called["messages"] = messages
            return "PLAIN"

    import models.llm as llm_mod
    monkeypatch.setattr(llm_mod, "llm", _FakeLLM())
    resp = ar.respond_with_optional_tools(["m1", "m2"], "persona", "task")
    assert resp == "PLAIN"
    assert called["messages"] == ["m1", "m2"]


def test_respond_uses_tool_answer_and_skips_plain_invoke(monkeypatch):
    # When the tool loop yields an answer, the plain llm.invoke path is skipped.
    # (AIMessage itself is a conftest MagicMock, so we assert behaviour, not type.)
    monkeypatch.setenv("AMAGRA_AGENT_TOOLS", "1")
    monkeypatch.setattr(ar, "run_with_tools", lambda *a, **k: "TOOL-ANSWER")
    called = {"plain": False}

    class _FakeLLM:
        def invoke(self, messages):
            called["plain"] = True
            return "PLAIN"

    import models.llm as llm_mod
    monkeypatch.setattr(llm_mod, "llm", _FakeLLM())
    ar.respond_with_optional_tools(["msgs"], "persona", "task")
    assert called["plain"] is False


# ── system_preamble plumbing in run_tool_loop ─────────────────────────────────

def test_run_tool_loop_preamble_prepended():
    inv = _scripted("answer")
    tool_loop.run_tool_loop(inv, "q", system_preamble="LEAD")
    assert inv.seen[0][0][1].startswith("LEAD\n\n")


def test_run_tool_loop_no_preamble_is_bare():
    inv = _scripted("answer")
    tool_loop.run_tool_loop(inv, "q")
    assert inv.seen[0][0][1].startswith("You are a tool-using assistant")
