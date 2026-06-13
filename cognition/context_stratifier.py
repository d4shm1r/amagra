"""
context_stratifier.py — Context Stratification (Phase 36)

Solves the state contamination bug where routing decisions are polluted
by dependency outputs and historical context from previous steps.

Root cause:
    When the planner builds sub_tasks like:
        "Set up PostgreSQL\n\nOriginal query: Build FastAPI..."
    the entire string is passed to normalize() and _detect_domains(),
    which sees "router.py", "keyword_map.py", "networking" from prior
    context and selects the wrong agent.

Fix:
    Decompose context into layers with different routing weights:

        primary_task       weight=1.0  (what to do RIGHT NOW)
        dependency_outputs weight=0.3  (what previous steps produced)
        historical_context weight=0.1  (older conversation context)
        world_state        weight=0.2  (project-level facts)

    Routing uses only the weighted primary_task text.
    Execution receives the full structured context.

Usage:
    from cognition.context_stratifier import PromptContext, stratify, routing_text

    ctx = stratify(state, task="Set up PostgreSQL", plan_step=step)
    routing_signal = routing_text(ctx)       # use for normalize()
    execution_prompt = execution_text(ctx)   # inject into agent prompt
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── Routing weights ───────────────────────────────────────────
WEIGHT = {
    "primary_task":        1.0,
    "dependency_outputs":  0.3,
    "historical_context":  0.1,
    "world_state":         0.2,
}


# ── Data model ────────────────────────────────────────────────

@dataclass
class PromptContext:
    """
    A stratified view of the full request context.

    Layers:
      primary_task       — the user's current intent (always present)
      dependency_outputs — outputs from upstream plan steps (optional)
      historical_context — recent interaction summaries (optional)
      world_state        — world_model context summary (optional)
    """
    primary_task:        str
    dependency_outputs:  List[str] = field(default_factory=list)
    historical_context:  List[str] = field(default_factory=list)
    world_state:         str       = ""

    # Metadata
    original_task:       str       = ""  # raw task before extraction
    step_id:             str       = ""
    step_uncertainty:    float     = 0.4


def routing_text(ctx: PromptContext) -> str:
    """
    Return the text to feed into normalize() and _detect_domains().
    Uses ONLY the primary task — contamination-free.
    """
    return ctx.primary_task


def execution_text(ctx: PromptContext) -> str:
    """
    Return the full structured context for injecting into agent prompts.
    This is what agents see — full detail, structured by layer.
    """
    parts = [f"Task: {ctx.primary_task}"]

    if ctx.world_state:
        parts.append(f"\nProject context: {ctx.world_state}")

    if ctx.dependency_outputs:
        dep_section = "\n".join(
            f"  [Step {i+1}]: {o[:300]}"
            for i, o in enumerate(ctx.dependency_outputs)
        )
        parts.append(f"\nPrevious step outputs:\n{dep_section}")

    if ctx.historical_context:
        hist_section = "\n".join(f"  - {h[:150]}" for h in ctx.historical_context[-3:])
        parts.append(f"\nRecent context:\n{hist_section}")

    return "\n".join(parts)


def weighted_text(ctx: PromptContext) -> str:
    """
    Build a text string where each layer contributes proportional to its
    routing weight. Used when a distance metric (rather than pure routing)
    needs to account for multiple layers.

    Repeats the primary_task to give it full weight; truncates other layers.
    """
    tokens = []

    # Primary task at full weight: repeat 3x to dominate signal
    primary_words = ctx.primary_task.split()
    tokens.extend(primary_words * 3)

    # Dependency outputs at 0.3 weight
    if ctx.dependency_outputs:
        dep_words = " ".join(ctx.dependency_outputs).split()
        keep = int(len(dep_words) * WEIGHT["dependency_outputs"])
        tokens.extend(dep_words[:keep])

    # World state at 0.2 weight
    if ctx.world_state:
        ws_words = ctx.world_state.split()
        keep = int(len(ws_words) * WEIGHT["world_state"])
        tokens.extend(ws_words[:keep])

    # Historical context at 0.1 weight (minimal — usually noise for routing)
    if ctx.historical_context:
        hist_words = " ".join(ctx.historical_context[-2:]).split()
        keep = int(len(hist_words) * WEIGHT["historical_context"])
        tokens.extend(hist_words[:keep])

    return " ".join(tokens)


# ── Stratification parser ─────────────────────────────────────

# Markers we inject when building sub_tasks in deep_pipeline
_ORIGINAL_QUERY_RE = re.compile(
    r"\nOriginal query:\s*(.+?)(?:\n|$)", re.IGNORECASE | re.DOTALL
)
_STEP_DESC_RE = re.compile(
    r"^(.+?)(?:\n\nOriginal query:|\Z)", re.DOTALL
)


def stratify(
    state: Dict[str, Any],
    task: str = "",
    plan_step: Any = None,          # PlanStep or None
    world_summary: str = "",
) -> PromptContext:
    """
    Build a PromptContext from raw state + optional plan_step.

    Extraction logic:
      1. If the task contains "Original query:" (deep_pipeline format),
         extract the step description as a dependency output and
         use the original query as the primary_task.
      2. Otherwise, the task IS the primary_task.
      3. Gather historical context from the last N messages in state.
      4. Attach world_state from the cognitive_state or explicit arg.
    """
    raw_task = task or (
        state.get("task") or
        (state["messages"][-1].content if state.get("messages") else "")
    )

    # ── Separate primary_task from dependency context ──────────
    orig_match = _ORIGINAL_QUERY_RE.search(raw_task)
    if orig_match:
        # deep_pipeline format: "{step_description}\n\nOriginal query: {query}"
        primary_task = orig_match.group(1).strip()
        step_desc    = _STEP_DESC_RE.match(raw_task)
        dep_outputs  = [step_desc.group(1).strip()] if step_desc else []
    else:
        primary_task = raw_task.strip()
        dep_outputs  = []

    # ── Historical context from message history ────────────────
    historical: List[str] = []
    messages = state.get("messages", [])
    # Skip the last message (= current query); take up to 4 prior exchanges
    if len(messages) > 1:
        for msg in messages[-5:-1]:
            content = getattr(msg, "content", "") or ""
            if content and len(content.strip()) > 10:
                historical.append(content.strip()[:200])

    # ── World state ────────────────────────────────────────────
    world = world_summary
    if not world:
        try:
            from models.cognitive_state import get_session_state
            cos = get_session_state("cos-session-main")
            if cos.world:
                world = cos.world.context_summary()
        except Exception:
            pass

    step_id          = (plan_step.step_id if plan_step else
                        state.get("step_id", ""))
    step_uncertainty = (plan_step.uncertainty if plan_step else 0.4)

    return PromptContext(
        primary_task       = primary_task,
        dependency_outputs = dep_outputs,
        historical_context = historical,
        world_state        = world,
        original_task      = raw_task,
        step_id            = step_id,
        step_uncertainty   = step_uncertainty,
    )


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, AIMessage

    print("=" * 65)
    print("  context_stratifier — contamination isolation test")
    print("=" * 65)

    # Simulate the contamination scenario
    contaminated_sub_task = (
        "Set up a PostgreSQL database schema\n\n"
        "Original query: Build a FastAPI backend with JWT auth"
    )

    state_with_history = {
        "task":     contaminated_sub_task,
        "messages": [
            HumanMessage(content="How does router.py handle keyword_map networking?"),
            AIMessage(content="The router uses keyword_map.py to detect networking domains via regex patterns..."),
            HumanMessage(content=contaminated_sub_task),
        ],
    }

    ctx = stratify(state_with_history)

    print(f"\n  Raw task (contaminated):")
    print(f"    {contaminated_sub_task!r}")

    print(f"\n  routing_text() — what normalize() sees:")
    print(f"    {routing_text(ctx)!r}")

    print(f"\n  execution_text() — what agents see:")
    for line in execution_text(ctx).splitlines():
        print(f"    {line}")

    print(f"\n  weighted_text() (first 100 chars):")
    print(f"    {weighted_text(ctx)[:100]!r}")

    # Verify contamination is gone from routing signal
    assert "router" not in routing_text(ctx).lower(), "contamination still present in routing signal!"
    assert "networking" not in routing_text(ctx).lower(), "domain contamination in routing signal!"
    assert "FastAPI" in routing_text(ctx) or "JWT" in routing_text(ctx), "primary task missing!"
    print("\n  Contamination isolation: PASS")
    print(f"  primary_task:  {ctx.primary_task!r}")
    print(f"  dep_outputs:   {ctx.dependency_outputs}")
    print(f"  historical:    {len(ctx.historical_context)} items (not used for routing)")
