"""
OpenAI-compatible API adapter — ModelProvider implementation.

One adapter, many backends: anything that speaks the OpenAI chat-completions API
works here just by changing OPENAI_BASE_URL —

  OpenAI       https://api.openai.com/v1
  Groq         https://api.groq.com/openai/v1
  OpenRouter   https://openrouter.ai/api/v1
  Together     https://api.together.xyz/v1
  LM Studio    http://localhost:1234/v1
  Ollama       http://localhost:11434/v1   (a remote box, so the device stays light)

Agents and the coordinator never import this directly — core_brain gets it from
providers.registry.get_provider("brain"), and the agent hot path goes through
models.llm (which builds a langchain ChatOpenAI for the same config).

Configuration (all optional except the key for hosted endpoints):
  OPENAI_BASE_URL   default https://api.openai.com/v1
  OPENAI_API_KEY    required for hosted APIs; any non-empty string for local servers
  OPENAI_MODEL      default gpt-4o-mini
"""

import os
from typing import AsyncIterator

from providers.base import ModelProvider


class OpenAICompatProvider(ModelProvider):

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        # Local servers (LM Studio, Ollama) ignore the key but the SDK requires one.
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or "not-needed"

    @property
    def name(self) -> str:
        return f"openai/{self._model}"

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self._api_key, base_url=self._base_url)

    def _async_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    @staticmethod
    def _messages(prompt: str, system_prompt: str | None) -> list[dict]:
        msgs: list[dict] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        try:
            resp = self._client().chat.completions.create(
                model=self._model,
                messages=self._messages(prompt, system_prompt),
                temperature=temperature,
                max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"OpenAI-compatible API error: {exc}") from exc

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        try:
            client = self._async_client()
            resp = await client.chat.completions.create(
                model=self._model,
                messages=self._messages(prompt, system_prompt),
                temperature=temperature,
                max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"OpenAI-compatible API error: {exc}") from exc

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        client = self._async_client()
        stream = await client.chat.completions.create(
            model=self._model,
            messages=self._messages(prompt, system_prompt),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    def health(self) -> dict:
        base = {"provider": "openai", "model": self._model, "base_url": self._base_url}
        try:
            models = [m.id for m in self._client().models.list()]
            return {**base, "status": "ok", "model_available": self._model in models}
        except Exception as exc:
            return {**base, "status": "error", "error": str(exc)}
