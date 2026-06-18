"""
routes/debug_prompt.py — the cross-model prompt debugger.

  POST /debug/prompt   run one prompt across N models and return them side by side

This is the load-bearing half of the prompt debugger: the static analyzer
(ui/src/PromptEditorTab.jsx) already says *why* a prompt is weak; this endpoint
actually *runs* it, so the UI can show real outputs from one or many models
next to each other — same prompt, same system, same temperature.

Model configs reuse the exact shape and builder used by
routes/settings_provider.py, so a model that works in Provider Settings works
here unchanged. A blank api_key falls back to the stored owner key, matching
the /settings/llm/test behaviour.

Fan-out is concurrent: generate() is synchronous, so each call runs in a worker
thread via asyncio.to_thread and they are awaited together. One model failing
never sinks the others — its slot carries the error string instead of output.

Authenticated like the other owner actions (not in api.py `_PUBLIC_PATHS`):
it makes outbound model calls, possibly with the stored key.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from infrastructure import provider_config as pc
from routes.settings_provider import LLMConfig, _build_for, _validate

router = APIRouter()


class DebugRequest(BaseModel):
    prompt: str
    system: str | None = None
    temperature: float = 0.2
    # Empty = run against the single currently-configured brain provider, so the
    # default "just hit Run" path works with zero setup.
    models: list[LLMConfig] = Field(default_factory=list)


class DebugResult(BaseModel):
    provider: str
    model: str | None = None
    output: str | None = None
    latency_ms: int | None = None
    chars: int | None = None
    words: int | None = None
    error: str | None = None


def _resolve_models(models: list[LLMConfig]) -> list[dict]:
    """Validate each config and fill a blank api_key from the stored owner key."""
    if not models:
        cur = pc.current()  # {provider, model, base_url, ...} — no secret returned
        models = [LLMConfig(provider=cur["provider"], model=cur.get("model"),
                            base_url=cur.get("base_url"))]
    stored = pc.load()
    resolved: list[dict] = []
    for cfg in models:
        _validate(cfg)
        body = cfg.model_dump()
        if not body.get("api_key") and stored.get("api_key"):
            body["api_key"] = stored["api_key"]
        resolved.append(body)
    return resolved


def _run_one(body: dict, prompt: str, system: str | None, temperature: float) -> DebugResult:
    """Blocking single-model run — executed in a worker thread by the caller."""
    label_model = body.get("model")
    started = time.perf_counter()
    try:
        out = _build_for(body).generate(prompt, system_prompt=system, temperature=temperature)
        elapsed = int((time.perf_counter() - started) * 1000)
        return DebugResult(
            provider=body["provider"], model=label_model, output=out,
            latency_ms=elapsed, chars=len(out), words=len(out.split()),
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return DebugResult(
            provider=body["provider"], model=label_model,
            latency_ms=elapsed, error=str(exc),
        )


@router.post("/debug/prompt", response_model=list[DebugResult])
async def debug_prompt(req: DebugRequest):
    """Run req.prompt across every requested model concurrently, side by side."""
    bodies = _resolve_models(req.models)
    results = await asyncio.gather(
        *(asyncio.to_thread(_run_one, b, req.prompt, req.system, req.temperature)
          for b in bodies)
    )
    return list(results)
