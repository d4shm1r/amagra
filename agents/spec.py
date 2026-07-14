"""
What an agent IS, as data.

Every agent in this system does the same six things: build a prompt from its
persona + the user profile + recalled memory, run any self-checks the task
mentions, trim the history, call the model, save what it said, and report back.
The only things that actually differ between them are declared here.

Adding an agent means writing a spec and its probes — not another copy of the
pipeline. `agents/runner.py` is the pipeline, and it is the only one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class Probe:
    """A system self-check the agent runs *before* answering, when the task
    mentions one of `triggers`.

    `run` takes the task text and returns the block body. Returning an empty
    string means "nothing to report" and the block is omitted entirely — this
    is load-bearing for probes that match a keyword but find nothing to say
    (e.g. the learning roadmap, which triggers on "roadmap" but only fires if
    it also recognizes the subject).
    """
    triggers: tuple[str, ...]
    label: str
    run: Callable[[str], str]


@dataclass(frozen=True)
class AgentSpec:
    """The whole of an agent's identity. Everything else is shared machinery."""

    name: str                       # must match a key in agents/registry.py
    prompt: str                     # persona; may contain a {user_profile} slot

    probes: tuple[Probe, ...] = ()

    # How recalled/saved memory is tagged. Mostly "chat"; python_dev writes
    # "code" and knowledge_learning writes "lesson", and downstream retrieval
    # filters on it, so it is not cosmetic.
    memory_kind: str = "chat"

    # Wording around the injected probe results. These sit in the model's
    # context, so they are behaviour, not decoration — each agent keeps its own.
    probe_intro: str = "Tool results from this system:"
    probe_outro: str = "Use these in your response."

    max_messages: int = 10

    remembers: bool = True          # recall before answering, save after
    uses_profile: bool = True       # fill the {user_profile} slot
    uses_tools: bool = True         # tool-calling loop vs. a bare model call

    # Ran after the response is saved, for agents with side effects of their
    # own (knowledge_learning records the lesson and advances progress).
    after: Optional[Callable[[str, str], None]] = None
