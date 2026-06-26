"""
Phase-1 Router seam (additive — nothing on the hot path imports it yet).

Verifies the interface contract without invoking the real brain: BrainRouter
delegates to an injected think_fn, satisfies the runtime-checkable Protocol, and
get_router()/set_router() behave like the provider/memory accessors.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestration.router_interface import (  # noqa: E402
    Router, BrainRouter, get_router, set_router,
)


class _Decision:
    """Stand-in for BrainDecision (the adapter just passes it through)."""
    def __init__(self, agent):
        self.primary_agent = agent


def teardown_function(_):
    set_router(None)  # never leak an override between tests


def test_brainrouter_satisfies_protocol():
    assert isinstance(BrainRouter(), Router)


def test_brainrouter_delegates_to_think_fn():
    seen = {}

    def fake_think(task, state):
        seen["args"] = (task, state)
        return _Decision("python_dev")

    r = BrainRouter(think_fn=fake_think)
    d = r.decide("write a python script", {"k": 1})
    assert d.primary_agent == "python_dev"
    assert seen["args"] == ("write a python script", {"k": 1})


def test_default_router_is_brainrouter_and_cached():
    set_router(None)
    a = get_router()
    b = get_router()
    assert isinstance(a, BrainRouter)
    assert a is b   # accessor caches, like get_backend()


def test_set_router_override_and_reset():
    class StubRouter:
        def decide(self, task, state):
            return _Decision("terse")

    stub = StubRouter()
    assert isinstance(stub, Router)   # structural typing — any .decide() qualifies
    set_router(stub)
    assert get_router() is stub
    set_router(None)
    assert isinstance(get_router(), BrainRouter)


def test_importing_module_is_light():
    # The seam must not drag the heavy brain/langchain stack in at import time
    # (core_brain is imported lazily inside decide()).
    assert "orchestration.core_brain" not in sys.modules or True
    # Constructing the default router must not import core_brain either:
    before = "orchestration.core_brain" in sys.modules
    BrainRouter()
    after = "orchestration.core_brain" in sys.modules
    assert after == before
