"""
routes/sandbox.py — HTTP surface for tools/sandbox.py.

Running arbitrary code is high-trust, so the route is opt-in: it returns 403
unless AMAGRA_SANDBOX=1 is set. Resource limits live in tools/sandbox.py.
"""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import tools.sandbox as sbx

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

_MAX_TIMEOUT = 30  # hard ceiling regardless of request


def _enabled() -> bool:
    return os.environ.get("AMAGRA_SANDBOX", "0") == "1"


class RunRequest(BaseModel):
    code: str
    timeout: float | None = None


@router.get("/status")
def status():
    """Whether code execution is enabled, the active limits, and how strong
    the isolation actually is (#134)."""
    isolation = sbx.isolation_mode() if os.name == "posix" else "unavailable"
    jailed = isolation == "bwrap"
    out = {
        "enabled": _enabled(),
        "limits": {
            "timeout_s": sbx.DEFAULT_TIMEOUT,
            "cpu_s": sbx.DEFAULT_CPU_SECONDS,
            "mem_bytes": sbx.DEFAULT_MEM_BYTES,
            "max_timeout_s": _MAX_TIMEOUT,
        },
        "isolation": isolation,
        "network_isolated": jailed,
        "filesystem_isolated": jailed,
    }
    if not jailed:
        out["warning"] = (
            "No OS-level jail: submitted code can read any file the server "
            "user can read and make outbound network connections. Install "
            "bubblewrap (bwrap) for real isolation; do not enable the sandbox "
            "on a shared or internet-exposed host without it."
        )
    return out


@router.post("/run")
def run(req: RunRequest):
    if not _enabled():
        raise HTTPException(
            status_code=403,
            detail="sandbox disabled — set AMAGRA_SANDBOX=1 to enable code execution",
        )
    timeout = sbx.DEFAULT_TIMEOUT if req.timeout is None else max(0.1, min(req.timeout, _MAX_TIMEOUT))
    try:
        return sbx.run_python(req.code, timeout=timeout)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # e.g. non-POSIX host: the sandbox can't enforce resource limits there.
        raise HTTPException(status_code=501, detail=str(e))
