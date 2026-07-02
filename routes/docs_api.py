import os
from datetime import datetime
from fastapi import APIRouter, HTTPException

from .deps import _ROOT

router = APIRouter()

_DOCS_DIR = os.path.join(_ROOT, "docs")

# Curated project docs served over the API. Names are stable slugs; values are
# paths relative to docs/ (see docs/PROJECT_MAP.md for the directory layout).
# Only files in this map are readable — no path components accepted.
_ALLOWED_DOCS = {
    "project-map":       "PROJECT_MAP.md",
    "guide":             "GUIDE.md",
    "architecture":      "ARCHITECTURE.md",
    "reference":         "REFERENCE.md",
    "roadmap":           "ROADMAP.md",
    "design-principles": "design/DESIGN_PRINCIPLES.md",
    "identity":          "design/IDENTITY.md",
    "plugin-architecture": "design/PLUGIN_ARCHITECTURE.md",
    "history":           "records/HISTORY.md",
    "findings":          "records/FINDINGS.md",
    "failures":          "records/FAILURES.md",
    "issues":            "records/ISSUES.md",
    "vision":            "product/VISION.md",
    "comparison":        "product/COMPARISON.md",
    "deploy":            "ops/DEPLOY.md",
    "providers":         "ops/PROVIDERS.md",
}


# NOTE: mounted at /docs/index, not /docs — FastAPI's built-in Swagger UI owns
# the exact path /docs, which silently shadowed the old list endpoint.
@router.get("/docs/index")
def list_docs():
    docs = []
    for name, rel in _ALLOWED_DOCS.items():
        path = os.path.join(_DOCS_DIR, rel)
        if os.path.exists(path):
            docs.append({
                "name":     name,
                "size":     os.path.getsize(path),
                "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
            })
    return {"docs": sorted(docs, key=lambda d: d["name"])}


@router.get("/docs/{name}")
def get_doc(name: str):
    rel = _ALLOWED_DOCS.get(name)
    if rel is None:
        raise HTTPException(status_code=404, detail=f"Doc '{name}' not found")
    path = os.path.join(_DOCS_DIR, rel)
    if os.path.exists(path):
        return {"name": name, "content": open(path, encoding="utf-8").read()}
    raise HTTPException(status_code=404, detail=f"Doc '{name}' not found")
