"""
Neutral extension boundary for the Amagra runtime.

These are the ONLY data structures that cross between the core runtime and an
extension (agent). This module imports nothing from langchain / langgraph by
design — that quarantine is the entire point. An extension may use any
framework it likes internally, but it speaks Context/Result at the wire.

Layering:
    [ core runtime loop ]
            │  Context  ───────────────────►  extension.main()
            │  ◄───────────────────  Result
    RoutingMeta is visible to MIDDLEWARE (reflection, critic gate) only —
    never handed to an extension, so agents cannot branch on routing state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Msg:
    """One turn of conversation history. Framework-neutral."""
    role: str       # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Context:
    """Everything an extension is allowed to read. Deliberately lean —
    no routing metadata, no framework objects."""
    task: str
    history: tuple[Msg, ...] = ()
    memory: Mapping[str, Any] = field(default_factory=dict)
    run_id: str = ""


@dataclass(frozen=True)
class RoutingMeta:
    """The brain's decision. Seen by middleware (reflection / critic gate),
    NOT passed into extensions. Confidence/regret live here because the brain
    computes them — an extension must never fabricate these values."""
    agent: str
    complexity: str = "simple"      # simple | moderate | compound
    confidence: float = 0.67
    regret: float = 0.0
    reflect_level: str = "none"     # none | light | full
    reflect_type: str = "general"   # code | research | general
    conflict: bool = False


@dataclass(frozen=True)
class Result:
    """Everything an extension returns. `output` is the only required field;
    `meta` carries genuinely agent-produced extras (e.g. gram_winner)."""
    output: str
    meta: Mapping[str, Any] = field(default_factory=dict)


def trim_history(history: tuple[Msg, ...], max_messages: int = 20) -> tuple[Msg, ...]:
    """
    Neutral re-implementation of core.context_tools.trim_messages, operating on
    Msg tuples instead of langchain BaseMessage. Hard cut, no summarization.

    - Preserves a leading system message if present.
    - Injects the truncation notice as an assistant turn (never a user turn,
      so the model does not try to answer it).
    """
    if not history:
        return ()

    items = list(history)
    system = items.pop(0) if items and items[0].role == "system" else None

    if len(items) <= max_messages:
        return tuple(([system] if system else []) + items)

    original = len(items)
    items = items[-max_messages:]
    notice = Msg("assistant", f"[Context trimmed: {original} → {max_messages} messages kept]")
    out = ([system] if system else []) + [notice] + items
    return tuple(out)
