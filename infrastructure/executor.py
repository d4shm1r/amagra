# ~/agentic-ai/executor.py
# ─────────────────────────────────────────────────────────────
# Sequential task graph executor.
#
# Execution model:
#   Find next ready step (pending, all deps completed)
#   → build prompt (inject previous step outputs)
#   → run assigned agent via coordinator
#   → verify output (basic: non-empty, non-error)
#   → mark completed / failed
#   → repeat until no more steps or a step fails
#
# Runs inside asyncio via to_thread() — does not block FastAPI.
# One graph executes at a time per graph_id (idempotent lock).
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import sys
import time

import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.task_graph import (
    get_graph, next_pending_step,
    mark_step_running, mark_step_completed, mark_step_failed,
    update_graph_status, is_graph_complete, has_failed_step,
)


def _classify_failure(reason: str) -> str:
    """Map a verification/exception message to a structured failure_type."""
    r = reason.lower()
    if "empty response"          in r: return "empty_response"
    if "too short"               in r: return "trivial_response"
    if "failure phrase"          in r: return "refusal"
    if "no code block"           in r: return "code_missing"
    if "timed out"               in r: return "timeout"
    if "dependency"              in r: return "dependency_error"
    if "coordinator"             in r: return "agent_error"
    return "agent_error"

_running: set = set()          # graph_ids currently executing
_lock    = asyncio.Lock()      # guards _running set


# ── Verification ─────────────────────────────────────────────

def _verify(step: dict, response: str) -> tuple[bool, str]:
    """
    Basic verification: structural checks on the agent response.

    Returns (passed: bool, reason: str).
    Verification is intentionally lenient — it catches failures,
    not quality. Quality is handled by reflection.
    """
    if not response or not response.strip():
        return False, "empty response"

    words = response.split()
    # Terse agent responses are intentionally short (1-6 words is correct).
    # Apply a reduced threshold when the step was routed to the terse agent.
    min_words = 1 if step.get("agent") == "terse" else 8
    if len(words) < min_words:
        return False, f"response too short ({len(words)} words)"

    # Explicit failure markers
    failure_phrases = [
        "i cannot", "i can't", "i am unable", "i'm unable",
        "i don't know how", "i don't have", "error occurred",
        "i apologize, but i cannot",
    ]
    low = response.lower()
    for phrase in failure_phrases:
        if low.startswith(phrase):
            return False, f"response starts with failure phrase: '{phrase}'"

    # Code steps: if prompt asks for implementation/writing, expect a code block
    prompt_lower = step.get("prompt", "").lower()
    if any(w in prompt_lower for w in ["implement", "write code", "create function", "build"]):
        if "```" not in response and "def " not in response and "class " not in response:
            return False, "prompt requested code but no code block found"

    return True, "ok"


# ── Prompt builder ────────────────────────────────────────────

def _build_prompt(goal: str, step: dict, previous_outputs: dict) -> str:
    """
    Build the full prompt for a step by injecting previous step outputs.

    previous_outputs: {step_id: response_text}
    """
    parts = [f"Goal: {goal}", ""]

    deps = step.get("depends_on", [])
    if deps and previous_outputs:
        parts.append("Context from previous steps:")
        for dep_id in deps:
            if dep_id in previous_outputs:
                dep_out = previous_outputs[dep_id][:1200]  # cap context length
                parts.append(f"\n[{dep_id}]\n{dep_out}")
        parts.append("")

    parts.append(f"Current task: {step['prompt']}")
    return "\n".join(parts)


# ── Step runner ───────────────────────────────────────────────

def _run_step_sync(goal: str, step: dict, previous_outputs: dict) -> str:
    """
    Run a single step synchronously via the coordinator.
    Returns the agent's response text.
    Raises on coordinator failure.
    """
    from orchestration.coordinator import coordinator
    from langchain_core.messages import HumanMessage

    prompt = _build_prompt(goal, step, previous_outputs)
    agent  = step["agent"]

    state = {
        "messages":       [HumanMessage(content=prompt)],
        "active_agent":   "",
        "task":           prompt,
        "result":         "",
        "next_agent":     "",
        "memory":         {},
        "force_agent":    agent,
        "brain_decision": {},
        "reflect":        False,
        "reflect_type":   "general",
    }

    result = coordinator.invoke(state)

    if "messages" in result and result["messages"]:
        return result["messages"][-1].content
    if "result" in result and result["result"]:
        return result["result"]
    raise ValueError("coordinator returned no content")


# ── Main executor ─────────────────────────────────────────────

async def execute_graph(graph_id: int) -> None:
    """
    Execute a task graph sequentially.
    Safe to call multiple times — will return immediately if already running.
    """
    async with _lock:
        if graph_id in _running:
            print(f"[executor] graph {graph_id} already running — skipping")
            return
        _running.add(graph_id)

    try:
        graph = get_graph(graph_id)
        if not graph:
            print(f"[executor] graph {graph_id} not found")
            return

        if graph["status"] in ("completed", "failed"):
            print(f"[executor] graph {graph_id} already {graph['status']}")
            return

        update_graph_status(graph_id, "running")
        print(f"[executor] starting graph {graph_id}: {graph['goal'][:60]}")

        # Collect outputs keyed by step_id
        previous_outputs: dict = {}

        # Hydrate any already-completed steps
        for s in graph["steps"]:
            if s["status"] == "completed" and s["output_data"].get("response"):
                previous_outputs[s["step_id"]] = s["output_data"]["response"]

        while True:
            step = next_pending_step(graph_id)
            if not step:
                break

            step_id = step["step_id"]
            agent   = step["agent"]
            print(f"[executor] step '{step_id}' → [{agent}]")

            mark_step_running(graph_id, step_id, input_data={
                "previous_steps": list(previous_outputs.keys())
            })

            try:
                t0       = time.time()
                response = await asyncio.to_thread(
                    _run_step_sync, graph["goal"], step, previous_outputs
                )
                duration = int((time.time() - t0) * 1000)

                passed, reason = _verify(step, response)

                if passed:
                    mark_step_completed(graph_id, step_id, output_data={
                        "response":    response,
                        "duration_ms": duration,
                    })
                    previous_outputs[step_id] = response
                    print(f"[executor] step '{step_id}' completed ({duration}ms)")
                else:
                    ftype = _classify_failure(reason)
                    mark_step_failed(graph_id, step_id,
                                     error=f"verification failed: {reason}",
                                     failure_type=ftype)
                    print(f"[executor] step '{step_id}' failed [{ftype}]: {reason}")
                    update_graph_status(graph_id, "failed")
                    return

            except Exception as e:
                ftype = _classify_failure(str(e))
                mark_step_failed(graph_id, step_id, error=str(e)[:500],
                                 failure_type=ftype)
                print(f"[executor] step '{step_id}' raised [{ftype}]: {e}")
                update_graph_status(graph_id, "failed")
                return

        # All steps processed — determine final status
        if is_graph_complete(graph_id):
            update_graph_status(graph_id, "completed")
            print(f"[executor] graph {graph_id} completed")
        elif has_failed_step(graph_id):
            update_graph_status(graph_id, "failed")
            print(f"[executor] graph {graph_id} failed")
        else:
            update_graph_status(graph_id, "paused")
            print(f"[executor] graph {graph_id} paused — no ready steps")

    finally:
        async with _lock:
            _running.discard(graph_id)
