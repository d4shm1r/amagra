import secrets
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

import core.api_keys as _ak
from .deps import CreateKeyRequest

router = APIRouter()


class CreateKeyRequestFull(CreateKeyRequest):
    org_id: str | None = None


class CreateOrgRequest(BaseModel):
    name: str
    owner_email: str = ""


@router.get("/usage")
async def get_usage(request: Request, x_api_key: Optional[str] = Header(default=None)):
    raw = x_api_key or request.headers.get("X-API-Key", "")
    if not raw:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    info = _ak.get_usage(raw)
    if info is None:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return info


@router.post("/admin/keys")
async def create_api_key(body: CreateKeyRequestFull):
    try:
        raw = _ak.create_key(body.owner, body.tier, org_id=body.org_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "key":    raw,
        "owner":  body.owner,
        "tier":   body.tier,
        "org_id": body.org_id,
        "note":   "Store this key securely — it will not be shown again.",
    }


@router.get("/admin/keys")
async def list_api_keys():
    return {"keys": _ak.list_keys()}


@router.delete("/admin/keys/{key_id}")
async def deactivate_api_key(key_id: int):
    _ak.deactivate_key(key_id)
    return {"deactivated": key_id}


# ── Org management ─────────────────────────────────────────────

@router.post("/admin/orgs")
async def create_org(body: CreateOrgRequest):
    """
    Create a team org. Returns an org_id that links multiple API keys
    to a shared world model and event bus session.
    Pass org_id when creating team-tier keys via POST /admin/keys.
    """
    org_id = "org-" + secrets.token_urlsafe(12)
    # Persist to api_keys.db for now; a dedicated orgs table can be added later
    try:
        import sqlite3, os
        db = _ak.DB_PATH
        con = sqlite3.connect(db, timeout=5)
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS orgs (
                    org_id       TEXT PRIMARY KEY,
                    name         TEXT NOT NULL,
                    owner_email  TEXT,
                    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                    active       INTEGER DEFAULT 1
                )
            """)
        except Exception:
            pass
        con.execute(
            "INSERT OR IGNORE INTO orgs (org_id, name, owner_email) VALUES (?,?,?)",
            (org_id, body.name, body.owner_email),
        )
        con.commit()
        con.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "org_id":      org_id,
        "name":        body.name,
        "note":        "Add org_id to POST /admin/keys to link team members. "
                       "Members sharing an org_id share one world model and event stream.",
    }


@router.get("/admin/orgs")
async def list_orgs():
    try:
        import sqlite3
        con = sqlite3.connect(_ak.DB_PATH, timeout=3)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT org_id, name, owner_email, created_at, active FROM orgs"
            ).fetchall()
        except Exception:
            rows = []
        con.close()
        return {"orgs": [dict(r) for r in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
