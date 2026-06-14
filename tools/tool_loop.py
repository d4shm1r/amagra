"""
tools/tool_loop.py — the structured tool loop: action → execute → observe → repeat.

The LLM is *injected* (`invoke` callable), so the loop is provider-agnostic and
fully testable without a model. Protocol: the model either answers directly, or
emits a single fenced JSON block

    ```tool
    {"tool": "read_file", "args": {"path": "main.py"}}
    ```

which we execute and feed back as an observation. Bounded to `max_iters`
tool-calling rounds; on the last round the model is asked to answer outright.
"""

import json
import re

from infrastructure import event_bus
import tools.catalog as catalog

# A fenced block (```tool / ```json / ```) wrapping a JSON object.
_TOOL_BLOCK = re.compile(r"```(?:tool|json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _system_prompt(tools: dict) -> str:
    lines = [
        "You are a tool-using assistant. To call a tool, reply with ONLY a fenced block:",
        "```tool",
        '{"tool": "<name>", "args": { ... }}',
        "```",
        "",
        "Available tools:",
    ]
    for name, t in tools.items():
        lines.append(f"- {name}({', '.join(t['args'])}): {t['desc']}")
    lines.append("")
    lines.append("When you have enough information, reply with a normal answer and NO tool block.")
    return "\n".join(lines)


def extract_call(text: str):
    """Parse a tool call from model output. Returns (name, args) or None."""
    m = _TOOL_BLOCK.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or "tool" not in obj:
        return None
    return str(obj["tool"]), (obj.get("args") if isinstance(obj.get("args"), dict) else {})


def run_tool_loop(invoke, prompt: str, max_iters: int = 3, log: bool = True) -> dict:
    """Drive the model through up to `max_iters` tool calls, then a final answer.

    `invoke(transcript)` takes a list of (role, content) tuples and returns the
    model's text. Returns {answer, iterations, stopped, calls:[{tool,args,ok,...}]}.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt must not be empty")
    tools = catalog.available_tools()
    transcript = [("system", _system_prompt(tools)), ("user", prompt)]
    calls: list[dict] = []

    for i in range(max_iters):
        text = invoke(transcript) or ""
        call = extract_call(text)
        if call is None:
            return {"answer": text, "iterations": i, "stopped": "answer", "calls": calls}

        name, args = call
        try:
            result = catalog.execute(name, args)
            ok = True
        except Exception as e:  # tool errors become observations, never crash the loop
            result = {"error": f"{type(e).__name__}: {e}"}
            ok = False
        calls.append({"tool": name, "args": args, "ok": ok})
        if log:
            try:
                event_bus.emit("tool.call", {"tool": name, "ok": ok, "args": args})
            except Exception:
                pass

        transcript.append(("assistant", text))
        observation = json.dumps(result, default=str)[:2000]
        transcript.append(("user", f"Observation from {name}: {observation}"))

    # Out of tool rounds — force a final answer from the gathered observations.
    transcript.append(("user",
        "Answer the original question using the observations above. Do not call any more tools."))
    final = invoke(transcript) or ""
    return {"answer": final, "iterations": max_iters, "stopped": "max_iters", "calls": calls}
