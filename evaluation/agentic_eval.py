"""
agentic_eval.py — task-completion benchmark for the agentic execution substrate.

The scorecard rates Planning (5) and Autonomy (4) as *(subjective)* because no
eval exercises multi-step, tool-using task completion end-to-end. This harness
supplies the missing measurement, and it deliberately separates two questions
the scorecard has always conflated:

  substrate ceiling  — given a *perfect* agent (one that emits exactly the right
                       tool calls), does the real plumbing (tools/catalog.py →
                       tools/tool_loop.py → tools/workspace.py) actually complete
                       the task and leave the correct end state on disk?
  model capability   — can the local model (phi4-mini) itself drive that loop?
                       Slow, non-deterministic, needs Ollama. Opt-in via --live.

The substrate ceiling is the honest floor for Autonomy/Planning: if a perfect
agent scores 0, the model can never do better, and no amount of prompt work
matters until the substrate is fixed. It runs offline in well under a second and
is fully deterministic, matching the rest of evaluation/.

Every task runs in an isolated temp workspace (AMAGRA_WORKSPACE is repointed for
the duration), so the eval never reads or writes the real workspace tree.

Run:
    PYTHONPATH=. python3 evaluation/agentic_eval.py
    PYTHONPATH=. python3 evaluation/agentic_eval.py --verbose
    AMAGRA_WORKSPACE_WRITE=1 PYTHONPATH=. python3 evaluation/agentic_eval.py
"""

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.tool_loop as tool_loop
import tools.workspace as ws


# ── Task model ────────────────────────────────────────────────

@dataclass
class Task:
    tid:     str
    prompt:  str                       # what the agent is told to do
    oracle:  list[dict]                # the tool calls a perfect agent would emit
    check:   Callable[[Path], bool]    # end-state assertion over the workspace root
    seed:    Callable[[Path], None] = None   # optional: pre-populate the workspace
    needs:   list[str] = field(default_factory=list)  # tools the task requires


# ── Scripted "perfect agent" ──────────────────────────────────

def _oracle_invoke(oracle: list[dict]):
    """Return an invoke() that replays the oracle's tool calls, one per turn,
    then answers plainly. This exercises the real tool loop + catalog + workspace
    without any model — so a failure is a substrate failure, never a model one."""
    calls = list(oracle)

    def invoke(_transcript):
        if calls:
            call = calls.pop(0)
            return "```tool\n" + json.dumps(call) + "\n```"
        return "Done."

    return invoke


# The preamble the model sees in --live mode. It leads the tool-protocol system
# message (tool_loop injects the tool list after it), so the model knows it must
# actually mutate the workspace, not merely describe what it would do.
_LIVE_PREAMBLE = (
    "You are an autonomous engineering agent operating inside a sandboxed project "
    "workspace. Complete the user's task by CALLING TOOLS to actually create, read, "
    "and modify files — do not just describe what you would do. Take one tool action "
    "per turn. When the task is fully done on disk, reply with a short plain-text "
    "confirmation and no tool block."
)


def _live_invoke():
    """The real production invoke: adapt a transcript to models.llm via the same
    adapter the agent runtime uses, so --live measures the actual agent path.
    Probes the backend eagerly so a missing model/library fails here with a clear
    message, not mid-loop."""
    import langchain_core.messages  # noqa: F401 — the adapter needs this
    from models.llm import llm      # forces the provider to build
    _ = llm
    from tools.agent_runtime import _llm_invoke
    return _llm_invoke


# ── Task suite (deterministic, workspace end-state checked) ────

def _seed_config(root: Path):
    (root / "config.txt").write_text("timeout=30\nretries=3\n", encoding="utf-8")


def _seed_notes(root: Path):
    (root / "notes.md").write_text(
        "# Notes\nTODO: wire the executor\nTODO: measure autonomy\n", encoding="utf-8"
    )


