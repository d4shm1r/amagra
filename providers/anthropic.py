"""
Anthropic API adapter — ModelProvider implementation.

This provider routes CoreBrain inference through the Anthropic API.
Agents and the coordinator never import from this file directly — they
get an AnthropicProvider instance from providers.registry.get_provider("brain").

Configuration (all optional, fall back to these defaults):
  ANTHROPIC_API_KEY   Required — Anthropic API key
  ANTHROPIC_MODEL     claude-opus-4-8
"""

import os
from typing import AsyncIterator

from providers.base import ModelProvider


class AnthropicProvider(ModelProvider):

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self._model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    @property
    def name(self) -> str:
        return f"anthropic/{self._model}"

    def _client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self._api_key)

    def _async_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self._api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        import anthropic
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        # temperature not supported on Opus 4.7+; only set for older models
        if "opus-4-6" in self._model or "sonnet" in self._model or "haiku" in self._model:
            kwargs["temperature"] = temperature

        client = self._client()
        try:
            response = client.messages.create(**kwargs)
            return next(
                (block.text for block in response.content if block.type == "text"), ""
            )
        except anthropic.APIError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        import anthropic
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if "opus-4-6" in self._model or "sonnet" in self._model or "haiku" in self._model:
            kwargs["temperature"] = temperature

        async with self._async_client() as client:
            try:
                response = await client.messages.create(**kwargs)
                return next(
                    (block.text for block in response.content if block.type == "text"), ""
                )
            except anthropic.APIError as exc:
                raise RuntimeError(f"Anthropic API error: {exc}") from exc

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._async_client() as client:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text

    def health(self) -> dict:
        if not self._api_key:
            return {
                "status": "error",
                "provider": "anthropic",
                "model": self._model,
                "error": "ANTHROPIC_API_KEY not set",
            }
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self._api_key)
            # Lightweight check: list models (no inference cost)
            models = [m.id for m in client.models.list()]
            available = self._model in models
            return {
                "status": "ok",
                "provider": "anthropic",
                "model": self._model,
                "model_available": available,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "anthropic",
                "model": self._model,
                "error": str(exc),
            }
