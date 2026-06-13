"""
Vertical-slice proof for the lean runtime (feature/lean-runtime-core).

Proves, without touching the live coordinator:
  1. The onion composes and fires in the right order (outer→inner→outer).
  2. Middleware sees RoutingMeta; the extension never does.
  3. The registry dispatches by lazy import — including the real
     agents.python_dev_neutral:main — with zero hardcoded agent import here.
  4. Every run lands in an append-only SQLite row you can SELECT.

Run:  python3 scripts/runtime_slice_demo.py
The real-Ollama run is the last block, guarded so it only fires when the
server is reachable.
"""
import os
import sqlite3
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.contract import Context, Result, RoutingMeta, Msg
from core.registry import ExtensionRegistry
from core.run_log import RunLog
from core.runtime import run

trace: list[str] = []


# ── A fake extension (routing-blind) ──────────────────────────
def echo_extension(ctx: Context) -> Result:
    trace.append("ext:run")
    # Proof of quarantine: Context has no routing fields to read.
    assert not hasattr(ctx, "confidence") and not hasattr(ctx, "reflect_level")
    return Result(output=f"echo::{ctx.task}", meta={"len": len(ctx.task)})


# ── Two middlewares (web-router style, see RoutingMeta) ───────
def trace_mw(ctx: Context, meta: RoutingMeta, nxt) -> Result:
    trace.append("trace:before")
    r = nxt(ctx, meta)
    trace.append("trace:after")
    return r


def gate_mw(ctx: Context, meta: RoutingMeta, nxt) -> Result:
    # Proof: middleware CAN read routing the extension cannot.
    trace.append(f"gate:before(conf={meta.confidence})")
    r = nxt(ctx, meta)
    verdict = "accept" if meta.confidence >= 0.5 else "flag"
    trace.append(f"gate:after({verdict})")
    return Result(output=r.output, meta={**dict(r.meta), "gate": verdict})


def main() -> None:
    reg = ExtensionRegistry({
        "echo":       f"{__name__}:echo_extension",
        # the REAL converted agent, resolved by lazy import — no import up top
        "python_dev": "agents.python_dev_neutral:main",
    })
    log = RunLog(path=os.path.join("logs", "runtime_slice.db"))

    ctx = Context(
        task="write a function to count lines of code",
        history=(Msg("user", "hi"), Msg("assistant", "hello"), Msg("user", "go")),
    )
    meta = RoutingMeta(agent="echo", complexity="simple", confidence=0.82)

    # 1+2+4: onion order, routing visibility, logging — with the fake extension
    result = run(
        ctx,
        router=lambda c: "echo",
        registry=reg,
        middlewares=[trace_mw, gate_mw],   # index 0 = outermost
        meta=meta,
        logger=log,
    )

    print("── 1+2. Onion order & routing visibility ──")
    print("   trace:", " → ".join(trace))
    expected = ["trace:before", "gate:before(conf=0.82)", "ext:run",
                "gate:after(accept)", "trace:after"]
    assert trace == expected, f"order wrong: {trace}"
    print("   ✓ outer→inner→outer; middleware read conf=0.82, extension stayed blind")

    print("\n── result ──")
    print("   output:", result.output)
    print("   meta:  ", dict(result.meta), "(gate verdict added by middleware)")
    assert result.output == "echo::write a function to count lines of code"
    assert result.meta["gate"] == "accept" and result.meta["len"] == len(ctx.task)

    # 3. lazy registry dispatch of the REAL agent (resolve, don't fire LLM)
    print("\n── 3. Registry lazy-resolves the real converted agent ──")
    fn = reg.get("python_dev")
    print(f"   ✓ python_dev → {fn.__module__}:{fn.__name__} (imported on demand)")
    assert fn.__module__ == "agents.python_dev_neutral" and fn.__name__ == "main"

    # 4. read the log back with plain SQL
    print("\n── 4. Transparent state (plain SELECT) ──")
    con = sqlite3.connect(os.path.join("logs", "runtime_slice.db"))
    rows = con.execute("SELECT ext_id, output, meta FROM runs ORDER BY id DESC LIMIT 1").fetchall()
    con.close()
    print("   last row:", rows[0])
    assert rows and rows[0][0] == "echo"

    # ── Real Ollama run (guarded) ─────────────────────────────
    print("\n── 5. End-to-end with real Ollama ──")
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        live = True
    except Exception:
        live = False
    if not live:
        print("   ⏭  Ollama not reachable — skipping live LLM call.")
        print("      Re-run this script with the server up to fire python_dev for real.")
    else:
        real = run(
            Context(task="write a python function that adds two ints, with type hints"),
            router=lambda c: "python_dev",
            registry=reg,
            middlewares=[trace_mw],
            logger=log,
        )
        print("   ✓ python_dev_neutral via runtime:\n")
        print("   " + real.output.replace("\n", "\n   ")[:600])

    print("\n✅ SLICE PROVEN: Context → router → registry → onion → Result → SQLite")


if __name__ == "__main__":
    main()