TASKS: list[Task] = [
    Task(
        tid="write_single_file",
        prompt="Create hello.py containing a greet() function.",
        oracle=[{"tool": "write_file",
                 "args": {"path": "hello.py", "content": "def greet():\n    return 'hi'\n"}}],
        check=lambda r: (r / "hello.py").exists()
                        and "def greet" in (r / "hello.py").read_text(),
        needs=["write_file"],
    ),
    Task(
        tid="make_package",
        prompt="Create a pkg/ package with __init__.py and core.py.",
        oracle=[
            {"tool": "make_dir", "args": {"path": "pkg"}},
            {"tool": "write_file", "args": {"path": "pkg/__init__.py", "content": ""}},
            {"tool": "write_file",
             "args": {"path": "pkg/core.py", "content": "VALUE = 42\n"}},
        ],
        check=lambda r: (r / "pkg/__init__.py").exists()
                        and (r / "pkg/core.py").exists()
                        and "VALUE = 42" in (r / "pkg/core.py").read_text(),
        needs=["make_dir", "write_file"],
    ),
    Task(
        tid="read_modify_write",
        prompt="Read config.txt and change the timeout to 60.",
        seed=_seed_config,
        oracle=[
            {"tool": "read_file", "args": {"path": "config.txt"}},
            {"tool": "write_file",
             "args": {"path": "config.txt", "content": "timeout=60\nretries=3\n"}},
        ],
        check=lambda r: "timeout=60" in (r / "config.txt").read_text(),
        needs=["read_file", "write_file"],
    ),
    Task(
        tid="search_then_report",
        prompt="Find every TODO in the workspace and write them to todos.txt.",
        seed=_seed_notes,
        oracle=[
            {"tool": "search_files", "args": {"query": "TODO"}},
            {"tool": "write_file",
             "args": {"path": "todos.txt",
                      "content": "wire the executor\nmeasure autonomy\n"}},
        ],
        check=lambda r: (r / "todos.txt").exists()
                        and "executor" in (r / "todos.txt").read_text(),
        needs=["search_files", "write_file"],
    ),
    Task(
        tid="rename_file",
        prompt="Rename notes.md to TODO.md.",
        seed=_seed_notes,
        oracle=[{"tool": "move", "args": {"src": "notes.md", "dst": "TODO.md"}}],
        check=lambda r: (r / "TODO.md").exists() and not (r / "notes.md").exists(),
        needs=["move"],
    ),
    Task(
        tid="read_only_baseline",
        prompt="Read config.txt and report the retries value.",
        seed=_seed_config,
        oracle=[{"tool": "read_file", "args": {"path": "config.txt"}}],
        # A read-only task the current substrate already supports — proves the
        # harness itself works and isolates the write-path gap from a harness bug.
        check=lambda r: (r / "config.txt").exists(),
        needs=["read_file"],
    ),
]


# ── Runner ────────────────────────────────────────────────────

def _run_task(task: Task, verbose: bool, *, invoke=None, live: bool = False,
              max_iters: int = None) -> dict:
    """Run one task in a fresh temp workspace. Returns a result record.

    invoke   — the model driver. Defaults to the perfect-agent oracle; pass a real
               (or test-double) invoke to measure model-driven completion.
    live     — auto-enable workspace writes for the isolated temp workspace, so a
               model-driven run isn't blocked by the opt-in gate it can't set itself.
    """
    import tools.catalog as catalog

    with tempfile.TemporaryDirectory(prefix="agentic-eval-") as tmp:
        root = Path(tmp).resolve()
        saved = {k: os.environ.get(k) for k in ("AMAGRA_WORKSPACE", "AMAGRA_WORKSPACE_WRITE")}
        os.environ["AMAGRA_WORKSPACE"] = str(root)
        if live:
            os.environ["AMAGRA_WORKSPACE_WRITE"] = "1"
        try:
            if task.seed:
                task.seed(root)

            available = set(catalog.available_tools())
            missing = [t for t in task.needs if t not in available]

            driver = invoke if invoke is not None else _oracle_invoke(task.oracle)
            iters = max_iters or (len(task.oracle) + 1)
            preamble = _LIVE_PREAMBLE if live else None
            result = tool_loop.run_tool_loop(
                driver, task.prompt, max_iters=iters, log=False,
                system_preamble=preamble,
            )
            calls = result.get("calls", [])
            failed_calls = [c for c in calls if not c.get("ok")]

            try:
                passed = bool(task.check(root))
            except Exception:
                passed = False

            reason = ""
            if not passed:
                if missing:
                    reason = f"tools not available: {', '.join(missing)}"
                elif not calls:
                    reason = "no tool calls emitted"
                elif failed_calls:
                    reason = f"tool call failed: {failed_calls[0]['tool']}"
                else:
                    reason = "end-state assertion failed"
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    rec = {"task": task.tid, "passed": passed, "reason": reason, "missing": missing,
           "calls": len(calls), "ok_calls": len(calls) - len(failed_calls),
           "stopped": result.get("stopped", "")}
    if verbose:
        status = "PASS" if passed else "FAIL"
        detail = "" if passed else f"  — {reason}"
        extra = f"  ({rec['ok_calls']}/{rec['calls']} calls ok)" if calls else ""
        print(f"  [{status}] {task.tid}{detail}{extra}")
    return rec


