"""
Run-log tests — the append-only "transparent state" surface (core/run_log.py).

The promise is that a run is debuggable with a plain SELECT: one row per run,
meta round-trips as JSON, and appends accumulate in order. Tests use tmp_path so
they never touch the real logs/runtime.db.
"""
import json
import sqlite3

from core.contract import Result
from core.run_log import RunLog


def _db(tmp_path):
    return str(tmp_path / "runtime.db")


def test_append_writes_one_selectable_row(tmp_path):
    log = RunLog(path=_db(tmp_path))
    log.append(task="count loc", ext_id="python_dev",
               result=Result(output="def f(): ...", meta={"gram_winner": "b"}))

    con = sqlite3.connect(_db(tmp_path))
    rows = con.execute("SELECT task, ext_id, output, meta FROM runs").fetchall()
    con.close()

    assert len(rows) == 1
    task, ext_id, output, meta = rows[0]
    assert (task, ext_id, output) == ("count loc", "python_dev", "def f(): ...")
    assert json.loads(meta) == {"gram_winner": "b"}   # meta round-trips as JSON


def test_appends_accumulate_in_order(tmp_path):
    log = RunLog(path=_db(tmp_path))
    for i in range(3):
        log.append(task=f"t{i}", ext_id="echo", result=Result(output=str(i)))

    con = sqlite3.connect(_db(tmp_path))
    outputs = [r[0] for r in con.execute(
        "SELECT output FROM runs ORDER BY id").fetchall()]
    con.close()
    assert outputs == ["0", "1", "2"]


def test_empty_meta_serializes_to_empty_object(tmp_path):
    log = RunLog(path=_db(tmp_path))
    log.append(task="t", ext_id="e", result=Result(output="o"))

    con = sqlite3.connect(_db(tmp_path))
    (meta,) = con.execute("SELECT meta FROM runs").fetchone()
    con.close()
    assert json.loads(meta) == {}


def test_constructor_creates_parent_dir(tmp_path):
    # RunLog must mkdir the logs/ dir it's pointed at, not assume it exists.
    nested = str(tmp_path / "deep" / "logs" / "runtime.db")
    RunLog(path=nested)
    log = RunLog(path=nested)   # idempotent: opening an existing db must not error
    log.append(task="t", ext_id="e", result=Result(output="o"))

    con = sqlite3.connect(nested)
    assert con.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    con.close()


def test_wal_journal_mode_is_set(tmp_path):
    RunLog(path=_db(tmp_path))
    con = sqlite3.connect(_db(tmp_path))
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    assert mode.lower() == "wal"
