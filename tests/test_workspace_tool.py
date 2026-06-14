"""
Tests for tools/workspace.py — the jailed read-only file tool.

The security-critical cases: directory traversal, absolute-path injection, and
symlink escape must all be refused. Happy-path read/list/search must work.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.workspace as ws


def _make_tree(root):
    (root / "a.txt").write_text("hello world\nsecond line\n")
    (root / "sub").mkdir()
    (root / "sub" / "b.py").write_text("def f():\n    return 42  # needle\n")
    (root / "big.txt").write_text("x" * 5000)


# ── happy paths ────────────────────────────────────────────────────────────

def test_read_file(tmp_path):
    _make_tree(tmp_path)
    out = ws.read_file("a.txt", root=tmp_path)
    assert out["path"] == "a.txt"
    assert "hello world" in out["content"]
    assert out["size"] == len("hello world\nsecond line\n")


def test_read_nested_file(tmp_path):
    _make_tree(tmp_path)
    out = ws.read_file("sub/b.py", root=tmp_path)
    assert "return 42" in out["content"]


def test_list_dir(tmp_path):
    _make_tree(tmp_path)
    out = ws.list_dir("", root=tmp_path)
    names = {e["name"]: e["type"] for e in out["entries"]}
    assert names["sub"] == "dir"
    assert names["a.txt"] == "file"
    # Dirs sort before files.
    assert out["entries"][0]["type"] == "dir"


def test_search_finds_match(tmp_path):
    _make_tree(tmp_path)
    out = ws.search("needle", root=tmp_path)
    assert out["count"] == 1
    assert out["matches"][0]["path"] == "sub/b.py"
    assert out["matches"][0]["line"] == 2


def test_search_respects_max_results(tmp_path):
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text("match here\n")
    out = ws.search("match", max_results=3, root=tmp_path)
    assert out["count"] == 3
    assert out["truncated"] is True


# ── the jail (security) ──────────────────────────────────────────────────────

def test_traversal_is_blocked(tmp_path):
    _make_tree(tmp_path)
    with pytest.raises(ws.PathEscape):
        ws.read_file("../../etc/passwd", root=tmp_path)


def test_absolute_path_is_contained(tmp_path):
    _make_tree(tmp_path)
    # An absolute path must not override the join and read the real /etc/passwd;
    # it is reinterpreted relative to the root, where it doesn't exist.
    with pytest.raises((ws.NotFound, ws.PathEscape)):
        ws.read_file("/etc/passwd", root=tmp_path)


def test_symlink_escape_is_blocked(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    link = root / "link.txt"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(ws.PathEscape):
        ws.read_file("link.txt", root=root)


def test_search_skips_symlinked_escape(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("needle outside the jail\n")
    try:
        (root / "leak.txt").symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not supported on this platform")
    # The symlinked file resolves outside the root, so search must not surface it.
    out = ws.search("needle", root=root)
    assert out["count"] == 0


# ── error mapping ────────────────────────────────────────────────────────────

def test_read_missing_raises_notfound(tmp_path):
    with pytest.raises(ws.NotFound):
        ws.read_file("nope.txt", root=tmp_path)


def test_read_directory_raises(tmp_path):
    _make_tree(tmp_path)
    with pytest.raises(ws.WorkspaceError):
        ws.read_file("sub", root=tmp_path)


def test_read_oversize_raises_toolarge(tmp_path):
    _make_tree(tmp_path)
    with pytest.raises(ws.TooLarge):
        ws.read_file("big.txt", max_bytes=1000, root=tmp_path)


def test_read_binary_raises_nottext(tmp_path):
    (tmp_path / "bin").write_bytes(b"\x89PNG\x00\x01\x02\x00")
    with pytest.raises(ws.NotText):
        ws.read_file("bin", root=tmp_path)


def test_search_empty_query_raises(tmp_path):
    with pytest.raises(ws.WorkspaceError):
        ws.search("", root=tmp_path)


def test_list_missing_raises_notfound(tmp_path):
    with pytest.raises(ws.NotFound):
        ws.list_dir("does/not/exist", root=tmp_path)
