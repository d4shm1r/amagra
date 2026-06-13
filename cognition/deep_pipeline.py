"""
Phase 28 — Deep Pipeline v1

Handles compound queries by fanning out to multiple agents and
synthesizing a unified response.

Current architecture gap:
  core_brain can detect compound queries and returns agent_strategy=[A, B],
  but coordinator only executes agent_strategy[0]. Multi-domain questions
  get half an answer.

What this module adds:
  1. decompose(query, agents) — splits the query into per-agent sub-tasks
  2. fan_out(sub_tasks, state, agent_runners) — runs each sub-task through
     its designated agent and collects responses
  3. synthesize(query, agent_responses) — merges responses into a coherent
     unified answer with per-agent sections

Integration point (coordinator.py):
  When brain_decision.complexity == "compound" and len(agent_strategy) > 1,
  call run_deep_pipeline() instead of routing to a single agent node.

Design choices:
  - Decomposition is rule-based (no LLM call): each agent gets the full
    query but with a scoped system prompt that focuses it on its domain.
    This is v1 — a full LLM decomposer would be v2.
  - Synthesis is structural: each response becomes a named section.
    A clean concatenation is better than an unreliable LLM merge on phi4-mini.
  - Each agent still runs through _run_with_reflection in coordinator.py,
    so learning and episodic memory work unchanged.
"""

import sys
import time
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage

# ── Agent display names ───────────────────────────────────────
_AGENT_LABELS = {
    "python_dev":        "Python",
    "dotnet_dev":        "Blazor / .NET",
    "it_networking":     "Networking",
    "ai_ml":             "AI / ML",
    "knowledge_learning":"General",
    "terse":             "Quick Answer",
}

# ── Domain focus hints injected into each sub-task ───────────
# Appended to the sub-query so the agent knows what aspect to cover.
_DOMAIN_HINTS = {
    "python_dev":        "Focus on the Python/backend aspects of this request.",
    "dotnet_dev":        "Focus on the Blazor/.NET/C# aspects of this request.",
    "it_networking":     "Focus on the networking/infrastructure aspects of this request.",
    "ai_ml":             "Focus on the AI/ML aspects of this request.",
    "knowledge_learning":"Provide a general conceptual overview.",
    "terse":             "Give a brief, direct answer.",
}


def decompose(query: str, agents: list[str]) -> list[dict]:
    """
    Split a compound query into per-agent sub-tasks.

    v1 strategy: each agent receives the full original query plus a
    domain-scoping hint. This is intentionally simple — a dedicated
    LLM decomposer would produce cleaner sub-tasks but at ~15s extra cost.

    Returns list of {"agent": str, "sub_task": str}.
    """
    sub_tasks = []
    for agent in agents:
        hint = _DOMAIN_HINTS.get(agent, "")
        sub_task = f"{query}\n\n[{hint}]" if hint else query
        sub_tasks.append({"agent": agent, "sub_task": sub_task})
    return sub_tasks


def synthesize(original_query: str, agent_responses: list[dict]) -> str:
    """
    Merge per-agent responses into a single structured answer.

    Format:
      ## Overview
      (brief intro sentence — generated locally, no LLM)

      ## [Agent Label] — [Domain]
      <agent response>

      ---
      ## [Agent Label] — [Domain]
      <agent response>

    The caller receives this as the final message content.
    """
    if not agent_responses:
        return "No agent responses received."

    if len(agent_responses) == 1:
        return agent_responses[0]["response"]

    sections = []
    for r in agent_responses:
        agent   = r["agent"]
        label   = _AGENT_LABELS.get(agent, agent.replace("_", " ").title())
        content = r["response"].strip()
        sections.append(f"## {label}\n\n{content}")

    body = "\n\n---\n\n".join(sections)
    agents_used = " + ".join(
        _AGENT_LABELS.get(r["agent"], r["agent"]) for r in agent_responses
    )
    header = f"*Multi-agent response ({agents_used})*\n\n"
    return header + body


