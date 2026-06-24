"""
v1.5 Hybrid Inference — foundation tests (no LLM, no network).

Covers the cheap-win foundation that the auto-escalation policy will build on:
  - providers.base cost accounting (GenResult, estimate_tokens/cost, price_for)
  - the default generate_detailed() wrapper (char-estimated tokens)
  - orchestration.router.decide_with_confidence() — routing-confidence signal
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.base import (
    GenResult,
    ModelProvider,
    estimate_cost,
    estimate_tokens,
    price_for,
)
from orchestration.router import decide, decide_with_confidence, score


# ── cost accounting primitives ────────────────────────────────────────────────

def test_estimate_tokens_char_heuristic():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    assert estimate_tokens("a") == 1            # floor of 1 for any non-empty text
    assert estimate_tokens("x" * 40) == 10      # ~4 chars/token


def test_price_for_known_and_unknown():
    assert price_for("anthropic/claude-opus-4-8") == (15.0, 75.0)
    # Local / unknown backends are free, not guessed.
    assert price_for("ollama/phi4-mini:latest") == (0.0, 0.0)
    assert price_for("totally-unknown") == (0.0, 0.0)


def test_estimate_cost_math():
    # 1M input + 1M output on opus pricing = 15 + 75 = 90 USD.
    assert estimate_cost("anthropic/claude-opus-4-8", 1_000_000, 1_000_000) == 90.0
    assert estimate_cost("ollama/phi4-mini:latest", 1_000_000, 1_000_000) == 0.0


# ── default generate_detailed() wrapper ───────────────────────────────────────

class _FakeProvider(ModelProvider):
    """Minimal local-style provider for exercising the base wrapper."""

    @property
    def name(self) -> str:
        return "ollama/phi4-mini:latest"

    def generate(self, prompt, system_prompt=None, temperature=0.2) -> str:
        return "hello world response"

    async def agenerate(self, prompt, system_prompt=None, temperature=0.2) -> str:
        return self.generate(prompt, system_prompt, temperature)

    async def stream(self, prompt, system_prompt=None):
        yield "hello"

    def health(self) -> dict:
        return {"status": "ok", "provider": "fake"}


def test_generate_detailed_default_is_estimated_and_free_for_local():
    p = _FakeProvider()
    res = p.generate_detailed("a question that is reasonably long")
    assert isinstance(res, GenResult)
    assert res.text == "hello world response"
    assert res.provider == "ollama/phi4-mini:latest"
    assert res.estimated is True
    assert res.tokens_in > 0 and res.tokens_out > 0
    assert res.cost_usd == 0.0           # local backend is free
    assert res.latency_ms >= 0.0


def test_generate_detailed_text_matches_generate():
    p = _FakeProvider()
    assert p.generate_detailed("q").text == p.generate("q")


# ── routing confidence ────────────────────────────────────────────────────────

def test_decide_with_confidence_matches_decide_agent():
    # decide() must stay a thin wrapper — same agent, every time.
    for q in ["write a python function to sort a list",
              "what does dns stand for?",
              "reset port",
              "tell me something"]:
        s = score(q)
        assert decide(q, s) == decide_with_confidence(q, s)[0]


def test_confidence_in_unit_range():
    for q in ["deploy a kubernetes cluster with helm and terraform",
              "what does dns stand for?",
              "hi"]:
        _, conf = decide_with_confidence(q, score(q))
        assert 0.0 <= conf <= 1.0


def test_clear_keyword_winner_is_high_confidence():
    # A query with multiple keywords for one agent and a clear margin.
    q = "write python code to read a csv file and plot a pandas dataframe"
    agent, conf = decide_with_confidence(q, score(q))
    assert conf >= 0.60


def test_ambiguous_short_query_is_low_confidence():
    # Single lone keyword ('docker') in a short query → default fallback,
    # flagged ambiguous (issue #10): not enough context to commit to devops.
    q = "docker logs"
    agent, conf = decide_with_confidence(q, score(q))
    assert agent == "knowledge_learning"
    assert conf <= 0.30


def test_no_match_is_lowest_confidence():
    q = "kubectl pods"
    agent, conf = decide_with_confidence(q, score(q))
    # No scored domain keyword → default fallback at the lowest confidence band.
    assert agent == "knowledge_learning"
    assert conf <= 0.25


# ── smart_llm.enhance_response force gate (hybrid low-confidence escalation) ───

class _FakeAnthropic:
    def __init__(self, *a, **k):
        pass

    def generate(self, prompt, system_prompt=None, temperature=0.2):
        return "ENHANCED"

    def generate_detailed(self, prompt, system_prompt=None, temperature=0.2):
        return GenResult(
            text="ENHANCED", provider="anthropic/claude-sonnet-4-6",
            tokens_in=10, tokens_out=5, cost_usd=0.001, estimated=False,
        )


def test_enhance_skips_simple_without_force(monkeypatch):
    import models.smart_llm as smart_llm
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("providers.anthropic.AnthropicProvider", _FakeAnthropic)
    # complexity "simple" and no force → unchanged draft (legacy behaviour).
    assert smart_llm.enhance_response("q", "draft", "writer", "simple") == "draft"


def test_enhance_force_bypasses_complexity_gate(monkeypatch):
    import models.smart_llm as smart_llm
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("providers.anthropic.AnthropicProvider", _FakeAnthropic)
    # force=True runs the cloud pass even on a "simple" query.
    assert smart_llm.enhance_response("q", "draft", "writer", "simple", force=True) == "ENHANCED"


def test_enhance_force_still_falls_back_without_key(monkeypatch):
    import models.smart_llm as smart_llm
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # No key → draft unchanged regardless of force.
    assert smart_llm.enhance_response("q", "draft", "writer", "simple", force=True) == "draft"
