"""
Hybrid-inference escalation policy (v1.5).

Keeps the local model as the default, but escalates *automatically* to a cloud
backend when a query is hard (compound/moderate complexity) or the router was
unsure (low routing confidence) — without the user choosing a model.

Design constraints:
  - **Off by default.** `enabled=False` means local-only, unchanged behaviour.
    Escalation is opt-in via AMAGRA_HYBRID=1 (or an explicit policy), so the
    self-hosted, no-API-key posture is preserved.
  - **Declarative.** `EscalationPolicy` is a plain dataclass; `load_policy()`
    builds it from env today and can be sourced from a `providers.yaml` later
    without touching callers.
  - **Cheap gate.** Readiness is a key-presence check (no network) so the hot
    path never blocks on a provider health round-trip.
  - **Fallback chain.** If escalation is warranted but the cloud backend is not
    ready (missing key) or over budget, we fall back to local and say why.

`select_provider()` is pure w.r.t. its inputs (confidence/complexity/tier/
spent) — it reads env only through `load_policy()` when no policy is passed,
which keeps it trivially testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Optional

from providers.base import ModelProvider
from providers.registry import build_provider

# Complexities that warrant escalation regardless of routing confidence.
_DEFAULT_ESCALATE_COMPLEXITIES = frozenset({"compound", "moderate"})
# Tiers permitted to spend on cloud inference.
_DEFAULT_ALLOW_TIERS = frozenset({"pro", "team", "admin"})

# Cheap readiness preconditions per cloud backend — key/URL presence only.
_OPENAI_COMPAT_BACKENDS = {
    "openai", "openai_compat", "groq", "openrouter", "together", "lmstudio",
}


@dataclass(frozen=True)
class EscalationPolicy:
    enabled: bool = False
    # Escalate when routing confidence is strictly below this.
    confidence_below: float = 0.60
    # Escalate when the query complexity is one of these.
    escalate_complexities: frozenset = _DEFAULT_ESCALATE_COMPLEXITIES
    # Cloud backend to escalate to (must be a build_provider() backend name).
    cloud_backend: str = "anthropic"
    # Local backend used as the default and the fallback.
    local_backend: str = "ollama"
    # Tiers allowed to escalate; others always stay local.
    allow_tiers: frozenset = _DEFAULT_ALLOW_TIERS
    # USD ceiling on accumulated spend; 0 = unlimited. Compared against the
    # caller-supplied running total (the spend ledger lands with cost→traces).
    max_cost_usd: float = 0.0


@dataclass(frozen=True)
class ProviderChoice:
    """Result of select_provider — which provider to use and why."""
    provider: ModelProvider
    backend: str
    escalated: bool
    reason: str


def load_policy() -> EscalationPolicy:
    """Build the active policy from the environment.

    Defaults to disabled (local-only). A future `providers.yaml` loader can
    replace this without changing select_provider() callers.
    """
    enabled = os.environ.get("AMAGRA_HYBRID", "").lower() in {"1", "true", "yes", "on"}
    policy = EscalationPolicy(enabled=enabled)

    raw_conf = os.environ.get("AMAGRA_HYBRID_CONFIDENCE_BELOW")
    if raw_conf:
        try:
            policy = replace(policy, confidence_below=float(raw_conf))
        except ValueError:
            pass

    backend = os.environ.get("AMAGRA_HYBRID_CLOUD_BACKEND")
    if backend:
        policy = replace(policy, cloud_backend=backend.lower())

    raw_budget = os.environ.get("AMAGRA_HYBRID_MAX_COST_USD")
    if raw_budget:
        try:
            policy = replace(policy, max_cost_usd=float(raw_budget))
        except ValueError:
            pass

    return policy


def cloud_ready(backend: str) -> bool:
    """Cheap, no-network check that a cloud backend is configured to be usable.

    A missing API key is the common reason an escalation must fall back to
    local, and checking it here avoids a provider health round-trip in the hot
    path.
    """
    backend = (backend or "").lower()
    if backend == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if backend in _OPENAI_COMPAT_BACKENDS:
        # A custom base URL (LM Studio / local gateway) needs no key; otherwise
        # require an OpenAI key.
        return bool(
            os.environ.get("OPENAI_API_KEY", "").strip()
            or os.environ.get("OPENAI_BASE_URL", "").strip()
        )
    # Unknown backend → treat as not ready (force local fallback).
    return False


def should_escalate(
    confidence: float,
    complexity: Optional[str],
    policy: EscalationPolicy,
) -> bool:
    """Pure predicate: does this query warrant escalation under the policy?

    (Ignores tier/budget/readiness — those are gates applied in
    select_provider after the intent to escalate is established.)
    """
    if not policy.enabled:
        return False
    if complexity and complexity.lower() in policy.escalate_complexities:
        return True
    if confidence < policy.confidence_below:
        return True
    return False


def select_provider(
    *,
    confidence: float = 1.0,
    complexity: Optional[str] = None,
    tier: str = "free",
    spent_usd: float = 0.0,
    policy: Optional[EscalationPolicy] = None,
) -> ProviderChoice:
    """Pick a provider for one generation under the hybrid-inference policy.

    Local stays the default. Escalation requires ALL of: policy enabled, the
    query warrants it (hard or low-confidence), the tier is allowed, the budget
    is not exhausted, and the cloud backend is ready. Any failed gate falls back
    to local with an explanatory reason (the fallback chain).
    """
    policy = policy or load_policy()
    local = ProviderChoice(
        provider=build_provider(policy.local_backend),
        backend=policy.local_backend,
        escalated=False,
        reason="",
    )

    if not should_escalate(confidence, complexity, policy):
        return replace(local, reason="local default (no escalation trigger)")

    if (tier or "free").lower() not in policy.allow_tiers:
        return replace(local, reason=f"tier '{tier}' not permitted to escalate")

    if policy.max_cost_usd and spent_usd >= policy.max_cost_usd:
        return replace(
            local,
            reason=f"budget exhausted (${spent_usd:.2f} ≥ ${policy.max_cost_usd:.2f})",
        )

    if not cloud_ready(policy.cloud_backend):
        return replace(
            local, reason=f"cloud backend '{policy.cloud_backend}' not configured"
        )

    trigger = (
        "low confidence"
        if confidence < policy.confidence_below
        else f"complexity={complexity}"
    )
    return ProviderChoice(
        provider=build_provider(policy.cloud_backend),
        backend=policy.cloud_backend,
        escalated=True,
        reason=f"escalated to {policy.cloud_backend} ({trigger})",
    )
