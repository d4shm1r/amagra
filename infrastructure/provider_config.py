"""
infrastructure/provider_config.py — durable LLM provider/model selection.

The provider abstraction (providers/, models/llm.py) is driven entirely by env
vars, which are normally read once at process start. This module lets the user
change the brain model at runtime from the Settings UI and have the choice
survive a restart:

  * load()          read the persisted config (or {} if none)
  * save(cfg)       persist and apply it (env + live reload)
  * apply_to_env()  map a config dict onto the env vars the providers read
  * current()       a UI-safe view (the API key is never returned, only a flag)

Persistence is a single JSON file at <project>/provider_config.json, overridable
with AMAGRA_PROVIDER_CONFIG. The file is gitignored — it can hold an API key.

Only the "brain" (LLM_PROVIDER / BRAIN_PROVIDER) is configurable here. Embeddings
stay local on purpose: the FAISS index is namespaced to nomic-embed-text and
swapping the embedding model would silently break retrieval.
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Providers we know how to drive (must stay in sync with models/llm.py).
# Everything except "ollama" and "anthropic" is served by the one OpenAI-compatible adapter.
OPENAI_COMPAT = {"openai", "groq", "openrouter", "together", "lmstudio"}
KNOWN_PROVIDERS = {"ollama", "anthropic", *OPENAI_COMPAT}

_SENTINEL_KEEP = "__keep__"  # POST may send this to mean "leave the stored key unchanged"


def config_path() -> str:
    if os.environ.get("AMAGRA_PROVIDER_CONFIG"):
        return os.environ["AMAGRA_PROVIDER_CONFIG"]
    from infrastructure.paths import base_dir
    return os.path.join(base_dir(), "provider_config.json")


def load() -> dict:
    """Return the persisted config, or {} when nothing has been saved yet."""
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _write(cfg: dict) -> None:
    tmp = config_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, config_path())  # atomic on POSIX


def apply_to_env(cfg: dict) -> None:
    """
    Map a config dict onto the env vars that providers/registry.py and
    models/llm.py read. Setting both LLM_PROVIDER and BRAIN_PROVIDER moves the
    agent hot path and the signal/brain registry together.
    """
    provider = (cfg.get("provider") or "ollama").lower()
    if provider not in KNOWN_PROVIDERS:
        provider = "ollama"

    os.environ["LLM_PROVIDER"] = provider
    os.environ["BRAIN_PROVIDER"] = provider

    if provider == "ollama":
        if cfg.get("model"):
            os.environ["OLLAMA_MODEL"] = cfg["model"]
        if cfg.get("base_url"):
            os.environ["OLLAMA_BASE_URL"] = cfg["base_url"]
    elif provider == "anthropic":
        if cfg.get("model"):
            os.environ["ANTHROPIC_MODEL"] = cfg["model"]
        if cfg.get("api_key"):
            os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
    else:  # OpenAI-compatible family
        if cfg.get("model"):
            os.environ["OPENAI_MODEL"] = cfg["model"]
        if cfg.get("base_url"):
            os.environ["OPENAI_BASE_URL"] = cfg["base_url"]
        if cfg.get("api_key"):
            os.environ["OPENAI_API_KEY"] = cfg["api_key"]


def reload_runtime() -> None:
    """Rebuild the cached LLM/provider singletons so a new config takes effect now."""
    import models.llm as llm_mod
    llm_mod.reload_llm()
    try:
        import providers.registry as reg
        reg._model_cache.clear()
    except Exception:
        pass


def save(cfg: dict, *, apply: bool = True) -> dict:
    """
    Persist a config and (by default) apply it to the running process.

    A blank or sentinel api_key means "keep whatever was stored" so the UI can
    re-save without re-typing the secret. Returns the UI-safe current() view.
    """
    incoming = dict(cfg)
    stored = load()

    key = incoming.get("api_key")
    if key in (None, "", _SENTINEL_KEEP):
        # preserve the existing key rather than wiping it
        if stored.get("api_key"):
            incoming["api_key"] = stored["api_key"]
        else:
            incoming.pop("api_key", None)

    _write(incoming)
    if apply:
        apply_to_env(incoming)
        reload_runtime()
    return current()


def current() -> dict:
    """UI-safe view of the effective config (never exposes the API key)."""
    cfg = load()
    provider = (cfg.get("provider") or os.environ.get("LLM_PROVIDER", "ollama")).lower()

    if provider == "ollama":
        model = cfg.get("model") or os.environ.get("OLLAMA_MODEL", "phi4-mini:latest")
        base_url = cfg.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        has_key = False
    elif provider == "anthropic":
        model = cfg.get("model") or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        base_url = ""
        has_key = bool(cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY"))
    else:
        model = cfg.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        base_url = cfg.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        has_key = bool(cfg.get("api_key") or os.environ.get("OPENAI_API_KEY"))

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "has_api_key": has_key,
        "is_openai_compat": provider in OPENAI_COMPAT,
        "embed_model": os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    }
