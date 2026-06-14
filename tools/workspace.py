"""
tools/workspace.py — a read-only file tool jailed to a single root directory.

The first v1.1 "tool-using agents" capability: let agents read, list, and search
files — but never outside a configured workspace root. The security boundary is
one primitive applied to every path:

    resolved = (root / user_path).resolve()      # follows symlinks
    if not resolved.is_relative_to(root_real):   # escape → rejected
        raise PathEscape

Because ``.resolve()`` collapses ``..`` and follows symlinks before the check,
this defeats directory traversal (``../../etc/passwd``), absolute-path injection
(``/etc/passwd``), and symlink escapes (a link inside the root pointing out).

The root is ``$AMAGRA_WORKSPACE`` (default ``<project>/workspace``). This module
is intentionally read-only — writing and code execution are separate, higher-
trust capabilities (sandbox) tracked elsewhere in v1.1.
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Defaults — generous but bounded, to keep a single read/search from blowing up
# memory or stalling on a giant binary.
DEFAULT_MAX_READ_BYTES = 1 * 1024 * 1024       # 1 MB per file read
DEFAULT_MAX_SEARCH_FILE_BYTES = 512 * 1024     # skip files larger than this in search
DEFAULT_MAX_RESULTS = 200


class WorkspaceError(Exception):
    """Base for workspace tool errors."""


class PathEscape(WorkspaceError):
    """A path resolved outside the workspace root."""


class NotFound(WorkspaceError):
    """The requested path does not exist."""


class TooLarge(WorkspaceError):
    """The file exceeds the allowed read size."""


class NotText(WorkspaceError):
    """The file is binary / not decodable as UTF-8 text."""


def workspace_root() -> Path:
    """The jail root: $AMAGRA_WORKSPACE, else <project>/workspace. Created if missing."""
    env = os.environ.get("AMAGRA_WORKSPACE", "").strip()
    root = Path(env) if env else (_PROJECT_ROOT / "workspace")
    if not root.is_absolute():
        root = (_PROJECT_ROOT / root)
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_resolve(rel_path: str, root: Path | None = None) -> Path:
    """Resolve a user path against the root, refusing anything that escapes it.

    The single chokepoint every operation goes through.
    """
    root = (root or workspace_root()).resolve()
    # Treat the input as relative to the root regardless of leading slashes, so
    # an absolute "/etc/passwd" can't override the join — but the is_relative_to
    # check below is the real guarantee.
    candidate = (root / str(rel_path).lstrip("/\\")).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise PathEscape(f"path escapes the workspace root: {rel_path!r}")
    return candidate


def _rel(path: Path, root: Path) -> str:
    """Path relative to root, as a forward-slash string ('' for the root itself)."""
    r = path.relative_to(root).as_posix()
    return "" if r == "." else r


def read_file(rel_path: str, max_bytes: int = DEFAULT_MAX_READ_BYTES,
              root: Path | None = None) -> dict:
    """Read a UTF-8 text file inside the workspace. Returns {path, size, content}."""
    root = (root or workspace_root()).resolve()
    target = _safe_resolve(rel_path, root)
    if not target.exists():
        raise NotFound(f"no such file: {rel_path!r}")
    if target.is_dir():
        raise WorkspaceError(f"is a directory, not a file: {rel_path!r}")
    size = target.stat().st_size
    if size > max_bytes:
        raise TooLarge(f"file is {size} bytes (limit {max_bytes})")
    data = target.read_bytes()
    if b"\x00" in data:
        raise NotText(f"file looks binary: {rel_path!r}")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise NotText(f"file is not valid UTF-8: {rel_path!r}") from e
    return {"path": _rel(target, root), "size": size, "content": content}


def list_dir(rel_path: str = "", root: Path | None = None) -> dict:
    """List a directory inside the workspace. Returns {path, entries:[{name,type,size}]}."""
    root = (root or workspace_root()).resolve()
    target = _safe_resolve(rel_path, root)
    if not target.exists():
        raise NotFound(f"no such directory: {rel_path!r}")
    if not target.is_dir():
        raise WorkspaceError(f"not a directory: {rel_path!r}")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
        is_dir = child.is_dir()
        entries.append({
            "name": child.name,
            "path": _rel(child, root),
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else child.stat().st_size,
        })
    return {"path": _rel(target, root), "entries": entries}


def search(query: str, glob: str = "**/*", max_results: int = DEFAULT_MAX_RESULTS,
           max_file_bytes: int = DEFAULT_MAX_SEARCH_FILE_BYTES,
           root: Path | None = None) -> dict:
    """Plain substring search over text files in the workspace.

    Returns {query, count, truncated, matches:[{path, line, text}]}. Each glob
    match is re-checked through the jail, so a symlinked entry can't leak.
    """
    if not query:
        raise WorkspaceError("query must not be empty")
    root = (root or workspace_root()).resolve()
    matches: list[dict] = []
    truncated = False
    for path in sorted(root.glob(glob)):
        if len(matches) >= max_results:
            truncated = True
            break
        if not path.is_file():
            continue
        try:
            safe = _safe_resolve(path.relative_to(root).as_posix(), root)
        except (PathEscape, ValueError):
            continue  # symlink or oddity pointing outside the root — skip
        try:
            if safe.stat().st_size > max_file_bytes:
                continue
            with safe.open("r", encoding="utf-8", errors="strict") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if query in line:
                        matches.append({
                            "path": _rel(safe, root),
                            "line": lineno,
                            "text": line.rstrip("\n")[:500],
                        })
                        if len(matches) >= max_results:
                            truncated = True
                            break
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — skip
    return {"query": query, "count": len(matches), "truncated": truncated,
            "matches": matches}
