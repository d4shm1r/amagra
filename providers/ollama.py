"""
Ollama adapter — first ModelProvider and EmbeddingProvider implementation.

Agents and the coordinator never import from this file directly. They depend on
the interface in providers.base, and get an OllamaProvider instance from
providers.registry.get_model_provider() or via models.llm.llm (legacy path).

Configuration (all optional, fall back to these defaults):
  OLLAMA_BASE_URL   http://localhost:11434
  OLLAMA_MODEL      phi4-mini:latest
  OLLAMA_EMBED_MODEL nomic-embed-text
"""

import os
from typing import AsyncIterator

from providers.base import EmbeddingProvider, ModelProvider


class OllamaProvider(ModelProvider):

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        num_ctx: int = 2048,
        num_thread: int = 6,
        num_predict: int = 256,
    ):
        from langchain_ollama import ChatOllama

        self._model    = model    or os.environ.get("OLLAMA_MODEL",    "phi4-mini:latest")
        self._base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

        # chat_model is exposed so existing agent code (from models.llm import llm)
        # continues to work without modification during the Phase 1 migration.
        self.chat_model = ChatOllama(
            model=self._model,
            temperature=temperature,
            num_ctx=num_ctx,
            num_thread=num_thread,
            num_predict=num_predict,
            base_url=self._base_url,
        )

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        return self.chat_model.invoke(messages).content

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        response = await self.chat_model.ainvoke(messages)
        return response.content

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        async for chunk in self.chat_model.astream(messages):
            if chunk.content:
                yield chunk.content

    def health(self) -> dict:
        try:
            import httpx
            r = httpx.get(f"{self._base_url}/api/tags", timeout=3.0)
            models = [m["name"] for m in r.json().get("models", [])]
            return {
                "status":           "ok",
                "provider":         "ollama",
                "model":            self._model,
                "base_url":         self._base_url,
                "available_models": models,
            }
        except Exception as exc:
            return {
                "status":   "error",
                "provider": "ollama",
                "model":    self._model,
                "error":    str(exc),
            }


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider backed by Ollama's /api/embeddings endpoint.

    Current production model: nomic-embed-text (768 dimensions).
    The _DIMENSIONS table exists to avoid a round-trip when the dimension is
    already known — it does not restrict which models can be used.
    """

    _DIMENSIONS: dict[str, int] = {
        "nomic-embed-text":        768,
        "nomic-embed-text:latest": 768,
        "mxbai-embed-large":       1024,
        "all-minilm":              384,
    }

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self._model    = model    or os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self._base_url = base_url or os.environ.get("OLLAMA_BASE_URL",   "http://localhost:11434")

    @property
    def model_id(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        import httpx
        r = httpx.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()["embedding"]

    async def aembed(self, text: str) -> list[float]:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
                timeout=30.0,
            )
            r.raise_for_status()
            return r.json()["embedding"]

    def dimensions(self) -> int:
        return self._DIMENSIONS.get(self._model, 768)
