"""
routes/consensus.py — POST /consensus

Run one prompt across N models (reusing the cross-model debugger's concurrent
fan-out), then measure how much they *agree* and, optionally, synthesize a single
consensus answer through a neutral judge.

This is the debugger's divergence view turned into a **trust** feature: the
response is "consensus: …" or "models disagree — here's where", with the full
agreement matrix attached so the verdict stays inspectable, never a black box.

  POST /consensus   { prompt, system?, temperature?, models?, synthesize? }

Auth: like /debug/prompt — an owner action that makes outbound model calls
(possibly with the stored key), so it is NOT in api.py `_PUBLIC_PATHS`.
"""
from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core import consensus as cc
from routes.debug_prompt import DebugResult, _resolve_models, _run_one
from routes.settings_provider import LLMConfig, _build_for

router = APIRouter()

_JUDGE_SYSTEM = (
    "You are a neutral adjudicator. You are given several independent answers to "
    "the same question. Produce a single best consensus answer that reflects what "
    "the answers agree on, then briefly note any meaningful disagreement. Do not "
    "introduce facts that none of the answers contain."
)


class ConsensusRequest(BaseModel):
    prompt: str
    system: str | None = None
    temperature: float = 0.2
    # Empty = run against the single configured brain provider (zero-setup path).
    models: list[LLMConfig] = Field(default_factory=list)
    # Also merge the answers into one consensus answer via a neutral judge.
    synthesize: bool = True


class CandidateOut(DebugResult):
    # Mean cosine similarity of this answer to the OTHER answers (None if it
    # failed/was empty or analysis was unavailable).
    agreement: float | None = None


class ConsensusResponse(BaseModel):
    candidates: list[CandidateOut]
    n_ok: int
    verdict: str  # consensus | partial | divergent | single | error
    agreement_score: float | None = None
    summary: str | None = None
    matrix: list = Field(default_factory=list)
    representative_index: int | None = None
    dissenters: list[int] = Field(default_factory=list)
    consensus_answer: str | None = None
    contradiction_note: str | None = None
    synthesized_by: str | None = None
    note: str | None = None  # graceful-degradation explanation


def _judge_prompt(prompt: str, answers: list[str]) -> str:
    blocks = "\n\n".join(f"[Answer {i + 1}]\n{a}" for i, a in enumerate(answers))
    return (
        f"Question:\n{prompt}\n\n"
        f"Independent answers:\n{blocks}\n\n"
        "Respond in exactly two sections:\n"
        "CONSENSUS:\n<the merged best answer>\n\n"
        "DISAGREEMENT:\n<one or two sentences on where they differ, or 'None.'>"
    )


def _split_judgment(text: str) -> tuple[str, str | None]:
    """Parse the two-section judge reply; tolerant of formatting drift."""
    m = re.search(
        r"CONSENSUS:\s*(.*?)(?:\n\s*DISAGREEMENT:\s*(.*))?$", text, re.S | re.I
    )
    if not m:
        return text.strip(), None
    cons = (m.group(1) or "").strip() or text.strip()
    dis = (m.group(2) or "").strip() or None
    if dis and dis.lower().rstrip(".") == "none":
        dis = None
    return cons, dis


@router.post("/consensus", response_model=ConsensusResponse)
async def consensus(req: ConsensusRequest):
    bodies = _resolve_models(req.models)
    results = list(await asyncio.gather(
        *(asyncio.to_thread(_run_one, b, req.prompt, req.system, req.temperature)
          for b in bodies)
    ))
    texts = [r.output or "" for r in results]
    ok_idx = [i for i, r in enumerate(results) if r.error is None and (r.output or "").strip()]

    # Accountable core: agreement analysis over the successful answers. If the
    # embedder (Ollama) is down, degrade to the side-by-side answers only.
    analysis = None
    note = None
    try:
        from memory_core.db import get_embedding
        analysis = cc.analyze(texts, embed_fn=get_embedding)
    except Exception as exc:  # pragma: no cover - exercised via route test mock
        note = f"agreement analysis unavailable ({exc}); showing answers only"

    per = (analysis or {}).get("per_candidate") or [None] * len(results)
    cands = [
        CandidateOut(**r.model_dump(), agreement=(per[i] if i < len(per) else None))
        for i, r in enumerate(results)
    ]

    if analysis is None:
        return ConsensusResponse(candidates=cands, n_ok=len(ok_idx), verdict="error", note=note)

    # Optional synthesis via a neutral judge (the configured brain provider).
    # Best-effort: the verdict and matrix stand even if this is skipped.
    consensus_answer = contradiction = synthesized_by = None
    if req.synthesize and len(ok_idx) >= 2:
        try:
            answers = [texts[i] for i in ok_idx]
            judge_body = _resolve_models([])[0]  # configured brain = neutral judge
            judge = _build_for(judge_body)
            raw = await asyncio.to_thread(
                judge.generate, _judge_prompt(req.prompt, answers),
                system_prompt=_JUDGE_SYSTEM, temperature=0.1,
            )
            consensus_answer, contradiction = _split_judgment(raw)
            synthesized_by = (
                f"{judge_body['provider']}/{judge_body.get('model')}"
                if judge_body.get("model") else judge_body["provider"]
            )
        except Exception as exc:
            note = (note + "; " if note else "") + f"synthesis skipped ({exc})"

    return ConsensusResponse(
        candidates=cands,
        n_ok=len(ok_idx),
        verdict=analysis["verdict"],
        agreement_score=analysis["agreement_score"],
        summary=cc.summarize(analysis),
        matrix=analysis["matrix"],
        representative_index=analysis["representative_index"],
        dissenters=analysis["dissenters"],
        consensus_answer=consensus_answer,
        contradiction_note=contradiction,
        synthesized_by=synthesized_by,
        note=note,
    )