def run_suite(*, live: bool = False, invoke=None, verbose: bool = False,
              max_iters: int = None) -> list[dict]:
    """Run every task and return the raw records. `invoke` overrides the driver
    (oracle by default, or a test double), so the measurement logic is exercisable
    without a real model."""
    return [_run_task(t, verbose, invoke=invoke, live=live, max_iters=max_iters)
            for t in TASKS]


def _report(records: list[dict], label: str) -> None:
    n = len(records)
    n_pass = sum(1 for r in records if r["passed"])
    total_calls = sum(r["calls"] for r in records)
    ok_calls = sum(r["ok_calls"] for r in records)
    print("-" * 64)
    print(f"  {label}: {n_pass}/{n} = {n_pass / n:.0%}")
    if total_calls:
        print(f"  tool-call validity: {ok_calls}/{total_calls} = {ok_calls / total_calls:.0%} "
              f"(parsed + executed without error)")
    if n_pass < n:
        blocked = {}
        for r in records:
            if not r["passed"]:
                blocked[r["reason"]] = blocked.get(r["reason"], 0) + 1
        print("  blocked by:")
        for reason, count in sorted(blocked.items(), key=lambda kv: -kv[1]):
            print(f"    {count}× {reason}")
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(description="Agentic task-completion benchmark")
    ap.add_argument("--verbose", action="store_true", help="per-task pass/fail lines")
    ap.add_argument("--json", action="store_true", help="emit the raw result records")
    ap.add_argument("--live", action="store_true",
                    help="drive with the real local model (models.llm) instead of "
                         "the perfect-agent oracle — needs a working backend (Ollama)")
    ap.add_argument("--max-iters", type=int, default=None,
                    help="tool-loop rounds per task (default: oracle length; 8 for --live)")
    args = ap.parse_args()

    if args.live:
        try:
            driver = _live_invoke()
        except Exception as e:
            print(f"--live requires a working model backend, but it failed to build: {e}")
            print("Set up Ollama (or LLM_PROVIDER=openai/anthropic) and retry.")
            return 2
        print("=" * 64)
        print("  agentic_eval.py — MODEL-DRIVEN completion (--live)")
        print(f"  backend: {os.environ.get('LLM_PROVIDER', os.environ.get('BRAIN_PROVIDER', 'ollama'))}"
              f" · model: {os.environ.get('OLLAMA_MODEL', 'phi4-mini:latest')}")
        print("  workspace writes: auto-ENABLED per isolated temp workspace")
        print("=" * 64)
        records = run_suite(live=True, invoke=driver, verbose=args.verbose,
                            max_iters=args.max_iters or 8)
        _report(records, "model-driven completion")
        if args.json:
            print(json.dumps(records, indent=2))
        return 0

    write_on = os.environ.get("AMAGRA_WORKSPACE_WRITE", "0") == "1"
    print("=" * 64)
    print("  agentic_eval.py — substrate ceiling (perfect-agent tool calls)")
    print(f"  workspace writes: {'ENABLED' if write_on else 'DISABLED'} "
          f"(AMAGRA_WORKSPACE_WRITE={'1' if write_on else '0'})")
    print("=" * 64)

    records = run_suite(verbose=args.verbose, max_iters=args.max_iters)
    _report(records, "substrate completion")
    if args.json:
        print(json.dumps(records, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
