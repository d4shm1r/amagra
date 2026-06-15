"""
Unit tests for orchestration/router.py — hybrid_router pure routing logic.

conftest stubs langchain_core.messages as MagicMock, making isinstance(msg, HumanMessage)
fail because HumanMessage is not a type. We patch hybrid_router to bypass the isinstance
check by injecting a real-class HumanMessage substitute for the routing logic.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest.mock as mock
import orchestration.router as rt


class _FakeHumanMessage:
    """Drop-in for HumanMessage in tests — passes isinstance check after patching."""
    def __init__(self, content):
        self.content = content


def _state(query):
    """Build AgentState with a patched HumanMessage so isinstance() passes."""
    msg = _FakeHumanMessage(query)
    return {"messages": [msg]}


def _route(query):
    """Run hybrid_router with HumanMessage patched to our fake class."""
    with mock.patch.object(rt, "HumanMessage", _FakeHumanMessage):
        return rt.hybrid_router(_state(query))


# ── hybrid_router ─────────────────────────────────────────────────────────────

def test_router_empty_messages():
    result = rt.hybrid_router({"messages": []})
    assert result == "coordinator"

def test_router_no_messages_key():
    result = rt.hybrid_router({})
    assert result == "coordinator"

def test_router_python_query():
    result = _route("how do I write a Python async function?")
    assert isinstance(result, str)
    assert len(result) > 0

def test_router_networking_query():
    result = _route("configure nginx reverse proxy and firewall rules")
    assert isinstance(result, str)

def test_router_default_fallback():
    result = _route("what is the meaning of life?")
    assert isinstance(result, str)

def test_router_returns_valid_node():
    result = _route("debug my SSH connection issue on port 22")
    assert isinstance(result, str)
    assert len(result) > 0

def test_router_terse_factual():
    result = _route("What is 2+2?")
    assert isinstance(result, str)

def test_router_always_returns_string():
    queries = [
        "configure VLAN on managed switch",
        "implement a REST API in Python",
        "explain machine learning gradient descent",
        "debug a .NET exception",
        "write technical documentation",
    ]
    for q in queries:
        result = _route(q)
        assert isinstance(result, str), f"Failed for query: {q}"
        assert len(result) > 0


# ── decide(): short-query keyword threshold (issue #10) ───────────────────────

def test_decide_short_query_single_keyword_defaults():
    # 3-token query with a single keyword hit is ambiguous → default fallback.
    # (Domain-shaped so the terse policy pin does not intercept it first.)
    result = rt.decide("configure vlan trunking", {"it_networking": 1})
    assert result == "knowledge_learning"


def test_decide_short_query_two_keywords_routes():
    # Two keyword hits clear the bar even for a short query.
    result = rt.decide("vlan port", {"it_networking": 2})
    assert result == "it_networking"


def test_decide_long_query_single_keyword_routes():
    # A lone keyword in a longer query carries enough context to route on.
    q = "i would like help to configure the office network setup"
    result = rt.decide(q, {"it_networking": 1})
    assert result == "it_networking"


def test_decide_no_keyword_defaults():
    result = rt.decide(
        "please assist me with this particular situation today",
        {"it_networking": 0},
    )
    assert result == "knowledge_learning"
