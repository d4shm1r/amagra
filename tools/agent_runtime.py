"""
tools/agent_runtime.py — opt-in bridge from a specialist agent to the tool loop.

Wires the bounded tool loop (tools/tool_loop.py) and the jailed workspace tool
(tools/workspace.py, via tools/catalog.py) into the default agent reasoning path
(GitHub issues #8 and #5). Gated behind config because phi4-mini's reliability at
emitting fenced tool JSON is unproven — when disabled, agents behave exactly as
before (a single llm.invoke).

Enable with:
    AMAGRA_AGENT_TOOLS=1

Even when enabled the loop only engages if at least one tool is actually
available (the workspace read tools always are; sandbox/web are separately
gated). Any failure falls back to a plain llm.invoke so a tool hiccup never
costs the user a response.

Exact-computation queries (#184's `compute` answer_shape) are additionally
steered toward the run_python sandbox tool via a directive preamble (#186), so
"compute the first 12 terms" is executed rather than free-handed — but only
when run_python is actually available, otherwise the preamble is untouched.
"""

import os

import tools.catalog as catalog
import tools.tool_loop as tool_loop

# Match routes/tools.py: keep the in-agent loop short so a misbehaving model
# can't spin. The default agent path is latency-sensitive.
DEFAULT_AGENT_TOOL_ITERS = 3


def agent_tools_enabled() -> bool:
    """True when the in-agent tool loop is switched on via config."""
    return os.environ.get("AMAGRA_AGENT_TOOLS", "0") == "1"


# Steer exact-computation queries (#184's `compute` shape) toward the sandbox
# instead of letting a small model free-hand a number/sequence/proof. This is
# the execution end of the chain #184→#185→#186: #185 votes on scalar answers
# it can validate; enumerations and proofs (vector/derivation answers) need a
# real interpreter, which is what run_python provides.
_COMPUTE_DIRECTIVE = (
    "This request needs an EXACT computed result — a number, a full sequence, "
    "or a proof — not a description of how to compute it. Use the run_python "
    "tool to compute the answer and read its real output; do not hand-calculate "
    "or guess. For an enumeration (\"the first N …\"), list every term straight "
    "from the program's output."
)


def _augment_for_compute(task: str, system_prompt: str, available: dict) -> str:
    """
    Prepend the compute directive when the query wants an exact computed result
    AND run_python is actually available.

    Guarded on run_python because without a sandbox the directive would order the
    model to use a tool it can't call — a dead instruction. When it's absent the
    preamble is returned untouched, so a compute query with the sandbox off
    behaves exactly like any other tool turn (no regression). The persona still
    leads the system message; the directive follows it, ahead of the tool
    protocol.
    """
    if "run_python" not in available:
        return system_prompt
    try:
        from orchestration.query_normalizer import detect_answer_shape
        if detect_answer_shape(task) != "compute":
            return system_prompt
    except Exception:
        return system_prompt
    return (f"{system_prompt}\n\n{_COMPUTE_DIRECTIVE}"
            if system_prompt else _COMPUTE_DIRECTIVE)


def _llm_invoke(transcript):
    """Adapt a (role, content) transcript to the LangChain LLM and return text.

    Mirrors routes/tools._llm_invoke; module-level so tests can monkeypatch it.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from models.llm import llm

    role_cls = {"system": SystemMessage, "assistant": AIMessage, "user": HumanMessage}
    msgs = [role_cls.get(role, HumanMessage)(content=content) for role, content in transcript]
    resp = llm.invoke(msgs)
    return getattr(resp, "content", str(resp))


def run_with_tools(system_prompt: str, task: str, *,
                   max_iters: int = DEFAULT_AGENT_TOOL_ITERS, invoke=None) -> str | None:
    """
    Drive the tool loop for one agent turn, returning the final answer text.

    Returns None — meaning "caller should fall back to a normal llm.invoke" —
    when the feature is disabled, no tools are available, the task is empty, or
    anything in the loop raises.
    """
    if not agent_tools_enabled():
        return None
    if not task or not task.strip():
        return None
    available = catalog.available_tools()
    if not available:
        return None
    inv = invoke or _llm_invoke
    preamble = _augment_for_compute(task, system_prompt, available)
    try:
        result = tool_loop.run_tool_loop(
            inv, task, max_iters=max_iters, system_preamble=preamble,
        )
        answer = result.get("answer")
        return answer if (answer and answer.strip()) else None
    except Exception as e:
        print(f"[agent_runtime] tool loop failed, falling back to plain invoke: {e}")
        return None


def respond_with_optional_tools(messages, system_prompt: str, task: str, *,
                                max_iters: int = DEFAULT_AGENT_TOOL_ITERS):
    """
    Single entry point an agent node uses in place of `llm.invoke(messages)`.

    When the tool loop is enabled and produces an answer, returns it wrapped in an
    AIMessage (so the caller's `.content` access is unchanged). Otherwise falls
    back to the plain `llm.invoke(messages)` path, preserving the agent's full
    message history.
    """
    answer = run_with_tools(system_prompt, task, max_iters=max_iters)
    if answer is not None:
        from langchain_core.messages import AIMessage
        return AIMessage(content=answer)
    from models.llm import llm
    return llm.invoke(messages)
