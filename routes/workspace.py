"""
routes/workspace.py — HTTP surface for the jailed file tool (tools/workspace.py).

All paths are confined to the workspace root; escape attempts return 403.
Read-only: read, list, search.
"""

from fastapi import APIRouter, HTTPException

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
