"""
The one agent pipeline.

Every agent used to carry its own copy of this: recall memory, format the
persona with the user profile, run keyword-triggered probes, trim history,
call the model, save the answer. Ten copies, ten chances to drift — and they
had drifted (knowledge_learning silently dropped the user profile whenever it
recalled a memory). There is now one copy, here, driven by an AgentSpec.

Two edges are exposed onto the same pipeline:

  Agent.invoke(state) -> dict   the LangGraph AgentState edge the coordinator
                                calls today. Note there is no StateGraph: each
                                agent used to compile a one-node START->node->END
                                graph purely to obtain `.invoke`, which is all
                                the coordinator ever wanted.

  run(spec, ctx) -> Result      the neutral edge (core/contract.py). No langchain
                                type crosses it. This is the boundary the core
                                runtime speaks, and the reason langchain imports
                                are quarantined to this module.
"""
from __future__ import annotations

# LangChain is confined to this file. It does not reach core/, and it does not
# reach a spec. Adding an agent requires importing none of it.
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

import models.llm as _llm  # late-bound: a runtime provider switch must be seen
from agents.spec import AgentSpec
from core.contract import Context, Result, trim_history
from core.context_tools import trim_messages
from core.user_profile import get_profile_context
from memory_core.context import get_memory_context, save_to_memory

_LC = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}


def _prompt_for(spec: AgentSpec, task: str) -> str:
    prompt = spec.prompt
    if spec.uses_profile:
        prompt = prompt.format(user_profile=get_profile_context(task))
    if spec.remembers and (recalled := get_memory_context(task, spec.name)):
        prompt += "\n\n" + recalled
    return prompt


def _probe_results(spec: AgentSpec, task: str) -> str:
    """Run every probe the task trips, in spec order. A probe that returns
    nothing contributes no block."""
    lowered = task.lower()
    blocks = ""
    for probe in spec.probes:
        if any(t in lowered for t in probe.triggers):
            if found := probe.run(task):
                blocks += f"\n[{probe.label}]\n{found}"
    return blocks


def _compose(spec: AgentSpec, task: str, history: list) -> tuple[list, str]:
    """Assemble the model input. `history` is already langchain messages."""
    prompt = _prompt_for(spec, task)
    messages = [SystemMessage(content=prompt), *history]
    if results := _probe_results(spec, task):
        messages.append(HumanMessage(
            content=f"{spec.probe_intro}\n{results}\n\n{spec.probe_outro}"
        ))
    return messages, prompt


def _answer(spec: AgentSpec, messages: list, prompt: str, task: str):
    if not spec.uses_tools:
        return _llm.llm.invoke(messages)
    from tools.agent_runtime import respond_with_optional_tools
    return respond_with_optional_tools(messages, prompt, task)


def _persist(spec: AgentSpec, task: str, answer: str) -> None:
    if spec.remembers:
        save_to_memory(spec.name, spec.memory_kind, answer,
                       {"task": task[:120] if task else ""})
    if spec.after:
        spec.after(task, answer)


class Agent:
    """An AgentSpec made callable on the coordinator's AgentState."""

    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self.name = spec.name

    def invoke(self, state) -> dict:
        spec = self.spec
        task = state.get("task", "")
        history = trim_messages(state["messages"], max_messages=spec.max_messages)
        messages, prompt = _compose(spec, task, history)
        response = _answer(spec, messages, prompt, task)
        _persist(spec, task, response.content)
        return {
            "messages":     [response],
            "active_agent": spec.name,
            "result":       response.content,
        }


def run(spec: AgentSpec, ctx: Context) -> Result:
    """The neutral edge: Context in, Result out, no langchain in the signature."""
    history = [_LC[m.role](content=m.content)
               for m in trim_history(ctx.history, max_messages=spec.max_messages)]
    messages, prompt = _compose(spec, ctx.task, history)
    response = _answer(spec, messages, prompt, ctx.task)
    _persist(spec, ctx.task, response.content)
    return Result(output=response.content)
