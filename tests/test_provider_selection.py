"""
Guards the provider-selection logic in models.llm and providers.registry
(the BYO-model / "choose API or local" feature).

Runs WITHOUT langchain-openai / openai installed and WITHOUT network: it verifies
the env-driven dispatch and the resilient fall-back to local Ollama, not live calls.
(The test env mocks Ollama, so we assert on selection + no-raise, not class names.)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.llm as llm_mod
from providers.registry import _OPENAI_COMPAT_BACKENDS


def test_default_selection_is_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("BRAIN_PROVIDER", raising=False)
    assert llm_mod._selected_provider() == "ollama"


def test_brain_provider_is_the_fallback_selector(monkeypatch):
    # LLM_PROVIDER unset → BRAIN_PROVIDER decides, so one switch moves routing + agents.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("BRAIN_PROVIDER", "openai")
    assert llm_mod._selected_provider() == "openai"


def test_llm_provider_takes_precedence(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("BRAIN_PROVIDER", "openai")
    assert llm_mod._selected_provider() == "anthropic"


def test_selection_is_case_and_space_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "  OpenAI ")
    assert llm_mod._selected_provider() == "openai"


def test_openai_without_package_falls_back_without_raising(monkeypatch):
    # langchain-openai absent in the base env → build_llm must catch and return the
    # local Ollama model rather than blowing up the whole app.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    model = llm_mod.build_llm()
    assert model is not None


def test_accessor_and_registry_agree_on_openai_backends():
    assert {"openai", "groq", "openrouter", "together", "lmstudio"} <= _OPENAI_COMPAT_BACKENDS
    assert _OPENAI_COMPAT_BACKENDS == llm_mod._OPENAI_COMPAT


def test_openai_compat_provider_constructs_offline(monkeypatch):
    # Constructing the adapter must not require network or a real key (lazy client).
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("OPENAI_MODEL", "llama-3.1-8b-instant")
    from providers.openai_compat import OpenAICompatProvider
    p = OpenAICompatProvider()
    assert p.name == "openai/llama-3.1-8b-instant"
    assert p._base_url.endswith("/openai/v1")
