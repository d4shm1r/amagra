"""orchestration/router_interface.py — the Router seam (Phase 1, additive).

The production routing authority is ``core_brain.think() -> BrainDecision``
(see ``orchestration/coordinator.py``: "Core brain is the sole routing
authority", issue #20 — ``orchestration/router.py``'s ``decide``/``score`` are
legacy/diagnostic, off the hot path). This module formalizes that authority
behind a swappable interface — mirroring ``MemoryBackend`` and ``ModelProvider``
— *without touching the hot path yet*.

`BrainRouter` is a thin, behavior-preserving adapter over ``core_brain.think``.
`get_router()` returns the default; `set_router()` swaps it (tests / future
extension loading).

STATUS: wired. ``orchestration/coordinator.py`` routes through ``get_router()``,
so this module is on the live path — it is loaded at boot and every request goes
through it. (It once said "nothing imports this module yet"; that stopped being
true when the coordinator was moved onto the seam, and the stale note survived
long enough to convince a reader the whole routing layer was dead code. It is
not: ``learned_router`` and ``semantic_fallback`` are both imported lazily inside
``core_brain.think`` and run per request. Only ``router.py`` is off the hot path,
and it says so itself.)
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — no runtime import of the heavy brain module
    from orchestration.core_brain import BrainDecision


@runtime_checkable
class Router(Protocol):
    """Decides WHO acts. Returns the structured ``BrainDecision`` the coordinator
    already consumes, so an implementation is drop-in for the current path."""

    def decide(self, task: str, state) -> "BrainDecision": ...


class BrainRouter:
    """Default router — delegates to ``core_brain.think`` (the current authority).

    ``think_fn`` is injectable so the adapter is unit-testable without invoking
    the real brain (which may call the LLM for ambiguous queries). Left ``None``,
    ``core_brain.think`` is imported lazily on first ``decide`` — so importing
    this module stays light.
    """

    name = "brain"

    def __init__(self, think_fn: Optional[Callable] = None):
        self._think = think_fn

    def decide(self, task: str, state) -> "BrainDecision":
        think = self._think
        if think is None:
            from orchestration.core_brain import think as _think
            think = _think
        return think(task, state)


_router: Optional[Router] = None


def get_router() -> Router:
    """The active router (defaults to ``BrainRouter``). Cached after first call."""
    global _router
    if _router is None:
        _router = BrainRouter()
    return _router


def set_router(router: Optional[Router]) -> None:
    """Swap the active router; pass ``None`` to reset to the default.

    The hook a future contribution model / ``AMAGRA_ROUTER`` selector uses to
    install an alternative (LLMRouter, GraphRouter, EnterpriseRouter…)."""
    global _router
    _router = router
