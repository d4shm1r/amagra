"""
Central LLM accessor — provider-selectable.

All agent and coordinator code does: from models.llm import llm
`llm` is a LangChain chat model (.invoke(messages) works the same regardless of
backend), so swapping the backend requires no agent changes.

Choose the backend with one env var (LLM_PROVIDER, or BRAIN_PROVIDER as a fallback
so a single switch moves both routing and agents together):

  ollama     (default) — local, private. Model via OLLAMA_MODEL / OLLAMA_BASE_URL.
  openai               — ANY OpenAI-compatible API: OpenAI, Groq, OpenRouter,
                         Together, LM Studio, or a remote Ollama at /v1.
                         OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL.
  anthropic            — Anthropic API. ANTHROPIC_API_KEY / ANTHROPIC_MODEL.

Lightweight by design: pick `openai` (a hosted API) and nothing heavy runs on the
device — the local footprint drops to the app itself. Pick `ollama` and a small
model (e.g. llama3.2:1b) to stay fully private on modest hardware. Embeddings stay
local regardless (see providers/registry.py) so retrieval keeps working offline.

Any failure to build a non-default backend (missing package, bad key) falls back
to local Ollama, so a misconfiguration never hard-fails the app.
"""

import os

from providers.ollama import OllamaProvider

# Backends that speak the OpenAI chat-completions API. One adapter, many vendors.
_OPENAI_COMPAT = {"openai", "openai_compat", "groq", "openrouter", "together", "lmstudio"}


def _selected_provider() -> str:
    return os.environ.get(
        "LLM_PROVIDER", os.environ.get("BRAIN_PROVIDER", "ollama")
    ).strip().lower()


def _build_openai_compat():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
        temperature=0.7,
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
    )


def _build_anthropic():
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        temperature=0.7,
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
    )


def _build_ollama():
    # Unchanged default — same params as before the provider split.
    return OllamaProvider(
        temperature=0.7,
        num_ctx=2048,
        num_thread=6,
        num_predict=256,
    ).chat_model


def build_llm():
    """Construct the active LangChain chat model from env config (see module docstring)."""
    provider = _selected_provider()
    try:
        if provider in _OPENAI_COMPAT:
            return _build_openai_compat()
        if provider == "anthropic":
            return _build_anthropic()
    except Exception as exc:  # missing package, bad config — never hard-fail
        print(f"[llm] provider '{provider}' unavailable ({exc}); using local Ollama")
    return _build_ollama()


# Existing agent code imports this directly and calls llm.invoke(messages).
llm = build_llm()


def reload_llm():
    """
    Rebuild the active chat model from the current env config and reassign the
    module global. The Settings UI calls this (via infrastructure.provider_config)
    so a provider/model switch takes effect without restarting the server.

    Hot-path callers (tools/agent_runtime.py) import `llm` at call time, so they
    pick up the new object automatically. The two by-value importers
    (agents/terse.py, orchestration/router.py) reference `models.llm.llm` live.
    """
    global llm
    llm = build_llm()
    return llm
