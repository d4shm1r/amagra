"""
Tests for scripts/migrate_to_single_db.py — the one-shot SQLite consolidation.

Covers rowid/PK preservation (FAISS keys on memories.id), multi-table copy,
the dry-run vs --apply gate, the collision guard (same table name, different
schema), and the new infrastructure.db.distinct_paths() helper.
"""

import importlib
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scripts.migrate_to_single_db as mig
from infrastructure import db


def _make_db(path, create_sql, rows, table):
    conn = sqlite3.connect(path)
    conn.execute(create_sql)
    if rows:
        ncols = len(rows[0])
        conn.executemany(
            f'INSERT INTO {table} VALUES ({",".join("?" * ncols)})', rows
        )
    conn.commit()
    conn.close()


def _registry_to(monkeypatch, mapping, root):
    """Point the migration at a synthetic REGISTRY rooted at `root`."""
    monkeypatch.setattr(mig, "REGISTRY", mapping, raising=True)
    monkeypatch.setattr(mig, "_ROOT", str(root), raising=True)


def test_distinct_paths_default(monkeypatch):
    monkeypatch.delenv("AMAGRA_DB", raising=False)
    paths = db.distinct_paths()
    # One distinct file per logical store in separate-file mode.
    assert len(paths) == len(db.REGISTRY)
    assert any(p.endswith(os.path.join("memory", "agent_memory.db")) for p in paths)


def test_distinct_paths_single_file_collapses(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DB", str(tmp_path / "amagra.db"))
    assert db.distinct_paths() == [str(tmp_path / "amagra.db")]


def test_rowid_alias_preserved(monkeypatch, tmp_path):
    src = tmp_path / "mem.db"
    _make_db(
        src,
        "CREATE TABLE memories (id INTEGER PRIMARY KEY, body TEXT)",
        [(5, "a"), (9, "b")],  # non-contiguous ids must survive
        "memories",
    )
    _registry_to(monkeypatch, {"memory": "mem.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    rc = mig.main_args(["--target", str(target), "--apply"])
    assert rc == 0

    conn = sqlite3.connect(target)
    ids = [r[0] for r in conn.execute("SELECT id FROM memories ORDER BY id")]
    conn.close()
    assert ids == [5, 9]


def test_plain_rowid_preserved(monkeypatch, tmp_path):
    src = tmp_path / "ev.db"
    _make_db(src, "CREATE TABLE events (msg TEXT)", [("x",), ("y",), ("z",)], "events")
    # Force a non-contiguous rowid.
    conn = sqlite3.connect(src)
    conn.execute("DELETE FROM events WHERE rowid=2")
    conn.commit()
    rowids_before = [r[0] for r in conn.execute("SELECT rowid FROM events")]
    conn.close()

    _registry_to(monkeypatch, {"events": "ev.db"}, tmp_path)
    target = tmp_path / "amagra.db"
    assert mig.main_args(["--target", str(target), "--apply"]) == 0

    conn = sqlite3.connect(target)
    rowids_after = [r[0] for r in conn.execute("SELECT rowid FROM events")]
    conn.close()
    assert rowids_after == rowids_before


def test_dry_run_writes_nothing(monkeypatch, tmp_path):
    src = tmp_path / "ev.db"
    _make_db(src, "CREATE TABLE events (msg TEXT)", [("x",)], "events")
    _registry_to(monkeypatch, {"events": "ev.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    assert mig.main_args(["--target", str(target), "--dry-run"]) == 0
    assert not target.exists()


def test_collision_different_schema_refuses(monkeypatch, tmp_path):
    _make_db(tmp_path / "a.db", "CREATE TABLE runs (run_id TEXT)", [("r1",)], "runs")
    _make_db(tmp_path / "b.db", "CREATE TABLE runs (id INTEGER, x REAL)", [(1, 1.0)], "runs")
    _registry_to(monkeypatch, {"a": "a.db", "b": "b.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    rc = mig.main_args(["--target", str(target), "--apply"])
    assert rc == 1  # refused, did not corrupt


def test_archive_renames_sources(monkeypatch, tmp_path):
    src = tmp_path / "ev.db"
    _make_db(src, "CREATE TABLE events (msg TEXT)", [("x",)], "events")
    _registry_to(monkeypatch, {"events": "ev.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    assert mig.main_args(["--target", str(target), "--apply", "--archive"]) == 0
    # Source moved aside; data still readable from the consolidated file.
    assert not src.exists()
    assert (tmp_path / "ev.db.pre-consolidation").exists()
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    conn.close()


def test_no_archive_leaves_sources(monkeypatch, tmp_path):
    src = tmp_path / "ev.db"
    _make_db(src, "CREATE TABLE events (msg TEXT)", [("x",)], "events")
    _registry_to(monkeypatch, {"events": "ev.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    assert mig.main_args(["--target", str(target), "--apply"]) == 0
    assert src.exists()  # untouched without --archive


def test_target_exists_without_force_refuses(monkeypatch, tmp_path):
    src = tmp_path / "ev.db"
    _make_db(src, "CREATE TABLE events (msg TEXT)", [("x",)], "events")
    _registry_to(monkeypatch, {"events": "ev.db"}, tmp_path)

    target = tmp_path / "amagra.db"
    target.write_text("not empty")
    assert mig.main_args(["--target", str(target), "--apply"]) == 1
