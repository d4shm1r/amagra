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

from decision import model_choices
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


# ── the bridge: a debug session → a structured, durable decision ───────────────
#
# /debug/prompt is stateless by design. This is where its throwaway structure
# (prompt, system, temperature, N candidates) is turned into knowledge, by
# capturing the one thing the run can't infer — which candidate won, and why.

class Candidate(BaseModel):
    provider: str
    model: str | None = None
    latency_ms: int | None = None
    chars: int | None = None
    words: int | None = None
    error: str | None = None


class DecisionRequest(BaseModel):
    prompt: str
    chosen_provider: str
    chosen_model: str | None = None
    system: str | None = None
    temperature: float = 0.2
    candidates: list[Candidate] = Field(default_factory=list)
    # The "why?" — the activation moment. Empty = a 'derived' (lower-trust) record.
    rationale: str = ""
    rationale_tags: list[str] = Field(default_factory=list)
    project: str = ""
    # If this choice revisits an earlier one, the old id it supersedes (currency).
    supersedes: int | None = None


def _decision_sentence(d: DecisionRequest) -> str:
    """A human-readable line for long-term memory, so 'Explain this project' can
    later synthesize across decisions instead of re-deriving them from chat."""
    model = f"{d.chosen_provider}/{d.chosen_model}" if d.chosen_model else d.chosen_provider
    losers = [
        (f"{c.provider}/{c.model}" if c.model else c.provider)
        for c in d.candidates
        if (c.provider, c.model) != (d.chosen_provider, d.chosen_model)
    ]
    line = f"Chose {model}"
    if losers:
        line += f" over {', '.join(losers)}"
    if d.rationale.strip():
        line += f" — {d.rationale.strip()}"
    elif d.rationale_tags:
        line += f" — {', '.join(d.rationale_tags)}"
    task = (d.prompt or "").strip().replace("\n", " ")
    if task:
        line += f" (for: {task[:120]})"
    return line


@router.post("/debug/decision")
def debug_decision(req: DecisionRequest):
    """Persist a model-selection decision and mirror it into long-term memory.

    Provenance is inferred (rationale present → 'explicit', else 'derived') and
    carried through to the memory backend's `quality` weight, so trustworthy
    user-stated decisions outrank bare clicks during later retrieval.
    """
    decision_id = model_choices.record(
        prompt=req.prompt,
        chosen_provider=req.chosen_provider,
        chosen_model=req.chosen_model or "",
        system=req.system or "",
        temperature=req.temperature,
        candidates=[c.model_dump() for c in req.candidates],
        rationale=req.rationale,
        rationale_tags=req.rationale_tags,
        project=req.project,
    )
    if decision_id < 0:
        return {"ok": False, "error": "could not persist decision"}

    stored = model_choices.get_by_id(decision_id)
    provenance = stored["provenance"] if stored else "derived"

    # Currency: a revisited choice supersedes the older one rather than competing.
    if req.supersedes:
        model_choices.supersede(req.supersedes, decision_id)

    # Mirror into the embedding memory so it surfaces in project synthesis.
    mirrored = False
    try:
        from memory_core.backend import get_backend
        ok = get_backend().store(
            content=_decision_sentence(req),
            agent_name="prompt_debugger",
            mem_type="decision",
            metadata={
                "kind":            "model_choice",
                "decision_id":     decision_id,
                "provenance":      provenance,
                "chosen_provider": req.chosen_provider,
                "chosen_model":    req.chosen_model or "",
                "project":         req.project,
            },
            quality=model_choices.quality_for(provenance),
        )
        if ok:
            model_choices.mark_mirrored(decision_id)
            mirrored = True
    except Exception as exc:  # memory mirror is best-effort; the record still stands
        print(f"[debug_decision] memory mirror skipped: {exc}")

    return {
        "ok": True,
        "decision_id": decision_id,
        "provenance": provenance,
        "mirrored": mirrored,
        "superseded": req.supersedes,
    }


@router.get("/debug/decisions")
def debug_decisions(limit: int = 50, project: str = "", active_only: bool = False):
    """Recent model decisions + coverage stats (explicit vs derived, active vs stale)."""
    return {
        "decisions": model_choices.recent(limit=limit, project=project, active_only=active_only),
        "coverage":  model_choices.coverage(project=project),
    }
