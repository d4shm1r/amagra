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

The root is ``$AMAGRA_WORKSPACE`` (default ``<project>/workspace``).

Reads (``read_file``/``list_dir``/``search``) and writes (``write_file``/``make_dir``/
``move``/``delete``) both go through the same ``_safe_resolve`` chokepoint, so the jail
holds for every operation. Writes are a higher-trust capability: the HTTP surface
(``routes/workspace.py``) is an *owner action* — never in ``api.py``'s ``_PUBLIC_PATHS``,
so it requires the owner key when ``REQUIRE_AUTH=1``. Code execution remains a separate
capability (the sandbox), not part of this module.
"""

import os
import shutil
import tempfile
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


# ── write operations (owner-gated at the HTTP layer) ─────────────────────────
# Every write resolves through _safe_resolve first, so the jail (traversal /
# absolute-path / symlink escape → PathEscape) holds identically to reads.

def write_file(rel_path: str, content: str, max_bytes: int = DEFAULT_MAX_READ_BYTES,
               overwrite: bool = True, root: Path | None = None) -> dict:
    """Write a UTF-8 text file inside the workspace, creating parent dirs as needed.

    Text-only and bounded, mirroring read_file: NUL bytes are rejected (NotText)
    and content over max_bytes is rejected (TooLarge). The write is atomic — staged
    to a temp file in the same directory, then os.replace()'d into place — so a
    reader never sees a half-written file. Returns {path, size, created}.
    """
    root = (root or workspace_root()).resolve()
    target = _safe_resolve(rel_path, root)
    if target == root or target.is_dir():
        raise WorkspaceError(f"is a directory, not a file: {rel_path!r}")
    if "\x00" in content:
        raise NotText(f"refusing to write binary (NUL) content: {rel_path!r}")
    data = content.encode("utf-8")
    if len(data) > max_bytes:
        raise TooLarge(f"content is {len(data)} bytes (limit {max_bytes})")
    existed = target.exists()
    if existed and not overwrite:
        raise WorkspaceError(f"file exists and overwrite=False: {rel_path!r}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace: temp file in the same dir (same filesystem) → os.replace.
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {"path": _rel(target, root), "size": len(data), "created": not existed}


def make_dir(rel_path: str, root: Path | None = None) -> dict:
    """Create a directory (and parents) inside the workspace. Idempotent.

    Returns {path, created}. A pre-existing file at the path is a conflict.
    """
    root = (root or workspace_root()).resolve()
    target = _safe_resolve(rel_path, root)
    if target == root:
        return {"path": "", "created": False}
    if target.exists() and not target.is_dir():
        raise WorkspaceError(f"a file already exists at: {rel_path!r}")
    existed = target.is_dir()
    target.mkdir(parents=True, exist_ok=True)
    return {"path": _rel(target, root), "created": not existed}


def move(src_path: str, dst_path: str, overwrite: bool = False,
         root: Path | None = None) -> dict:
    """Move/rename a file or directory within the workspace. Returns {src, dst}.

    Both endpoints are resolved through the jail, so neither side can escape the
    root. Parent dirs of the destination are created. Refuses to clobber an
    existing destination unless overwrite=True.
    """
    root = (root or workspace_root()).resolve()
    src = _safe_resolve(src_path, root)
    dst = _safe_resolve(dst_path, root)
    if src == root or dst == root:
        raise WorkspaceError("cannot move the workspace root itself")
    if not src.exists():
        raise NotFound(f"no such path: {src_path!r}")
    if dst.exists():
        if not overwrite:
            raise WorkspaceError(f"destination exists and overwrite=False: {dst_path!r}")
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"src": src_path.lstrip("/\\"), "dst": _rel(dst, root)}


def delete(rel_path: str, recursive: bool = False, root: Path | None = None) -> dict:
    """Delete a file or directory inside the workspace. Returns {path, deleted}.

    A non-empty directory requires recursive=True. The workspace root itself can
    never be deleted.
    """
    root = (root or workspace_root()).resolve()
    target = _safe_resolve(rel_path, root)
    if target == root:
        raise WorkspaceError("refusing to delete the workspace root")
    if not target.exists():
        raise NotFound(f"no such path: {rel_path!r}")
    if target.is_dir():
        if any(target.iterdir()) and not recursive:
            raise WorkspaceError(f"directory not empty (pass recursive=True): {rel_path!r}")
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"path": _rel(target, root), "deleted": True}
