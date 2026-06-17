"""
payments.py — Stripe Checkout integration

Flow:
  1. POST /checkout/session  → create a Stripe Checkout session, return URL
  2. User completes payment on Stripe's hosted page
  3. Stripe sends POST /webhook/stripe (checkout.session.completed)
  4. Webhook: verify signature → create API key → send onboarding email

Environment variables required:
  STRIPE_SECRET_KEY        sk_live_... or sk_test_...
  STRIPE_WEBHOOK_SECRET    whsec_...
  STRIPE_PRICE_ID          price_... (Developer plan, $39/month)
  BASE_URL                 https://yourdomain.com  (for success/cancel redirect)

Optional:
  STRIPE_TEAM_PRICE_ID     price_... (Team plan, $249/month)
"""

import os
import sqlite3

_STRIPE_KEY     = os.environ.get("STRIPE_SECRET_KEY", "")
_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
_PRICE_ID       = os.environ.get("STRIPE_PRICE_ID", "")
_TEAM_PRICE_ID  = os.environ.get("STRIPE_TEAM_PRICE_ID", "")
_BASE_URL       = os.environ.get("BASE_URL", "http://localhost:3000")

PLAN_TO_PRICE = {
    "developer": _PRICE_ID,
    "team":      _TEAM_PRICE_ID,
}

PLAN_TO_TIER = {
    "developer": "developer",
    "team":      "team",
}

# ── Idempotency store ─────────────────────────────────────────
from infrastructure.db import path as _dbpath
_EVENTS_DB = _dbpath("stripe_events")

def _init_events_db():
    os.makedirs(os.path.dirname(_EVENTS_DB), exist_ok=True)
    con = sqlite3.connect(_EVENTS_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id     TEXT PRIMARY KEY,
            event_type   TEXT,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def _is_duplicate_event(event_id: str) -> bool:
    try:
        _init_events_db()
        con = sqlite3.connect(_EVENTS_DB, timeout=3)
        row = con.execute(
            "SELECT 1 FROM processed_events WHERE event_id=?", (event_id,)
        ).fetchone()
        con.close()
        return row is not None
    except Exception:
        return False

def _mark_event_processed(event_id: str, event_type: str) -> None:
    try:
        con = sqlite3.connect(_EVENTS_DB, timeout=3)
        con.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, event_type) VALUES (?,?)",
            (event_id, event_type)
        )
        con.commit()
        con.close()
    except Exception:
        pass


def is_configured() -> bool:
    """Whether this deployment can create paid checkout sessions."""
    return bool(_STRIPE_KEY and any(PLAN_TO_PRICE.values()))


def is_webhook_configured() -> bool:
    """Whether incoming Stripe webhooks can be signature-verified."""
    return bool(_WEBHOOK_SECRET)


def _stripe():
    """Lazy import stripe so missing package doesn't break the whole API."""
    try:
        import stripe as _s
        _s.api_key = _STRIPE_KEY
        return _s
    except ImportError:
        raise RuntimeError(
            "stripe package not installed. Run: pip install stripe"
        )


def create_checkout_session(plan: str, customer_email: str | None = None) -> dict:
    """
    Create a Stripe Checkout session for the given plan.

    Returns:
        {"url": "https://checkout.stripe.com/...", "session_id": "cs_..."}

    Raises:
        ValueError  — unknown plan or missing STRIPE_PRICE_ID
        RuntimeError — Stripe package not installed
    """
    if not _STRIPE_KEY:
        raise ValueError("STRIPE_SECRET_KEY environment variable not set")

    price_id = PLAN_TO_PRICE.get(plan)
    if not price_id:
        raise ValueError(
            f"Unknown plan '{plan}' or STRIPE_PRICE_ID not configured. "
            f"Known plans: {list(PLAN_TO_PRICE.keys())}"
        )

    s = _stripe()

    kwargs: dict = {
        "mode":                 "subscription",
        "line_items":           [{"price": price_id, "quantity": 1}],
        "success_url":          f"{_BASE_URL}/success?session={{CHECKOUT_SESSION_ID}}",
        "cancel_url":           f"{_BASE_URL}/#pricing",
        "metadata":             {"plan": plan},
        "billing_address_collection": "auto",
        "allow_promotion_codes": True,
    }
    if customer_email:
        kwargs["customer_email"] = customer_email

    session = s.checkout.Session.create(**kwargs)
    return {"url": session.url, "session_id": session.id}


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Verify and dispatch a Stripe webhook event.

    Returns a result dict:
        {"event": "checkout.session.completed", "api_key": "sk-...", "email": "..."}
        or {"event": "...", "ignored": True}

    Raises:
        ValueError — signature verification failed
    """
    if not _WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET not set — cannot verify webhook")

    s = _stripe()

    try:
        event = s.Webhook.construct_event(payload, sig_header, _WEBHOOK_SECRET)
    except s.error.SignatureVerificationError as e:
        raise ValueError(f"Webhook signature invalid: {e}")

    event_id   = event.get("id", "")
    event_type = event.get("type", "")

    if _is_duplicate_event(event_id):
        print(f"[payments] duplicate event {event_id} — skipping")
        return {"event": event_type, "duplicate": True}

    _mark_event_processed(event_id, event_type)

    if event_type == "checkout.session.completed":
        return _on_checkout_completed(event["data"]["object"])

    return {"event": event_type, "ignored": True}


def _on_checkout_completed(session) -> dict:
    """
    Called when a Stripe Checkout session completes successfully.
    Creates an API key and triggers email delivery.
    """
    import core.api_keys as _ak
    from core.emailer import send_onboarding_email

    email  = session.get("customer_email") or session.get("customer_details", {}).get("email", "")
    plan   = session.get("metadata", {}).get("plan", "developer")
    tier   = PLAN_TO_TIER.get(plan, "developer")

    raw_key = _ak.create_key(owner=email, tier=tier)

    try:
        send_onboarding_email(
            to_email=email,
            api_key=raw_key,
            tier=tier,
            plan_label=plan.capitalize(),
        )
    except Exception as e:
        print(f"[payments] email delivery failed for {email}: {e}")

    print(f"[payments] key provisioned: tier={tier} owner={email}")
    return {
        "event":   "checkout.session.completed",
        "email":   email,
        "tier":    tier,
        "api_key": raw_key,
    }
