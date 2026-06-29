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


# ── write operations: happy paths ────────────────────────────────────────────

def test_write_then_read_roundtrip(tmp_path):
    out = ws.write_file("notes/todo.txt", "buy milk\n", root=tmp_path)
    assert out["created"] is True
    assert out["path"] == "notes/todo.txt"
    back = ws.read_file("notes/todo.txt", root=tmp_path)
    assert back["content"] == "buy milk\n"


def test_write_creates_parent_dirs(tmp_path):
    ws.write_file("a/b/c/deep.txt", "x", root=tmp_path)
    assert (tmp_path / "a" / "b" / "c" / "deep.txt").is_file()


def test_write_overwrite_reports_not_created(tmp_path):
    ws.write_file("f.txt", "one", root=tmp_path)
    out = ws.write_file("f.txt", "two", root=tmp_path)
    assert out["created"] is False
    assert ws.read_file("f.txt", root=tmp_path)["content"] == "two"


def test_make_dir_idempotent(tmp_path):
    first = ws.make_dir("sub/inner", root=tmp_path)
    assert first["created"] is True
    second = ws.make_dir("sub/inner", root=tmp_path)
    assert second["created"] is False
    assert (tmp_path / "sub" / "inner").is_dir()


def test_move_file(tmp_path):
    ws.write_file("src.txt", "data", root=tmp_path)
    out = ws.move("src.txt", "dst/moved.txt", root=tmp_path)
    assert out["dst"] == "dst/moved.txt"
    assert not (tmp_path / "src.txt").exists()
    assert ws.read_file("dst/moved.txt", root=tmp_path)["content"] == "data"


def test_move_overwrite(tmp_path):
    ws.write_file("a.txt", "AAA", root=tmp_path)
    ws.write_file("b.txt", "BBB", root=tmp_path)
    ws.move("a.txt", "b.txt", overwrite=True, root=tmp_path)
    assert ws.read_file("b.txt", root=tmp_path)["content"] == "AAA"


def test_delete_file(tmp_path):
    ws.write_file("gone.txt", "bye", root=tmp_path)
    out = ws.delete("gone.txt", root=tmp_path)
    assert out["deleted"] is True
    with pytest.raises(ws.NotFound):
        ws.read_file("gone.txt", root=tmp_path)


def test_delete_dir_recursive(tmp_path):
    ws.write_file("d/inner/x.txt", "x", root=tmp_path)
    ws.delete("d", recursive=True, root=tmp_path)
    assert not (tmp_path / "d").exists()


# ── write operations: the jail + error mapping ───────────────────────────────

def test_write_traversal_is_blocked(tmp_path):
    with pytest.raises(ws.PathEscape):
        ws.write_file("../escape.txt", "pwned", root=tmp_path)


def test_write_through_symlink_escape_is_blocked(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(ws.PathEscape):
        ws.write_file("link/evil.txt", "x", root=root)


def test_write_binary_content_raises_nottext(tmp_path):
    with pytest.raises(ws.NotText):
        ws.write_file("b.txt", "before\x00after", root=tmp_path)


def test_write_oversize_raises_toolarge(tmp_path):
    with pytest.raises(ws.TooLarge):
        ws.write_file("big.txt", "x" * 2000, max_bytes=1000, root=tmp_path)


def test_write_no_overwrite_raises_on_existing(tmp_path):
    ws.write_file("keep.txt", "first", root=tmp_path)
    with pytest.raises(ws.WorkspaceError):
        ws.write_file("keep.txt", "second", overwrite=False, root=tmp_path)
    assert ws.read_file("keep.txt", root=tmp_path)["content"] == "first"


def test_write_to_root_raises(tmp_path):
    with pytest.raises(ws.WorkspaceError):
        ws.write_file("", "x", root=tmp_path)


def test_make_dir_over_existing_file_raises(tmp_path):
    ws.write_file("clash", "x", root=tmp_path)
    with pytest.raises(ws.WorkspaceError):
        ws.make_dir("clash", root=tmp_path)


def test_move_missing_src_raises_notfound(tmp_path):
    with pytest.raises(ws.NotFound):
        ws.move("nope.txt", "dst.txt", root=tmp_path)


def test_move_clobber_without_overwrite_raises(tmp_path):
    ws.write_file("a.txt", "AAA", root=tmp_path)
    ws.write_file("b.txt", "BBB", root=tmp_path)
    with pytest.raises(ws.WorkspaceError):
        ws.move("a.txt", "b.txt", root=tmp_path)


def test_delete_missing_raises_notfound(tmp_path):
    with pytest.raises(ws.NotFound):
        ws.delete("ghost.txt", root=tmp_path)


def test_delete_nonempty_dir_without_recursive_raises(tmp_path):
    ws.write_file("d/x.txt", "x", root=tmp_path)
    with pytest.raises(ws.WorkspaceError):
        ws.delete("d", root=tmp_path)


def test_delete_root_is_refused(tmp_path):
    with pytest.raises(ws.WorkspaceError):
        ws.delete("", root=tmp_path)
    assert tmp_path.exists()
