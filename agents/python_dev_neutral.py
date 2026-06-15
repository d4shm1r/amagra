"""
PROOF-OF-CONCEPT: the python_dev agent converted to the neutral Context/Result
boundary (see core/contract.py).

This runs PARALLEL to agents/python_dev.py — it does not replace it, so the
live coordinator keeps working untouched. It exists to measure the real
conversion diff before committing to convert all 10 agents.

What this file proves:
  • core/contract.py imports ZERO langchain.
  • langchain lives ONLY here, at the extension edge (the _to_lc adapter).
  • the agent is a plain function — no compiled StateGraph subgraph wrapper.
  • the core never sees a BaseMessage; it sees Context in, Result out.
"""
from __future__ import annotations

# LangChain is quarantined to the extension edge. These imports never reach core.
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from core.contract import Context, Result, Msg, trim_history
from memory_core.context import get_memory_context, save_to_memory
from core.user_profile import get_profile_context
# Reuse the unchanged pure tool fn + prompt from the original module —
# the conversion only touches the I/O boundary, not the agent's logic.
from agents.python_dev import PYTHON_SYSTEM_PROMPT, check_python_env


# ── The entire LangChain translation wall: role -> message class ──
_LC = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}


def _to_lc(history: tuple[Msg, ...]) -> list:
    return [_LC[m.role](content=m.content) for m in history]


def main(ctx: Context) -> Result:
    """Python Dev extension — neutral boundary; langchain stays internal."""
    prompt = PYTHON_SYSTEM_PROMPT.format(user_profile=get_profile_context(ctx.task))
    if mem := get_memory_context(ctx.task, "python_dev"):
        prompt += "\n\n" + mem

    messages = [SystemMessage(content=prompt)]
    messages += _to_lc(trim_history(ctx.history, max_messages=10))

    if any(w in ctx.task.lower() for w in ("environment", "packages", "installed", "version")):
        messages.append(HumanMessage(
            content=(
                "Tool results from this system:\n"
                f"[PYTHON ENVIRONMENT]\n{check_python_env()}\n\n"
                "Use these in your response."
            )
        ))

    from tools.agent_runtime import respond_with_optional_tools
    response = respond_with_optional_tools(messages, prompt, ctx.task)
    save_to_memory("python_dev", "code", response.content,
                   {"task": ctx.task[:120] if ctx.task else ""})
    return Result(output=response.content)
