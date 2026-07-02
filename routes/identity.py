"""
routes/identity.py — read-only view of the Identity contract (models/identity.py).

GET /identity              full snapshot (intrinsic / learned / meta)
GET /identity/fingerprint  stable content hash — compare across restarts,
                           provider swaps, or deployments to verify the
                           "capability replacement must not modify identity"
                           invariant on a live system
"""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/identity")
def identity_snapshot():
    """One serializable view of who the system is for and what it has learned,
    split by mutation discipline (intrinsic vs learned). See docs/design/IDENTITY.md."""
    try:
        from models.identity import snapshot
        return snapshot()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/identity/fingerprint")
def identity_fingerprint():
    """Stable hash of identity content (volatile meta excluded)."""
    try:
        from models.identity import fingerprint, IDENTITY_SCHEMA_VERSION
        return {
            "fingerprint":    fingerprint(),
            "schema_version": IDENTITY_SCHEMA_VERSION,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
