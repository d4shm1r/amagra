"""
Provider registry — maps roles to configured provider singletons.

Roles
-----
signal   Fast routing — always local (OllamaProvider).
brain    Heavy reasoning — configurable, can be cloud.
embed    Embedding — must stay consistent with the FAISS index.

Env vars
--------
SIGNAL_PROVIDER = ollama (default, only option)
BRAIN_PROVIDER  = ollama | anthropic | openai  (default: ollama)
                  openai = any OpenAI-compatible API (OpenAI/Groq/OpenRouter/
                  Together/LM Studio/remote Ollama) via OPENAI_BASE_URL
EMBED_PROVIDER  = ollama (default, only option)

Singletons are lazy — nothing is instantiated on import. The first
get_provider("brain") call at request time creates and caches the instance.
"""

from __future__ import annotations

import os

from providers.base import EmbeddingProvider, ModelProvider

# Backends served by the single OpenAI-compatible adapter (one adapter, many vendors).
_OPENAI_COMPAT_BACKENDS = {"openai", "openai_compat", "groq", "openrouter", "together", "lmstudio"}

_model_cache: dict[str, ModelProvider] = {}
_embed_cache: dict[str, EmbeddingProvider] = {}


def get_provider(role: str) -> ModelProvider:
    """
    Return the singleton ModelProvider configured for role.

    role must be "signal" or "brain".  For embeddings use
    get_embedding_provider().
    """
    env_key = f"{role.upper()}_PROVIDER"
    backend = os.environ.get(env_key, "ollama").lower()
    cache_key = f"{role}:{backend}"

    if cache_key not in _model_cache:
        if backend == "anthropic":
            from providers.anthropic import AnthropicProvider
            _model_cache[cache_key] = AnthropicProvider()
        elif backend in _OPENAI_COMPAT_BACKENDS:
            from providers.openai_compat import OpenAICompatProvider
            _model_cache[cache_key] = OpenAICompatProvider()
        else:
            from providers.ollama import OllamaProvider
            _model_cache[cache_key] = OllamaProvider()

    return _model_cache[cache_key]


def get_embedding_provider() -> EmbeddingProvider:
    """
    Return the singleton EmbeddingProvider.

    Only Ollama is supported for embeddings — the FAISS index was built with
    nomic-embed-text and switching providers would silently break retrieval.
    """
    backend = os.environ.get("EMBED_PROVIDER", "ollama").lower()

    if backend not in _embed_cache:
        from providers.ollama import OllamaEmbeddingProvider
        _embed_cache[backend] = OllamaEmbeddingProvider()

    return _embed_cache[backend]
