"""
Unit tests for infrastructure/db.py — the central DB path registry.

Covers default (separate-file) resolution, the AMAGRA_DB single-file override,
unknown-name errors, parent-dir creation, and that connect() returns a usable
sqlite3 connection.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure import db


def test_path_default_layout(monkeypatch):
    monkeypatch.delenv("AMAGRA_DB", raising=False)
    assert db.path("runs").endswith(os.path.join("logs", "runs.db"))
    assert db.path("memory").endswith(os.path.join("memory", "agent_memory.db"))
    assert db.path("tasks").endswith("tasks.db")


def test_path_is_absolute(monkeypatch):
    monkeypatch.delenv("AMAGRA_DB", raising=False)
    assert os.path.isabs(db.path("decisions"))


def test_unknown_name_raises():
    try:
        db.path("does-not-exist")
        assert False, "expected KeyError"
    except KeyError as e:
        assert "unknown database" in str(e)


def test_single_file_override_collapses_all(monkeypatch, tmp_path):
    target = tmp_path / "amagra.db"
    monkeypatch.setenv("AMAGRA_DB", str(target))
    # Every logical name now resolves to the one file.
    assert db.path("runs") == str(target)
    assert db.path("memory") == str(target)
    assert db.path("decisions") == str(target)


def test_single_file_relative_is_rooted(monkeypatch):
    monkeypatch.setenv("AMAGRA_DB", "amagra.db")
    p = db.path("runs")
    assert os.path.isabs(p)
    assert p.endswith("amagra.db")


def test_connect_returns_usable_connection(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_DB", str(tmp_path / "amagra.db"))
    conn = db.connect("runs")
    try:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        assert conn.execute("SELECT x FROM t").fetchone()[0] == 1
    finally:
        conn.close()
    assert isinstance(conn, sqlite3.Connection)


def test_connect_creates_parent_dir(monkeypatch, tmp_path):
    nested = tmp_path / "a" / "b" / "amagra.db"
    monkeypatch.setenv("AMAGRA_DB", str(nested))
    conn = db.connect("memory")
    conn.close()
    assert nested.parent.is_dir()
