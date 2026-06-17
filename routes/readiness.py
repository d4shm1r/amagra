"""
routes/readiness.py — auto-detected launch-readiness status.

The Progress tab's Launch Readiness checklist was tracked by manual localStorage
checkboxes. This endpoint reports the *real* state of the items the server can
actually verify (config flags, Stripe wiring, whether a paying customer exists),
keyed by the same item ids as ui/src/constants.js LAUNCH_CHECKLIST so the UI can
merge auto-detected truth over the manual checkboxes.

Only booleans are returned — never the secret values themselves.
"""

import os

from fastapi import APIRouter

import core.api_keys as _ak
import core.payments as _pay

router = APIRouter(tags=["readiness"])


def _is_public_base_url(url: str) -> bool:
    """A real deployment URL: https and not a localhost/loopback host."""
    if not url:
        return False
    u = url.strip().lower()
    if not u.startswith("https://"):
        return False
    return not any(h in u for h in ("localhost", "127.0.0.1", "0.0.0.0"))


def _has_paying_customer() -> bool:
    try:
        return any(k.get("tier") in ("developer", "team") for k in _ak.list_keys())
    except Exception:
        return False


def compute_readiness() -> dict:
    """Map LAUNCH_CHECKLIST item ids → auto-detected {done, detail}."""
    require_auth   = os.environ.get("REQUIRE_AUTH", "0") == "1"
    admin_token    = bool(os.environ.get("ADMIN_TOKEN", "").strip())
    base_url       = os.environ.get("BASE_URL", "")
    stripe_ready   = _pay.is_configured()
    webhook_ready  = _pay.is_webhook_configured()
    paying         = _has_paying_customer()

    items = {
        # Security gate
        "s5": (admin_token,   "ADMIN_TOKEN env var is set" if admin_token
                              else "ADMIN_TOKEN not set — admin routes return 503"),
        "s6": (require_auth,  "REQUIRE_AUTH=1 — endpoints gated by API key" if require_auth
                              else "REQUIRE_AUTH=0 — all endpoints open (dev mode)"),
        # Technical gate
        "t1": (stripe_ready,  "Stripe checkout configured (key + price id)" if stripe_ready
                              else "STRIPE_SECRET_KEY / STRIPE_PRICE_ID not set"),
        "t2": (require_auth,  "API-key auth enforced on protected routes" if require_auth
                              else "Auth not enforced (REQUIRE_AUTH=0)"),
        "t4": (_is_public_base_url(base_url),
                              "BASE_URL points at a public https host" if _is_public_base_url(base_url)
                              else "BASE_URL unset or still localhost"),
        "t6": (require_auth,  "Per-tier daily + per-minute rate limits active" if require_auth
                              else "Rate limiting only applies once REQUIRE_AUTH=1"),
        # Revenue gate
        "r1": (webhook_ready, "STRIPE_WEBHOOK_SECRET set — webhooks verifiable" if webhook_ready
                              else "STRIPE_WEBHOOK_SECRET not set"),
        "r2": (paying,        "At least one Developer/Team key exists" if paying
                              else "No paying (Developer/Team) keys yet"),
    }
    return {k: {"done": done, "detail": detail} for k, (done, detail) in items.items()}


@router.get("/launch/readiness")
def launch_readiness():
    """Auto-detected status for the verifiable Launch Readiness items."""
    return {"items": compute_readiness()}