def run_deep_pipeline(
    query: str,
    agents: list[str],
    state: dict,
    agent_runner_map: dict,   # {"agent_name": run_fn}
    action: str = "unknown",
    complexity: str = "compound",
) -> dict:
    """
    Execute a compound query through multiple agents and return a merged result.

    Uses planner.plan_query() (Phase 33) to decompose the query into
    dependency-ordered steps before execution. Falls back to the legacy
    rule-based decompose() if the planner import fails.

    agent_runner_map must map agent names to their wrapper functions.

    Returns a dict compatible with coordinator result expectations:
      {"messages": [...], "result": str, "pipeline_agents": [...],
       "pipeline_responses": [...], "plan_summary": str}
    """
    # ── Phase 33: planner-based decomposition ─────────────────
    plan      = None
    sub_tasks = []
    try:
        from orchestration.planner import plan_query
        # Use stratifier to isolate routing text from any "Original query:" composite strings
        routing_query = query
        try:
            from cognition.context_stratifier import stratify, routing_text
            ctx = stratify({}, query)
            routing_query = routing_text(ctx) or query
        except Exception:
            pass
        plan = plan_query(routing_query, action=action, agents=agents, complexity=complexity)
        # Convert PlanStep list to the sub_task dict format, respecting order
        for step in plan.ordered_steps():
            runner_agent = step.agent
            # Fall back to first available runner if assigned agent has no runner
            if runner_agent not in agent_runner_map:
                runner_agent = next(
                    (a for a in agents if a in agent_runner_map), None
                )
            if runner_agent:
                sub_tasks.append({
                    "agent":    runner_agent,
                    "sub_task": f"{step.description}\n\nOriginal query: {query}",
                    "step_id":  step.step_id,
                    "uncertainty": step.uncertainty,
                })
        print(f"[deep_pipeline] planner ({plan.mode}): "
              f"{len(plan.steps)} steps, u={plan.uncertainty:.2f}, "
              f"{plan.elapsed_ms:.0f}ms")
    except Exception as e:
        print(f"[deep_pipeline] planner unavailable ({e}) — using legacy decompose()")

    # ── Legacy fallback ───────────────────────────────────────
    if not sub_tasks:
        sub_tasks = [
            {**t, "step_id": f"step_{i+1}", "uncertainty": 0.4}
            for i, t in enumerate(decompose(query, agents))
        ]
    agent_responses  = []
    all_messages     = []
    aborted          = False
    abort_reason     = ""

    # Build a step index for verification (keyed by step_id)
    step_index = {}
    if plan:
        step_index = {s.step_id: s for s in plan.steps}

    for sub in sub_tasks:
        if aborted:
            break

        agent    = sub["agent"]
        sub_task = sub["sub_task"]
        runner   = agent_runner_map.get(agent)

        if runner is None:
            print(f"[deep_pipeline] no runner for {agent} — skipping")
            continue

        sub_state = {
            **state,
            "task":         sub_task,
            "next_agent":   agent,
            "active_agent": agent,
            "messages":     [HumanMessage(content=sub_task)],
        }

        step_id     = sub.get("step_id", "?")
        uncertainty = sub.get("uncertainty", 0.4)
        plan_step   = step_index.get(step_id)
        retries     = 1   # one retry per step

        if plan_step is not None:
            plan_step.status = "running"

        for attempt in range(2):    # attempt 0 = first try, attempt 1 = retry
            t0 = time.time()
            try:
                print(f"[deep_pipeline] {step_id} [{agent}] u={uncertainty:.2f} "
                      f"attempt={attempt+1}...")
                result   = runner(sub_state)
                elapsed  = round((time.time() - t0) * 1000)
                response = result["messages"][-1].content if result.get("messages") else ""
                print(f"[deep_pipeline] {step_id} done in {elapsed}ms "
                      f"({len(response)} chars)")
                if plan_step is not None:
                    plan_step.elapsed_ms = elapsed
            except Exception as e:
                elapsed = round((time.time() - t0) * 1000)
                print(f"[deep_pipeline] {step_id} [{agent}] failed: {e}")
                response = f"[{agent} error: {e}]"
                if plan_step is not None:
                    plan_step.status         = "failed"
                    plan_step.result_snippet = str(e)[:120]
                    plan_step.elapsed_ms     = elapsed

            # ── Step verification ─────────────────────────────
            if plan_step is not None:
                try:
                    from cognition.step_verifier import verify_step
                    retries_left = retries - attempt
                    v = verify_step(plan_step, response,
                                    retries_remaining=retries_left)
                    print(f"[step_verifier] {v}")

                    if v.recommendation == "abort":
                        aborted      = True
                        abort_reason = f"{step_id} aborted: {'; '.join(v.issues)}"
                        plan_step.status         = "failed"
                        plan_step.result_snippet = f"abort: {'; '.join(v.issues)}"[:120]
                        agent_responses.append({
                            "agent":          agent,
                            "step_id":        step_id,
                            "uncertainty":    0.95,
                            "response":       response,
                            "verify_passed":  False,
                            "verify_score":   v.raw_score,
                            "recommendation": "abort",
                        })
                        break
                    elif v.recommendation == "retry" and attempt == 0:
                        print(f"[deep_pipeline] {step_id} retry triggered "
                              f"(score={v.raw_score:.3f} < thresh={v.threshold:.3f})")
                        continue   # re-run the step

                    # continue or replan — commit this response and move on
                    plan_step.status         = "completed" if v.passed else "failed"
                    plan_step.result_snippet = f"{v.recommendation} score={v.raw_score:.2f}"
                    agent_responses.append({
                        "agent":          agent,
                        "step_id":        step_id,
                        "uncertainty":    uncertainty,
                        "response":       response,
                        "verify_passed":  v.passed,
                        "verify_score":   v.raw_score,
                        "recommendation": v.recommendation,
                    })
                    all_messages.extend(result.get("messages", []))
                    break

                except Exception as e:
                    print(f"[step_verifier] verification error: {e}")
                    plan_step.status         = "completed"
                    plan_step.result_snippet = "verify unavailable"

            # No plan_step or verification unavailable — commit as-is
            agent_responses.append({
                "agent":       agent,
                "step_id":     step_id,
                "uncertainty": uncertainty,
                "response":    response,
            })
            all_messages.extend(result.get("messages", []))
            break   # no retry logic without a plan_step

    if aborted:
        print(f"[deep_pipeline] aborted: {abort_reason}")

    if not agent_responses:
        fallback = "[deep_pipeline] all agents failed — no response generated"
        return {
            "messages": [HumanMessage(content=query), AIMessage(content=fallback)],
            "result": fallback,
            "pipeline_agents": agents,
            "pipeline_responses": [],
        }

    merged = synthesize(query, agent_responses)

    # Propagated uncertainty: mean of completed steps (failed steps inflate it)
    mean_u = (
        sum(r["uncertainty"] for r in agent_responses) / len(agent_responses)
        if agent_responses else 0.5
    )

    return {
        "messages":            [HumanMessage(content=query), AIMessage(content=merged)],
        "result":              merged,
        "pipeline_agents":     [r["agent"]   for r in agent_responses],
        "pipeline_responses":  [
            {"agent": r["agent"], "step_id": r.get("step_id"), "length": len(r["response"])}
            for r in agent_responses
        ],
        "plan_summary":        plan.summary() if plan else "",
        "pipeline_uncertainty": round(mean_u, 3),
        "pipeline_aborted":    aborted,
        "abort_reason":        abort_reason,
        "plan":                plan,
    }


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    print("deep_pipeline.py — decomposition + synthesis test (no LLM needed)\n")

    query  = "Set up a FastAPI backend that serves data for a Blazor WASM frontend"
    agents = ["python_dev", "dotnet_dev"]

    print(f"Query: {query!r}")
    print(f"Agents: {agents}\n")

    sub_tasks = decompose(query, agents)
    print("Decomposed sub-tasks:")
    for st in sub_tasks:
        print(f"  [{st['agent']}] {st['sub_task'][:120]!r}...")

    print("\nSynthesis (with mock responses):")
    mock_responses = [
        {"agent": "python_dev",  "response": "Here is the FastAPI backend setup:\n\n```python\nfrom fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/data')\ndef get_data():\n    return {'items': [1, 2, 3]}\n```\n\nRun with: `uvicorn main:app --reload`"},
        {"agent": "dotnet_dev",  "response": "Here is the Blazor WASM component to consume the API:\n\n```csharp\n@inject HttpClient Http\n\n@foreach (var item in items) { <p>@item</p> }\n\n@code {\n    int[] items = [];\n    protected override async Task OnInitializedAsync() =>\n        items = await Http.GetFromJsonAsync<int[]>(\"/data\");\n}\n```"},
    ]
    merged = synthesize(query, mock_responses)
    print(merged)
    print("\n✅ deep_pipeline synthesis test passed")
