"""
v1.5 Hybrid Inference — escalation policy tests (no LLM, no network).

select_provider() must keep local as the default and only escalate when every
gate passes (enabled, warranted, tier allowed, in budget, cloud ready). Each
failed gate falls back to local with a reason.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import providers.registry as registry
from providers.anthropic import AnthropicProvider
from providers.ollama import OllamaProvider
from providers.policy import (
    EscalationPolicy,
    cloud_ready,
    load_policy,
    select_provider,
    should_escalate,
)


def _clear():
    registry._model_cache.clear()


ENABLED = EscalationPolicy(enabled=True)
PRO = "pro"


# ── should_escalate predicate ─────────────────────────────────────────────────

def test_disabled_policy_never_escalates():
    p = EscalationPolicy(enabled=False)
    assert should_escalate(0.0, "compound", p) is False


def test_escalates_on_low_confidence():
    assert should_escalate(0.30, None, ENABLED) is True


def test_escalates_on_hard_complexity():
    assert should_escalate(0.99, "compound", ENABLED) is True


def test_no_escalation_when_confident_and_simple():
    assert should_escalate(0.95, "simple", ENABLED) is False


# ── cloud_ready cheap gate ────────────────────────────────────────────────────

def test_cloud_ready_anthropic_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert cloud_ready("anthropic") is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert cloud_ready("anthropic") is True


def test_cloud_ready_unknown_backend_false():
    assert cloud_ready("nope") is False


# ── select_provider: default + gates ──────────────────────────────────────────

def test_default_is_local_when_disabled(monkeypatch):
    _clear()
    monkeypatch.delenv("AMAGRA_HYBRID", raising=False)
    choice = select_provider(confidence=0.1, complexity="compound", tier=PRO)
    assert isinstance(choice.provider, OllamaProvider)
    assert choice.escalated is False


def test_escalates_when_all_gates_pass(monkeypatch):
    _clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    choice = select_provider(
        confidence=0.30, tier=PRO, policy=ENABLED,
    )
    assert isinstance(choice.provider, AnthropicProvider)
    assert choice.escalated is True
    assert "low confidence" in choice.reason


def test_falls_back_when_cloud_not_configured(monkeypatch):
    _clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    choice = select_provider(confidence=0.30, tier=PRO, policy=ENABLED)
    assert isinstance(choice.provider, OllamaProvider)
    assert choice.escalated is False
    assert "not configured" in choice.reason


def test_free_tier_stays_local(monkeypatch):
    _clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    choice = select_provider(confidence=0.10, tier="free", policy=ENABLED)
    assert choice.escalated is False
    assert "not permitted" in choice.reason


def test_budget_exhausted_stays_local(monkeypatch):
    _clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    policy = EscalationPolicy(enabled=True, max_cost_usd=1.0)
    choice = select_provider(
        confidence=0.10, tier=PRO, spent_usd=1.5, policy=policy,
    )
    assert choice.escalated is False
    assert "budget" in choice.reason


def test_budget_under_ceiling_escalates(monkeypatch):
    _clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    policy = EscalationPolicy(enabled=True, max_cost_usd=10.0)
    choice = select_provider(
        confidence=0.10, tier=PRO, spent_usd=2.0, policy=policy,
    )
    assert choice.escalated is True


# ── load_policy env wiring ────────────────────────────────────────────────────

def test_load_policy_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AMAGRA_HYBRID", raising=False)
    assert load_policy().enabled is False


def test_load_policy_reads_env(monkeypatch):
    monkeypatch.setenv("AMAGRA_HYBRID", "1")
    monkeypatch.setenv("AMAGRA_HYBRID_CONFIDENCE_BELOW", "0.4")
    monkeypatch.setenv("AMAGRA_HYBRID_MAX_COST_USD", "5.0")
    p = load_policy()
    assert p.enabled is True
    assert p.confidence_below == 0.4
    assert p.max_cost_usd == 5.0
