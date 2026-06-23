"""
SmartLLM — tiered response enhancement via Claude.

For "compound" and "moderate" complexity queries, the specialist agent
generates a draft with phi4-mini; this module runs a Claude pass to
deepen, refine, and elevate it to elite quality.

Simple/fast queries skip enhancement entirely (no latency cost, no API cost).
Claude is also skipped when ANTHROPIC_API_KEY is not set.

Usage (coordinator):
    from models.smart_llm import enhance_response
    response = enhance_response(task, draft, agent, complexity)

LangChain-compatible class for direct agent use:
    from models.smart_llm import get_chat_model
    model = get_chat_model(complexity)
    response = model.invoke(messages)
"""

from __future__ import annotations

import os

_ENHANCE_COMPLEXITY = {"compound", "moderate"}

_ENHANCEMENT_SYSTEM = """\
You are Amagra, an elite AI advisor and specialist.

You are given a task and a draft response from a specialist agent. Your job:
- Deepen the technical reasoning where shallow
- Fix any errors or imprecision
- Add concrete examples, commands, or code where it strengthens the answer
- Cut filler — every sentence must earn its place

Rules:
- Output ONLY the improved response. No preamble, no "here is the enhanced version".
- Keep the same format (code blocks, lists, headers) as the draft.
- If the draft is already excellent, return it verbatim.
- Style: direct, no corporate language, skip the intros.\
"""


def enhance_response(
    task: str,
    draft: str,
    agent: str,
    complexity: str,
    force: bool = False,
) -> str:
    """
    Return Claude-enhanced version of draft for compound/moderate queries.
    Falls back to draft unchanged on any error or if API key is absent.

    `force=True` runs the enhancement regardless of complexity — used by the
    v1.5 hybrid-inference policy to escalate low-confidence routes the router
    was unsure about, even when their complexity is "simple".
    """
    return enhance_response_detailed(task, draft, agent, complexity, force=force)[0]


def enhance_response_detailed(
    task: str,
    draft: str,
    agent: str,
    complexity: str,
    force: bool = False,
):
    """Like enhance_response but also returns the cloud-pass GenResult (or None).

    Returns (text, gen_result). gen_result carries cost_usd/tokens for the
    Cognition Productivity cost axis; it is None whenever the enhancement was
    skipped (complexity gate, missing key, or error) and the draft is returned
    unchanged.
    """
    if not force and complexity not in _ENHANCE_COMPLEXITY:
        return draft, None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return draft, None

    try:
        from providers.anthropic import AnthropicProvider
        model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
        provider = AnthropicProvider(model=model, api_key=api_key)
        prompt = f"Agent specialization: {agent}\nTask: {task}\n\nDraft:\n{draft}"
        res = provider.generate_detailed(
            prompt, system_prompt=_ENHANCEMENT_SYSTEM, temperature=0.2,
        )
        text = res.text.strip() if res.text and res.text.strip() else draft
        return text, res
    except Exception as exc:
        print(f"[smart_llm] enhancement skipped ({complexity}): {exc}")
        return draft, None


async def aenhance_response(
    task: str,
    draft: str,
    agent: str,
    complexity: str,
    force: bool = False,
) -> str:
    """Async version of enhance_response. `force=True` bypasses the complexity
    gate (v1.5 hybrid-inference low-confidence escalation)."""
    if not force and complexity not in _ENHANCE_COMPLEXITY:
        return draft

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return draft

    try:
        from providers.anthropic import AnthropicProvider
        model = os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6")
        provider = AnthropicProvider(model=model, api_key=api_key)
        prompt = f"Agent specialization: {agent}\nTask: {task}\n\nDraft:\n{draft}"
        enhanced = await provider.agenerate(prompt, system_prompt=_ENHANCEMENT_SYSTEM, temperature=0.2)
        return enhanced.strip() if enhanced and enhanced.strip() else draft
    except Exception as exc:
        print(f"[smart_llm] async enhancement skipped ({complexity}): {exc}")
        return draft


def get_chat_model(complexity: str = "simple"):
    """
    Return a LangChain-compatible chat model appropriate for complexity.
    compound/moderate → ChatAnthropic (Claude Sonnet)
    simple/fast       → ChatOllama (phi4-mini, no API cost)
    """
    if complexity in _ENHANCE_COMPLEXITY:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=os.environ.get("ENHANCE_MODEL", "claude-sonnet-4-6"),
                    api_key=api_key,
                    temperature=0.2,
                    max_tokens=4096,
                )
            except Exception:
                pass
    from models.llm import llm
    return llm
