"""
Provider abstraction layer — Phase 1.

ModelProvider and EmbeddingProvider are the stable interfaces that all runtime
code (coordinator, agents, memory) should depend on. Concrete backends (Ollama,
Anthropic, OpenAI, ...) are adapters that implement these interfaces.

Design constraints:
  - generate() is synchronous because the current coordinator and agent code is
    synchronous (LangGraph). agenerate() exists for the async API path.
  - stream() is async-only — SSE streaming (v1.0) requires an async path.
  - EmbeddingProvider.model_id drives memory namespace isolation: switching
    embedding models changes the vector space, so FAISS indexes are namespaced
    by model_id. The namespace() helper returns a filesystem-safe string.
  - health() must not raise — it returns a dict with status="ok"|"error".
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class ModelProvider(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier, e.g. 'ollama/phi4-mini:latest' or 'anthropic/claude-sonnet-4-6'."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Synchronous single-turn generation. Returns the response text."""
        ...

    @abstractmethod
    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """Async single-turn generation. Returns the response text."""
        ...

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Async streaming generation. Yields text chunks as they arrive."""
        ...

    @abstractmethod
    def health(self) -> dict:
        """
        Return provider health without raising.
        Minimum keys: {"status": "ok"|"error", "provider": str}.
        """
        ...


class EmbeddingProvider(ABC):

    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Canonical model identifier, e.g. 'nomic-embed-text' or 'text-embedding-3-large'.

        This is used as the memory namespace key. Two providers with different
        model_ids produce incompatible vector spaces and must use separate FAISS indexes.
        """
        ...

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Synchronous embedding. Returns a float vector."""
        ...

    @abstractmethod
    async def aembed(self, text: str) -> list[float]:
        """Async embedding."""
        ...

    @abstractmethod
    def dimensions(self) -> int:
        """Output vector dimension. Must match the FAISS index dimension for this model_id."""
        ...

    def namespace(self) -> str:
        """
        Filesystem-safe string for namespacing FAISS indexes and SQLite tables.
        e.g. 'nomic-embed-text' → 'nomic-embed-text', 'openai/text-embedding-3-large' → 'openai_text-embedding-3-large'
        """
        return self.model_id.replace("/", "_").replace(":", "_")
