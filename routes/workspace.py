"""
routes/workspace.py — HTTP surface for the jailed file tool (tools/workspace.py).

All paths are confined to the workspace root; escape attempts return 403.
Reads (GET): read, list, search. Writes (POST): write, mkdir, move, delete.

Writes are an owner action: none of these paths are in api.py `_PUBLIC_PATHS`, so
when REQUIRE_AUTH=1 they require the owner key — same trust gate as /debug/prompt.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import tools.workspace as ws

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _handle(fn, *args, **kwargs):
    """Run a workspace op, mapping its typed errors to HTTP status codes."""
    try:
        return fn(*args, **kwargs)
    except ws.PathEscape as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ws.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ws.TooLarge, ws.NotText, ws.WorkspaceError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/root")
def get_root():
    """Report the active workspace root (absolute path on the server)."""
    return {"root": str(ws.workspace_root())}


@router.get("/read")
def read(path: str):
    return _handle(ws.read_file, path)


@router.get("/list")
def list_dir(path: str = ""):
    return _handle(ws.list_dir, path)


@router.get("/search")
def search(q: str, glob: str = "**/*", max_results: int = ws.DEFAULT_MAX_RESULTS):
    return _handle(ws.search, q, glob=glob, max_results=max_results)


# ── write surface (owner action — not in _PUBLIC_PATHS) ──────────────────────

class WriteBody(BaseModel):
    path: str
    content: str
    overwrite: bool = True


class MkdirBody(BaseModel):
    path: str


class MoveBody(BaseModel):
    src: str
    dst: str
    overwrite: bool = False


class DeleteBody(BaseModel):
    path: str
    recursive: bool = False


@router.post("/write")
def write(body: WriteBody):
    return _handle(ws.write_file, body.path, body.content, overwrite=body.overwrite)


@router.post("/mkdir")
def mkdir(body: MkdirBody):
    return _handle(ws.make_dir, body.path)


@router.post("/move")
def move(body: MoveBody):
    return _handle(ws.move, body.src, body.dst, overwrite=body.overwrite)


@router.post("/delete")
def delete(body: DeleteBody):
    return _handle(ws.delete, body.path, recursive=body.recursive)
