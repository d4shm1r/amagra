import os
from datetime import datetime
from fastapi import APIRouter, HTTPException

from .deps import _ROOT

router = APIRouter()

_DOCS_DIR = os.path.join(_ROOT, "docs")
_ALLOWED_DOCS = {
    "findings", "known-issues", "dashboard-guide", "ui-guide",
    "tracker", "tracker-v1", "tracker-v2", "tracker-v3",
    "failures", "ModelOverview",
}


@router.get("/docs")
def list_docs():
    docs = []
    for name in _ALLOWED_DOCS:
        for ext in (".md", ".MD"):
            path = os.path.join(_DOCS_DIR, name + ext)
            if os.path.exists(path):
                docs.append({
                    "name":     name,
                    "size":     os.path.getsize(path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                })
                break
    return {"docs": sorted(docs, key=lambda d: d["name"])}


@router.get("/docs/{name}")
def get_doc(name: str):
    if name not in _ALLOWED_DOCS:
        raise HTTPException(status_code=404, detail=f"Doc '{name}' not found")
    for ext in (".md", ".MD"):
        path = os.path.join(_DOCS_DIR, name + ext)
        if os.path.exists(path):
            return {"name": name, "content": open(path, encoding="utf-8").read()}
    raise HTTPException(status_code=404, detail=f"Doc '{name}' not found")
