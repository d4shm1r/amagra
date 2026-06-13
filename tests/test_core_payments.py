"""
Tests for core/payments.py — the Stripe integration layer.
All tests use environment variable stubs (no real Stripe calls).
Covers: idempotency store, error paths, plan validation.
"""

import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.payments as pay


# ── PLAN_TO_PRICE / PLAN_TO_TIER ─────────────────────────────────────────────

def test_plan_to_price_keys():
    assert "developer" in pay.PLAN_TO_PRICE
    assert "team" in pay.PLAN_TO_PRICE

def test_plan_to_tier_mapping():
    assert pay.PLAN_TO_TIER["developer"] == "developer"
    assert pay.PLAN_TO_TIER["team"] == "team"


# ── create_checkout_session — error paths ─────────────────────────────────────

def test_create_checkout_no_stripe_key(monkeypatch):
    monkeypatch.setattr(pay, "_STRIPE_KEY", "")
    try:
        pay.create_checkout_session("developer")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "STRIPE_SECRET_KEY" in str(e)

def test_create_checkout_unknown_plan(monkeypatch):
    monkeypatch.setattr(pay, "_STRIPE_KEY", "sk_test_fake")
    try:
        pay.create_checkout_session("unknown_plan")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "unknown_plan" in str(e).lower() or "Unknown plan" in str(e)

def test_create_checkout_known_plan_no_price_id(monkeypatch):
    # Known plan but STRIPE_PRICE_ID not configured → price_id is ""
    monkeypatch.setattr(pay, "_STRIPE_KEY", "sk_test_fake")
    monkeypatch.setattr(pay, "PLAN_TO_PRICE", {"developer": "", "team": ""})
    try:
        pay.create_checkout_session("developer")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "STRIPE_PRICE_ID" in str(e) or "developer" in str(e)


# ── handle_webhook — error paths ──────────────────────────────────────────────

def test_handle_webhook_no_secret(monkeypatch):
    monkeypatch.setattr(pay, "_WEBHOOK_SECRET", "")
    try:
        pay.handle_webhook(b"payload", "sig_header")
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "STRIPE_WEBHOOK_SECRET" in str(e)


# ── idempotency store ─────────────────────────────────────────────────────────

def test_init_events_db_creates_table(tmp_path, monkeypatch):
    db = str(tmp_path / "stripe_events.db")
    monkeypatch.setattr(pay, "_EVENTS_DB", db)
    pay._init_events_db()
    con = sqlite3.connect(db)
    tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    con.close()
    assert ("processed_events",) in tables

def test_is_duplicate_event_false_initially(tmp_path, monkeypatch):
    db = str(tmp_path / "stripe_events.db")
    monkeypatch.setattr(pay, "_EVENTS_DB", db)
    result = pay._is_duplicate_event("evt_test_001")
    assert result is False

def test_mark_and_check_duplicate(tmp_path, monkeypatch):
    db = str(tmp_path / "stripe_events.db")
    monkeypatch.setattr(pay, "_EVENTS_DB", db)
    pay._init_events_db()
    pay._mark_event_processed("evt_test_002", "checkout.session.completed")
    assert pay._is_duplicate_event("evt_test_002") is True

def test_duplicate_check_on_corrupt_db(monkeypatch):
    monkeypatch.setattr(pay, "_EVENTS_DB", "/nonexistent/path/events.db")
    # Should return False gracefully, not raise
    result = pay._is_duplicate_event("evt_test_003")
    assert result is False

def test_mark_event_on_corrupt_db(monkeypatch):
    monkeypatch.setattr(pay, "_EVENTS_DB", "/nonexistent/path/events.db")
    # Should not raise — best-effort
    pay._mark_event_processed("evt_test_004", "test.type")

def test_idempotency_ignores_duplicate_insert(tmp_path, monkeypatch):
    db = str(tmp_path / "stripe_events.db")
    monkeypatch.setattr(pay, "_EVENTS_DB", db)
    pay._init_events_db()
    pay._mark_event_processed("evt_dup", "checkout.session.completed")
    # Second insert should be silently ignored (INSERT OR IGNORE)
    pay._mark_event_processed("evt_dup", "checkout.session.completed")
    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM processed_events WHERE event_id='evt_dup'").fetchone()[0]
    con.close()
    assert n == 1


# ── _stripe() lazy import ─────────────────────────────────────────────────────

def test_stripe_lazy_import_missing():
    import unittest.mock as mock
    with mock.patch.dict(sys.modules, {"stripe": None}):
        try:
            pay._stripe()
        except (RuntimeError, ImportError):
            pass  # expected — stripe not installed or stubbed out


# ── create_checkout_session with mocked stripe ───────────────────────────────

def test_create_checkout_success(monkeypatch):
    import unittest.mock as mock

    fake_session = mock.MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    fake_session.id = "cs_fake_123"

    fake_stripe = mock.MagicMock()
    fake_stripe.checkout.Session.create.return_value = fake_session

    monkeypatch.setattr(pay, "_STRIPE_KEY", "sk_test_fake")
    monkeypatch.setattr(pay, "PLAN_TO_PRICE", {"developer": "price_dev_123"})
    monkeypatch.setattr(pay, "_stripe", lambda: fake_stripe)

    result = pay.create_checkout_session("developer")
    assert result["url"] == "https://checkout.stripe.com/fake"
    assert result["session_id"] == "cs_fake_123"

def test_create_checkout_with_email(monkeypatch):
    import unittest.mock as mock

    fake_session = mock.MagicMock()
    fake_session.url = "https://checkout.stripe.com/fake"
    fake_session.id = "cs_fake_456"

    fake_stripe = mock.MagicMock()
    fake_stripe.checkout.Session.create.return_value = fake_session

    monkeypatch.setattr(pay, "_STRIPE_KEY", "sk_test_fake")
    monkeypatch.setattr(pay, "PLAN_TO_PRICE", {"developer": "price_dev_123"})
    monkeypatch.setattr(pay, "_stripe", lambda: fake_stripe)

    result = pay.create_checkout_session("developer", customer_email="user@test.com")
    # Verify customer_email was passed to stripe
    call_kwargs = fake_stripe.checkout.Session.create.call_args[1]
    assert call_kwargs.get("customer_email") == "user@test.com"


# ── _on_checkout_completed ────────────────────────────────────────────────────

def test_on_checkout_completed(monkeypatch, tmp_path):
    session_obj = {
        "customer_email": "buyer@test.com",
        "metadata": {"plan": "developer"},
        "customer_details": {},
    }
    monkeypatch.setattr(pay, "_EVENTS_DB", str(tmp_path / "events.db"))

    result = pay._on_checkout_completed(session_obj)
    assert result["event"] == "checkout.session.completed"
    assert result["email"] == "buyer@test.com"
    assert "api_key" in result

def test_on_checkout_completed_missing_email(monkeypatch, tmp_path):
    session_obj = {
        "customer_email": "",
        "metadata": {"plan": "team"},
        "customer_details": {"email": "fallback@test.com"},
    }
    monkeypatch.setattr(pay, "_EVENTS_DB", str(tmp_path / "events.db"))

    result = pay._on_checkout_completed(session_obj)
    assert result["event"] == "checkout.session.completed"
