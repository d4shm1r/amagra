"""
Thread-safety audit + regression guard for SQLite access (#195).

Background: several modules open connections with `check_same_thread=False`
(run_tracer, task_graph, decision/log, decision/weights, decision/model_choices,
context_snapshot). The audit finding is that every one of them uses the
*fresh-connection-per-call* pattern — connect, use inside a single call frame,
close — so no connection object is ever shared across threads. WAL handles the
"database is locked" contention; the per-call scoping handles thread-safety.

These tests prove that invariant under real concurrency and guard it against
regression. If someone later "optimizes" a helper to cache a connection in a
module global, `check_same_thread=False` would silently permit cross-thread use
and this stress test is what should start failing.

No LLM / Ollama. DB paths are monkeypatched to per-test temp files so counts are
exact and nothing leaks into the session data dir.

Run: python3 -m pytest tests/test_db_thread_safety.py -v
"""

import os
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.context_snapshot as snap  # noqa: E402
import cognition.run_tracer as tracer  # noqa: E402
import decision.log as dlog  # noqa: E402
import infrastructure.task_graph as tg  # noqa: E402

_WORKERS = 16
_N = 400  # writes per test — enough to interleave across the pool many times


def _tmpfile() -> str:
    f = tempfile.NamedTemporaryFile(suffix="_195.db", delete=False)
    f.close()
    return f.name


def _row_count(db_path: str, table: str) -> int:
    c = sqlite3.connect(db_path)
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


def _run_concurrently(fn, n: int = _N) -> list:
    """Run fn(i) across the thread pool; re-raise the first worker exception."""
    with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        futures = [ex.submit(fn, i) for i in range(n)]
        return [f.result() for f in futures]  # .result() re-raises in the caller


def test_decision_log_concurrent_writes(monkeypatch):
    db = _tmpfile()
    monkeypatch.setattr(dlog, "DB_PATH", db)
    dlog.init()

    def _write(i: int) -> int:
        return dlog.log(
            task=f"t{i}", action="answer", complexity="simple",
            brain_agent="terse", router_agent="terse", final_agent="terse",
            conflict=False, reflect=False, reflect_type="none",
        )

    ids = _run_concurrently(_write)
    # Every call returned a real autoincrement id (not the -1 failure sentinel)…
    assert all(i > 0 for i in ids)
    # …and every row actually landed, with no cross-thread connection error.
    assert _row_count(db, "brain_decisions") == _N


def test_run_tracer_concurrent_lifecycle(monkeypatch):
    db = _tmpfile()
    monkeypatch.setattr(tracer, "_RUNS_DB", db)
    tracer._init()

    # start() + finish() = two separate connections per logical run, both from
    # the same worker thread — the multi-connection-per-op pattern.
    def _run(i: int) -> None:
        rid = tracer.start(f"query {i}")
        tracer.finish(rid, agent="terse")

    _run_concurrently(_run)
    assert _row_count(db, "runs") == _N


def test_context_snapshot_concurrent_persist(monkeypatch):
    db = _tmpfile()
    monkeypatch.setattr(snap, "DB_PATH", db)
    snap.init()

    def _persist(i: int) -> int:
        return snap._persist({"request_id": f"ctx{i}", "timestamp": "2026-07-23T00:00:00Z"})

    ids = _run_concurrently(_persist)
    assert all(i > 0 for i in ids)
    assert _row_count(db, "snapshots") == _N


def test_task_graph_concurrent_create(monkeypatch):
    db = _tmpfile()
    monkeypatch.setattr(tg, "DB_PATH", db)
    tg.init_db()

    def _create(i: int) -> int:
        return tg.create_graph(
            goal=f"goal {i}",
            steps=[{"id": "s1", "agent": "terse", "prompt": "do it", "depends_on": []}],
        )

    ids = _run_concurrently(_create, n=200)  # heavier per-op; fewer iterations
    assert all(i > 0 for i in ids)
    assert _row_count(db, "task_graphs") == 200


def test_flagged_modules_never_cache_a_connection():
    """Regression guard: the anti-pattern #195 warns about is a module-level
    (module-global) connection reused across threads. Assert none of the flagged
    modules assign a `sqlite3.connect(...)`/`_db.connect(...)` result at module
    scope — connections must stay local to a function/`_conn()` helper call.
    """
    import ast
    import pathlib

    flagged = [
        "cognition/run_tracer.py", "routes/tasks.py", "infrastructure/task_graph.py",
        "decision/weights.py", "decision/log.py", "decision/model_choices.py",
        "cognition/context_snapshot.py",
    ]
    root = pathlib.Path(__file__).resolve().parent.parent

    def _is_connect_call(node) -> bool:
        if not isinstance(node, ast.Call):
            return False
        fn = node.func
        # sqlite3.connect(...) / _db.connect(...) / connect(...)
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        return name == "connect"

    offenders = []
    for rel in flagged:
        tree = ast.parse((root / rel).read_text())
        # Module-level assignments only (function bodies are fine).
        for node in tree.body:
            if isinstance(node, ast.Assign) and _is_connect_call(node.value):
                offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "module-level cached SQLite connection(s) found — with "
        "check_same_thread=False this permits silent cross-thread reuse (#195): "
        + ", ".join(offenders)
    )
