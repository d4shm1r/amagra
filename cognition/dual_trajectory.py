"""
Dual-trajectory evaluation (GRAM-light) for code/debug agent tasks.

For python_dev and dotnet_dev on code or debug tasks:
  A: standard agent invocation (full pipeline with memory + tools)
  B: second LLM call with a CoT-augmented system prompt (lightweight, no tools)
  Critic: single short LLM call that picks A or B with a one-line reason

Only fires when answer_shape is "code" or "debug" (from QuerySignal).
Pass-through for all other tasks — zero overhead.
"""

import time
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from orchestration.query_normalizer import normalize

_CODE_SHAPES = {"code", "debug"}

# Added to system prompt for candidate B to nudge step-by-step reasoning.
_COT_SUFFIX = (
    "\n\nApproach: identify the key constraint first, then write the "
    "cleanest solution step by step."
)


def is_code_task(task: str) -> bool:
    """True when the task expects a code or debug response."""
    return normalize(task).answer_shape in _CODE_SHAPES


def _candidate_b(task: str, system_prompt: str, state_messages: list) -> str:
    """
    Lightweight second LLM call with CoT framing.
    No memory lookup, no tool calls — just the LLM.
    Returns empty string on failure.
    """
    from models.llm import llm

    user_msgs = [m for m in state_messages if not isinstance(m, SystemMessage)]
    messages = [
        SystemMessage(content=system_prompt + _COT_SUFFIX),
        *user_msgs[-4:],
    ]
    try:
        return llm.invoke(messages).content
    except Exception as e:
        print(f"[dual_traj] candidate B failed: {e}")
        return ""


def _critic_pick(task: str, a: str, b: str) -> tuple[str, str]:
    """
    Compare two code responses; return (winner_text, log_line).
    Critic prompt is intentionally short so it fits within num_predict=256.
    """
    from models.llm import llm

    prompt = (
        f"Task: {task[:80]}\n\n"
        f"[A]\n{a[:350]}\n\n"
        f"[B]\n{b[:350]}\n\n"
        "Which is better? Reply: 'A' or 'B' then one short reason."
    )
    try:
        text = llm.invoke([HumanMessage(content=prompt)]).content.strip()
        choice = "B" if text.upper().startswith("B") else "A"
        winner = b if choice == "B" else a
        return winner, f"[dual-traj chose {choice}] {text[:100]}"
    except Exception as e:
        print(f"[dual_traj] critic failed: {e}")
        return a, "[dual-traj critic failed — kept A]"


def dual_trajectory_invoke(invoke_fn, state: dict, system_prompt: str,
                           force: bool = False) -> dict:
    """
    Wrap an agent's invoke() with dual-trajectory selection.

    Args:
        invoke_fn     — the agent's .invoke method
        state         — current LangGraph state
        system_prompt — agent's base system prompt (used to build candidate B)
        force         — bypass the is_code_task gate (used when agent confidence is low)

    Returns the normal result dict, potentially with messages/result replaced
    by the critic-chosen winner.
    """
    task = state.get("task", "") or (
        state["messages"][-1].content if state.get("messages") else ""
    )

    # Gate: pass-through for non-code tasks unless forced by confidence signal
    if not force and not is_code_task(task):
        return invoke_fn(state)

    t0 = time.time()

    # Candidate A — full agent pipeline
    result_a = invoke_fn(state)
    response_a = ""
    if result_a.get("messages"):
        response_a = result_a["messages"][-1].content
    if not response_a and result_a.get("result"):
        response_a = result_a["result"]
    if not response_a:
        return result_a

    # Candidate B — lightweight CoT call
    response_b = _candidate_b(task, system_prompt, state.get("messages", []))
    if not response_b:
        return result_a

    # Critic — pick winner
    winner_text, log = _critic_pick(task, response_a, response_b)
    elapsed = round(time.time() - t0, 2)
    print(f"[dual_traj] {log} ({elapsed}s total for A+B+critic)")

    # A wins — return unmodified, but annotate with GRAM metadata
    if winner_text is response_a or winner_text == response_a:
        return {**result_a, "gram_winner": "A", "gram_log": log}

    # B wins — splice winner into result
    return {
        **result_a,
        "messages": [*result_a.get("messages", [])[:-1], AIMessage(content=winner_text)],
        "result":   winner_text,
        "gram_winner": "B",
        "gram_log":    log,
    }
