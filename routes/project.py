"""
routes/project.py — "Explain this project" (Tier 1 project intelligence).

This is the payoff for the debugger→memory bridge: it turns accumulated,
structured decisions into a narrative a new engineer (or your future self) can
read. It is the first feature that makes "accumulated understanding" tangible
rather than a promise.

Two safety lines run through it:

  * Retrieval is always safe; synthesis is gated. Listing the decisions the user
    explicitly recorded is just showing them their own records — it can't lie.
    *Narrating* over them with an LLM is where false confidence enters, so the
    prose summary only runs when evaluation/memory_gate.synthesis_allowed() is
    True (a fresh PASS on the recall benchmark). Until then the endpoint still
    returns the structured decisions, with a note on why the narrative is held.

  * The confidence hierarchy reaches the synthesis. Only active (non-superseded)
    decisions are considered, and explicit (user-stated rationale) decisions are
    presented to the model as established fact while derived (bare-click) ones
    are flagged tentative — so the narrative hedges exactly where the data is weak.
"""

from __future__ import annotations

from fastapi import APIRouter

from decision import model_choices
from evaluation import memory_gate
from infrastructure import provider_config as pc

router = APIRouter()

_SYSTEM = (
    "You brief a new engineer on a project using ONLY the decision records "
    "provided. Do not invent decisions, tools, or reasons that are not listed. "
    "Records marked [confirmed] are user-stated and reliable; records marked "
    "[tentative] are inferred from a bare selection — mention them more cautiously. "
    "Be concise and concrete: what was chosen, and why."
)


def _current_provider_body() -> dict | None:
    """The configured brain provider with its stored key, ready for _build_for."""
    try:
        cur = pc.current()  # {provider, model, base_url, ...} — no secret
        if not cur.get("provider"):
            return None
        body = {"provider": cur["provider"], "model": cur.get("model"),
                "base_url": cur.get("base_url")}
        stored = pc.load()
        if stored.get("api_key"):
            body["api_key"] = stored["api_key"]
        return body
    except Exception:
        return None


def _decision_line(d: dict) -> str:
    model = f"{d['chosen_provider']}/{d['chosen_model']}" if d.get("chosen_model") else d["chosen_provider"]
    tag = "[confirmed]" if d["provenance"] == "explicit" else "[tentative]"
    why = d.get("rationale") or ", ".join(d.get("rationale_tags") or []) or "no reason recorded"
    task = (d.get("prompt") or "").strip().replace("\n", " ")[:100]
    line = f"{tag} chose {model} — {why}"
    if task:
        line += f" (task: {task})"
    return line


def _synthesize(decisions: list[dict]) -> tuple[str | None, str | None]:
    """Generate the narrative. Returns (summary, error_note)."""
    body = _current_provider_body()
    if body is None:
        return None, "no model provider configured for synthesis"
    facts = "\n".join(f"- {_decision_line(d)}" for d in decisions)
    prompt = (
        "Decision records for this project:\n"
        f"{facts}\n\n"
        "Write a short briefing (a few sentences) explaining the model and "
        "tooling choices this project has made and the reasoning behind them. "
        "Group related choices. Do not list every record verbatim."
    )
    try:
        out = _build_provider(body).generate(prompt, system_prompt=_SYSTEM, temperature=0.2)
        return (out.strip() or None), None
    except Exception as exc:
        return None, f"synthesis failed: {exc}"


def _build_provider(body: dict):
    # Imported lazily so the route module stays importable without provider deps.
    from routes.settings_provider import _build_for
    return _build_for(body)


@router.get("/project/explain")
def explain_project(project: str = "", limit: int = 100):
    """Explain a project from its accumulated decision memory.

    Always returns the structured (active) decisions; adds an LLM narrative only
    when the memory-recall gate permits synthesis.
    """
    decisions = model_choices.recent(limit=limit, project=project, active_only=True)
    explicit = [d for d in decisions if d["provenance"] == "explicit"]
    derived  = [d for d in decisions if d["provenance"] != "explicit"]

    gate = memory_gate.status()
    summary: str | None = None
    summary_note: str | None = None

    if not decisions:
        summary_note = "no decisions recorded yet for this project — capture some in the prompt debugger"
    elif not gate["allowed"]:
        # Honest degradation: show the records, withhold the narrative.
        summary_note = f"synthesis withheld — {gate['reason']}. Run `make benchmark-memory`."
    else:
        # Prefer confirmed decisions for the narrative; fall back to all active.
        summary, summary_note = _synthesize(explicit or decisions)

    return {
        "project":           project or "(all)",
        "synthesis_allowed": gate["allowed"],
        "gate":              gate,
        "summary":           summary,
        "summary_note":      summary_note,
        "decisions":         decisions,
        "counts": {
            "active":   len(decisions),
            "confirmed": len(explicit),
            "tentative": len(derived),
        },
        "coverage":          model_choices.coverage(project=project),
    }
