"""
routes/payments.py — HTTP surface for core/payments.py (Stripe Checkout).

POST /checkout/session   create a Stripe Checkout session, return its hosted URL
POST /webhook/stripe     Stripe -> us: verify signature, provision the API key
GET  /checkout/status    whether Stripe is configured on this deployment

Both write paths are pre-auth (in api.py _PUBLIC_PATHS): a buyer has no API key
yet, and Stripe calls the webhook with its own signature, not our key.
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel

import core.payments as payments

router = APIRouter(tags=["payments"])


class CheckoutRequest(BaseModel):
    plan:  str = "developer"
    email: str | None = None


@router.get("/checkout/status")
def checkout_status():
    """Public: is paid checkout wired on this deployment?"""
    return {
        "configured": payments.is_configured(),
        "plans":      [p for p, price in payments.PLAN_TO_PRICE.items() if price],
    }


@router.post("/checkout/session")
def create_session(body: CheckoutRequest):
    """Create a Stripe Checkout session and return the hosted-page URL."""
    try:
        return payments.create_checkout_session(body.plan, customer_email=body.email)
    except ValueError as e:
        # Unknown plan, or Stripe not configured on this deployment.
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # stripe package missing — deployment misconfiguration.
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
):
    """
    Stripe -> us. Verify the signature against the raw body, then let
    core.payments dispatch (checkout.session.completed provisions a key).
    """
    payload = await request.body()
    try:
        result = payments.handle_webhook(payload, stripe_signature)
    except ValueError as e:
        # Bad/absent signature, or webhook secret not configured. 400 so
        # Stripe records the failure and retries.
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Never leak the raw provisioned key back to the webhook caller.
    result.pop("api_key", None)
    return {"received": True, **result}
