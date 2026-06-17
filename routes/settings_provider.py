"""
routes/settings_provider.py — choose the brain model/provider from the UI.

  GET  /settings/llm        current effective config (API key never returned)
  POST /settings/llm/test   build a transient provider from the body and health-check it
  POST /settings/llm        persist + apply a new config, then return the new view

These are authenticated (not in api.py `_PUBLIC_PATHS`) because changing the
backend — including an outbound base_url and API key — is an owner action.

Embeddings are intentionally not configurable here: the FAISS index is namespaced
to nomic-embed-text and switching the embedding model would break retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from infrastructure import provider_config as pc
from providers.registry import get_provider

router = APIRouter()


class LLMConfig(BaseModel):
    provider: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None  # "" or omitted = keep the stored key on save


def _validate(cfg: LLMConfig) -> None:
    if cfg.provider.lower() not in pc.KNOWN_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{cfg.provider}'. Known: {sorted(pc.KNOWN_PROVIDERS)}",
        )


@router.get("/settings/llm")
def get_llm_settings():
    return {
        "current": pc.current(),
        "providers": sorted(pc.KNOWN_PROVIDERS),
        "openai_compat": sorted(pc.OPENAI_COMPAT),
    }


def _build_for(cfg: dict):
    """Build a throwaway ModelProvider for the given config without touching env/state."""
    provider = cfg["provider"].lower()
    if provider == "ollama":
        from providers.ollama import OllamaProvider
        return OllamaProvider(model=cfg.get("model"), base_url=cfg.get("base_url"))
    if provider == "anthropic":
        from providers.anthropic import AnthropicProvider
        return AnthropicProvider(model=cfg.get("model"), api_key=cfg.get("api_key"))
    from providers.openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(
        model=cfg.get("model"),
        base_url=cfg.get("base_url"),
        api_key=cfg.get("api_key"),
    )


@router.post("/settings/llm/test")
def test_llm_settings(cfg: LLMConfig):
    """Health-check a candidate config without saving it. Falls back to the stored key if blank."""
    _validate(cfg)
    body = cfg.model_dump()
    if not body.get("api_key"):
        stored = pc.load()
        if stored.get("api_key"):
            body["api_key"] = stored["api_key"]
    try:
        return _build_for(body).health()
    except Exception as exc:
        return {"status": "error", "provider": cfg.provider, "error": str(exc)}


@router.post("/settings/llm")
def save_llm_settings(cfg: LLMConfig):
    """Persist + apply the config, then return the new effective view plus a health check."""
    _validate(cfg)
    current = pc.save(cfg.model_dump())  # preserves stored key when blank, applies + reloads
    try:
        health = get_provider("brain").health()
    except Exception as exc:
        health = {"status": "error", "error": str(exc)}
    return {"current": current, "health": health}
