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

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


# ── Cost accounting (v1.5 Hybrid Inference) ──────────────────────────────────
# USD per 1,000,000 tokens, (input, output). Approximate list prices; local
# backends (Ollama / LM Studio) are free. Unknown models fall back to (0, 0) —
# cost is reported as 0 rather than guessed wrong. Keep keys aligned with each
# provider's `name` property ("anthropic/<model>", "openai/<model>", ...).
_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus-4-8":   (15.0, 75.0),
    "anthropic/claude-opus-4-7":   (15.0, 75.0),
    "anthropic/claude-opus-4-6":   (15.0, 75.0),
    "anthropic/claude-sonnet-4-6": (3.0, 15.0),
    "anthropic/claude-haiku-4-5":  (0.80, 4.0),
    "openai/gpt-4o":               (2.5, 10.0),
    "openai/gpt-4o-mini":          (0.15, 0.60),
}


def estimate_tokens(text: str | None) -> int:
    """Cheap char-based token estimate (~4 chars/token). Used when a provider
    does not report exact usage. Never raises."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def price_for(provider_name: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a provider name. (0, 0) for local
    or unknown backends — we report 0 rather than guess."""
    return _PRICING_PER_MTOK.get(provider_name, (0.0, 0.0))


def estimate_cost(provider_name: str, tokens_in: int, tokens_out: int) -> float:
    cin, cout = price_for(provider_name)
    return (tokens_in / 1_000_000) * cin + (tokens_out / 1_000_000) * cout


@dataclass(frozen=True)
class GenResult:
    """Structured generation result with cost/latency telemetry.

    The synchronous `generate()` hot path still returns a bare `str` (unchanged,
    non-breaking). `generate_detailed()` is the additive path that also carries
    token counts, USD cost, and latency so hybrid-inference policy can budget
    escalations and the Cognition Productivity axis can chart spend.

    `estimated=True` means tokens were char-estimated rather than reported by
    the provider (true for local backends; Anthropic reports exact usage).
    """
    text: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    estimated: bool = True


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

    def generate_detailed(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> "GenResult":
        """Generate and return token/cost/latency telemetry alongside the text.

        Default implementation wraps `generate()` and char-estimates the token
        counts (estimated=True). Providers that report exact usage (e.g.
        Anthropic) should override this and set estimated=False. Non-breaking:
        callers that only need text keep using `generate()`.
        """
        t0 = time.perf_counter()
        text = self.generate(prompt, system_prompt, temperature)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        tin = estimate_tokens((system_prompt or "") + prompt)
        tout = estimate_tokens(text)
        return GenResult(
            text=text,
            provider=self.name,
            tokens_in=tin,
            tokens_out=tout,
            cost_usd=estimate_cost(self.name, tin, tout),
            latency_ms=latency_ms,
            estimated=True,
        )


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
