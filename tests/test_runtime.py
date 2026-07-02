"""
Runtime-spine tests — guard the load-bearing invariants of core/runtime.py.

This pins them down in pytest so the onion can't silently regress:

  • onion composition order is outer→inner→outer, even with 3+ middlewares
    (the make()/closure fix in compose() — a naive loop captures the last next);
  • the terminal adapter STRIPS RoutingMeta, so an extension is routing-blind;
  • run() supplies a default RoutingMeta(agent=ext_id) when none is passed;
  • run() logs exactly once, after execution, and only when a logger is given.
"""
from core.contract import Context, Result, RoutingMeta
from core.runtime import compose, run


# ── helpers ───────────────────────────────────────────────────
def _ext(tag: str = "ok"):
    def ext(ctx: Context) -> Result:
        return Result(output=f"{tag}::{ctx.task}")
    return ext


def _mw(name: str, trace: list):
    def mw(ctx: Context, meta: RoutingMeta, nxt) -> Result:
        trace.append(f"{name}:before")
        r = nxt(ctx, meta)
        trace.append(f"{name}:after")
        return r
    return mw


class _Reg:
    def __init__(self, ext):
        self._ext = ext

    def get(self, ext_id):
        return self._ext


class _Log:
    def __init__(self):
        self.rows = []

    def append(self, task, ext_id, result):
        self.rows.append((task, ext_id, result.output))


# ── compose(): onion order with the closure-capture guard ──────
def test_compose_runs_three_middlewares_outer_to_inner_to_outer():
    trace: list[str] = []
    handler = compose(
        lambda ctx: (trace.append("ext"), Result(output="x"))[1],
        [_mw("a", trace), _mw("b", trace), _mw("c", trace)],   # index 0 outermost
    )
    handler(Context(task="t"), RoutingMeta(agent="x"))
    # If compose() captured the loop var, all three would chain to the last next
    # and the symmetry would break. This exact sequence proves each mw kept ITS next.
    assert trace == ["a:before", "b:before", "c:before",
                     "ext", "c:after", "b:after", "a:after"]


def test_compose_with_no_middleware_calls_extension_directly():
    handler = compose(_ext("bare"), [])
    out = handler(Context(task="hi"), RoutingMeta(agent="bare"))
    assert out.output == "bare::hi"


# ── the quarantine: terminal strips RoutingMeta ────────────────
def test_extension_never_receives_routing_meta():
    seen = {}

    def spy(ctx: Context) -> Result:
        seen["argc"] = 1
        # Context carries no routing fields at all — the brain's state is absent.
        assert not hasattr(ctx, "confidence")
        assert not hasattr(ctx, "reflect_level")
        return Result(output="ok")

    run(Context(task="t"), router=lambda c: "spy",
        registry=_Reg(spy), meta=RoutingMeta(agent="spy", confidence=0.99))
    assert seen["argc"] == 1   # extension is unary: (Context) -> Result


def test_middleware_sees_routing_meta_extension_does_not():
    """Middleware can branch on confidence; the extension below it cannot."""
    verdicts: list[str] = []

    def gate(ctx, meta, nxt):
        verdicts.append("accept" if meta.confidence >= 0.5 else "flag")
        return nxt(ctx, meta)

    run(Context(task="t"), router=lambda c: "e", registry=_Reg(_ext()),
        middlewares=[gate], meta=RoutingMeta(agent="e", confidence=0.2))
    assert verdicts == ["flag"]


# ── run(): defaults & wiring ───────────────────────────────────
def test_run_returns_extension_output():
    out = run(Context(task="abc"), router=lambda c: "e", registry=_Reg(_ext("r")))
    assert out.output == "r::abc"


def test_run_synthesizes_default_meta_from_routed_id():
    """meta=None → RoutingMeta(agent=ext_id); middleware must still see it."""
    captured = {}

    def grab(ctx, meta, nxt):
        captured["agent"] = meta.agent
        captured["confidence"] = meta.confidence   # dataclass default
        return nxt(ctx, meta)

    run(Context(task="t"), router=lambda c: "python_dev",
        registry=_Reg(_ext()), middlewares=[grab])   # no meta passed
    assert captured["agent"] == "python_dev"
    assert captured["confidence"] == 0.67   # RoutingMeta's default


def test_run_logs_once_after_execution_with_routed_id():
    log = _Log()
    run(Context(task="task-x"), router=lambda c: "echo",
        registry=_Reg(_ext()), logger=log)
    assert log.rows == [("task-x", "echo", "ok::task-x")]


def test_run_does_not_log_when_no_logger_given():
    # No logger is the default; absence must not raise or fabricate state.
    out = run(Context(task="t"), router=lambda c: "e", registry=_Reg(_ext()))
    assert out.output == "ok::t"


def test_router_decides_which_extension_is_fetched():
    """The router's returned id is what registry.get receives — nothing else."""
    asked: list[str] = []

    class Reg:
        def get(self, ext_id):
            asked.append(ext_id)
            return _ext()

    run(Context(task="t"), router=lambda c: "chosen_one", registry=Reg())
    assert asked == ["chosen_one"]
