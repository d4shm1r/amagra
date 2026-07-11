"""
routes/register.py — Self-service free-tier registration.

POST /register/free
  - No payment required.
  - Creates a 'free' tier API key (100 req/day).
  - Sends a welcome email if SendGrid is configured.
  - Simple abuse guard: max 3 free keys per email address.
"""

import sqlite3
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

import core.api_keys as _ak
from infrastructure.db import path as _dbpath

router = APIRouter()

_REG_DB  = _dbpath("registrations")


# ── DB setup ─────────────────────────────────────────────────

def _init_reg_db():
    os.makedirs(os.path.dirname(_REG_DB), exist_ok=True)
    con = sqlite3.connect(_REG_DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS free_registrations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    NOT NULL,
            created_at TEXT    NOT NULL
        )
    """)
    con.commit()
    con.close()

_init_reg_db()


# Providers where dots in the local part are ignored (foo.bar@ == foobar@).
# Only these get dot-stripping — most providers treat dots as significant,
# so stripping them universally would conflate genuinely distinct addresses.
_DOT_INSENSITIVE_DOMAINS = {"gmail.com", "googlemail.com"}


def _canonicalize_email(email: str) -> str:
    """
    Collapse trivial aliases of one mailbox to a single canonical form so the
    3-key cap can't be bypassed with plus-addressing (#132):
      abuse+1@x.com, abuse+2@x.com  → abuse@x.com
      f.o.o+tag@gmail.com           → foo@gmail.com
    The cap check and the registration record both use the canonical form;
    the welcome email still goes to the address as entered.
    """
    local, _, domain = email.partition("@")
    local = local.split("+", 1)[0]
    if domain in _DOT_INSENSITIVE_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"


def _count_for_email(email: str) -> int:
    try:
        con = sqlite3.connect(_REG_DB, timeout=3)
        n   = con.execute(
            "SELECT COUNT(*) FROM free_registrations WHERE email=?", (email,)
        ).fetchone()[0]
        con.close()
        return n
    except Exception:
        return 0


def _record_registration(email: str) -> None:
    con = sqlite3.connect(_REG_DB, timeout=3)
    con.execute(
        "INSERT INTO free_registrations (email, created_at) VALUES (?,?)",
        (email, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


# ── Request / response models ────────────────────────────────

class RegisterFreeRequest(BaseModel):
    email: str
    name:  str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/register/free")
def register_free(body: RegisterFreeRequest):
    """
    Self-service free tier signup. Returns an API key immediately.
    Limit: 3 free keys per email address.
    """
    canonical = _canonicalize_email(body.email)
    if _count_for_email(canonical) >= 3:
        raise HTTPException(
            status_code=429,
            detail="Maximum 3 free keys per email address. Upgrade at /pricing.",
        )

    owner = body.name.strip() or body.email
    raw_key = _ak.create_key(owner=owner, tier="free")
    _record_registration(canonical)

    # Send welcome email if SendGrid is configured (best-effort, never blocks)
    try:
        from core.emailer import send_onboarding_email
        send_onboarding_email(
            to_email   = body.email,
            api_key    = raw_key,
            tier       = "free",
            plan_label = "Free",
        )
    except Exception:
        pass

    return {
        "key":         raw_key,
        "tier":        "free",
        "daily_limit": 100,
        "note":        "Store this key — it will not be shown again. "
                       "Upgrade to Developer ($39/mo) for 5,000 req/day at /pricing.",
    }


@router.get("/pricing")
def pricing():
    """Public: plan details and pricing."""
    return {
        "plans": [
            {
                "id":          "free",
                "name":        "Free",
                "price_usd":   0,
                "billing":     "none",
                "daily_limit": 100,
                "features":    ["100 req/day", "All agents", "Memory browser",
                                "Decision replay", "Plan graph"],
                "cta":         "POST /register/free",
            },
            {
                "id":          "developer",
                "name":        "Developer",
                "price_usd":   39,
                "billing":     "monthly",
                "daily_limit": 5000,
                "features":    ["5,000 req/day", "All agents", "Full COS access",
                                "Priority support", "Skill graph API"],
                "cta":         "POST /checkout/session",
            },
            {
                "id":          "team",
                "name":        "Team",
                "price_usd":   249,
                "billing":     "monthly",
                "daily_limit": 50000,
                "features":    ["50,000 req/day", "Shared cognitive state",
                                "Multi-user API keys", "Team analytics",
                                "Slack alerts"],
                "cta":         "POST /checkout/session (plan=team)",
                "available":   False,
                "note":        "Coming soon — join waitlist at /register/free",
            },
            {
                "id":          "enterprise",
                "name":        "Enterprise",
                "price_usd":   None,
                "billing":     "annual",
                "daily_limit": None,
                "features":    ["Unlimited requests", "On-premise deployment",
                                "SLA 99.9%", "Custom agents", "Dedicated support"],
                "cta":         "Contact sales",
            },
        ]
    }
