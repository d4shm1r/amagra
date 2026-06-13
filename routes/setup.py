"""
routes/setup.py — First-run onboarding support.

GET  /setup/status   Detect Ollama and report which required models are present.
POST /setup/pull     Stream an Ollama model pull as SSE progress events.

Both routes are public (listed in api.py `_PUBLIC_PATHS`) because onboarding
runs before the user has an API key. The pull route only accepts models from the
required set, so it can't be used as an arbitrary download proxy.
"""

import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _required_models() -> list[str]:
    """The two models Amagra needs, honoring the same env vars as the provider."""
    return [
        os.environ.get("OLLAMA_MODEL", "phi4-mini:latest"),
        os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    ]


def _installed_models() -> list[str] | None:
    """
    Return the list of installed Ollama model names, or None if Ollama is
    unreachable. Names are matched leniently (a bare `nomic-embed-text` request
    is satisfied by an installed `nomic-embed-text:latest`).
    """
    try:
        import httpx
        r = httpx.get(f"{_ollama_base()}/api/tags", timeout=3.0)
        if r.status_code != 200:
            return None
        return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return None


def _is_present(required: str, installed: list[str]) -> bool:
    # Match exactly, or by base name so "x" satisfies "x:latest" and vice versa.
    req_base = required.split(":")[0]
    return any(
        name == required or name.split(":")[0] == req_base
        for name in installed
    )


@router.get("/setup/status")
def setup_status():
    required = _required_models()
    installed = _installed_models()

    if installed is None:
        return {
            "ollama":    "offline",
            "ready":     False,
            "required":  required,
            "installed": [],
            "missing":   required,
            "hint":      "Start Ollama with: ollama serve",
        }

    missing = [m for m in required if not _is_present(m, installed)]
    return {
        "ollama":    "online",
        "ready":     len(missing) == 0,
        "required":  required,
        "installed": installed,
        "missing":   missing,
        "hint":      None,
    }


class PullRequest(BaseModel):
    model: str


@router.post("/setup/pull")
def setup_pull(req: PullRequest):
    if req.model not in _required_models():
        raise HTTPException(
            status_code=400,
            detail=f"Refusing to pull '{req.model}': not a required Amagra model.",
        )

    def _event_stream():
        try:
            import httpx
            with httpx.stream(
                "POST",
                f"{_ollama_base()}/api/pull",
                json={"name": req.model, "stream": True},
                timeout=None,
            ) as resp:
                if resp.status_code != 200:
                    yield f"data: {json.dumps({'type': 'error', 'detail': f'Ollama returned {resp.status_code}'})}\n\n"
                    return
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if "error" in payload:
                        yield f"data: {json.dumps({'type': 'error', 'detail': payload['error']})}\n\n"
                        return
                    total = payload.get("total")
                    completed = payload.get("completed")
                    percent = (
                        round(completed / total * 100, 1)
                        if total and completed is not None
                        else None
                    )
                    yield "data: " + json.dumps({
                        "type":      "progress",
                        "status":    payload.get("status", ""),
                        "completed": completed,
                        "total":     total,
                        "percent":   percent,
                    }) + "\n\n"
            yield f"data: {json.dumps({'type': 'done', 'model': req.model})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
