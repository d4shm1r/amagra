"""
Tests for the workspace-write tools exposed through tools/catalog.py.

Writes are opt-in (AMAGRA_WORKSPACE_WRITE=1), mirroring the owner-gate posture of
the HTTP write routes. These tests exercise the gate (hidden by default, visible
+ functional when enabled) and confirm the jail still holds through the catalog
seam — all in an isolated temp workspace, no real files touched.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.catalog as catalog
import tools.workspace as ws


@pytest.fixture
def temp_ws(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="catalog-test-") as tmp:
        monkeypatch.setenv("AMAGRA_WORKSPACE", tmp)
        yield Path(tmp).resolve()


def test_writes_hidden_by_default(temp_ws, monkeypatch):
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    available = catalog.available_tools()
    assert "read_file" in available          # reads always on
    assert "write_file" not in available     # writes gated off
    assert "make_dir" not in available
    assert "move" not in available


def test_write_blocked_when_gated_off(temp_ws, monkeypatch):
    monkeypatch.delenv("AMAGRA_WORKSPACE_WRITE", raising=False)
    with pytest.raises(PermissionError):
        catalog.execute("write_file", {"path": "x.txt", "content": "nope"})
    assert not (temp_ws / "x.txt").exists()


def test_write_and_make_dir_when_enabled(temp_ws, monkeypatch):
    monkeypatch.setenv("AMAGRA_WORKSPACE_WRITE", "1")
    assert "write_file" in catalog.available_tools()

    catalog.execute("make_dir", {"path": "pkg"})
    catalog.execute("write_file", {"path": "pkg/core.py", "content": "V = 1\n"})

    assert (temp_ws / "pkg").is_dir()
    assert (temp_ws / "pkg/core.py").read_text() == "V = 1\n"


def test_move_when_enabled(temp_ws, monkeypatch):
    monkeypatch.setenv("AMAGRA_WORKSPACE_WRITE", "1")
    (temp_ws / "a.txt").write_text("hi", encoding="utf-8")

    catalog.execute("move", {"src": "a.txt", "dst": "b.txt"})

    assert not (temp_ws / "a.txt").exists()
    assert (temp_ws / "b.txt").read_text() == "hi"


def test_jail_holds_through_catalog(temp_ws, monkeypatch):
    """A traversal path must be refused by the same PathEscape guard as reads."""
    monkeypatch.setenv("AMAGRA_WORKSPACE_WRITE", "1")
    with pytest.raises(ws.PathEscape):
        catalog.execute("write_file", {"path": "../escape.txt", "content": "x"})
    assert not (temp_ws.parent / "escape.txt").exists()
