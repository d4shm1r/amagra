"""
The Amagra runtime loop — the VS Code shell.

This is the entire execution spine: decide which extension to run, fetch it
from the registry, wrap it in an onion of middleware, execute, log, return.
It knows nothing about specific agents, tools, or frameworks — router,
registry, and logger are injected. Read it top to bottom in one sitting.

Signatures (the load-bearing asymmetry):
    Extension  : (Context) -> Result                 # routing-blind
    Middleware : (Context, RoutingMeta, next) -> Result   # sees routing
The terminal adapter strips RoutingMeta before calling the extension, so an
agent can never branch on the brain's decision — only middleware can.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Protocol

from core.contract import Context, Result, RoutingMeta

# ── Contracts ─────────────────────────────────────────────────
Extension  = Callable[[Context], Result]
Handler    = Callable[[Context, RoutingMeta], Result]
Middleware = Callable[[Context, RoutingMeta, Handler], Result]
Router     = Callable[[Context], str]   # Context -> extension_id


class Registry(Protocol):
    def get(self, ext_id: str) -> Extension: ...


class RunLogger(Protocol):
    def append(self, task: str, ext_id: str, result: Result) -> None: ...


# ── Onion composition ─────────────────────────────────────────
def _terminal(ext: Extension) -> Handler:
    """Innermost handler: drop RoutingMeta, call the routing-blind extension."""
    def handler(ctx: Context, meta: RoutingMeta) -> Result:
        return ext(ctx)
    return handler


def compose(ext: Extension, middlewares: List[Middleware]) -> Handler:
    """Wrap an extension in middleware. Index 0 is outermost (runs first)."""
    handler = _terminal(ext)
    for mw in reversed(middlewares):
        # bind mw + next at definition time, else the closure captures the loop var
        def make(mw: Middleware, nxt: Handler) -> Handler:
            return lambda ctx, meta: mw(ctx, meta, nxt)
        handler = make(mw, handler)
    return handler


# ── The loop ──────────────────────────────────────────────────
def run(
    ctx: Context,
    *,
    router: Router,
    registry: Registry,
    middlewares: Optional[List[Middleware]] = None,
    meta: Optional[RoutingMeta] = None,
    logger: Optional[RunLogger] = None,
) -> Result:
    """decide → fetch → wrap → execute → log → return."""
    ext_id  = router(ctx)                      # 1. which extension
    ext     = registry.get(ext_id)             # 2. lazy fetch, no hardcoded import
    meta    = meta or RoutingMeta(agent=ext_id)
    handler = compose(ext, middlewares or [])  # 3. build the onion
    result  = handler(ctx, meta)               # 4. execute
    if logger is not None:                      # 5. transparent state
        logger.append(task=ctx.task, ext_id=ext_id, result=result)
    return result
