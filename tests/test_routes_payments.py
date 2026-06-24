"""
Route tests for /checkout/* and /webhook/stripe — offline (Stripe SDK never
called). core.payments functions are monkeypatched so we exercise the HTTP
contract, not Stripe's network.
"""

import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _mod in (
    "langchain_ollama", "langchain_core", "langchain_core.messages",
    "langchain_core.documents", "langchain_core.documents.base",
    "langchain_core.runnables", "langchain_core.runnables.base",
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.prebuilt",
    "faiss", "sentence_transformers",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

import core.payments as payments
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)


# ── /checkout/status ──────────────────────────────────────────

def test_status_unconfigured(monkeypatch):
    monkeypatch.setattr(payments, "is_configured", lambda: False)
    monkeypatch.setattr(payments, "PLAN_TO_PRICE", {"developer": "", "team": ""})
    r = client.get("/checkout/status")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert body["plans"] == []


def test_status_configured(monkeypatch):
    monkeypatch.setattr(payments, "is_configured", lambda: True)
    monkeypatch.setattr(payments, "PLAN_TO_PRICE", {"developer": "price_x", "team": ""})
    r = client.get("/checkout/status")
    assert r.status_code == 200
    assert r.json()["plans"] == ["developer"]


# ── /checkout/session ─────────────────────────────────────────

def test_session_unconfigured_returns_400(monkeypatch):
    def _boom(plan, customer_email=None):
        raise ValueError("STRIPE_SECRET_KEY environment variable not set")
    monkeypatch.setattr(payments, "create_checkout_session", _boom)
    r = client.post("/checkout/session", json={"plan": "developer"})
    assert r.status_code == 400


def test_session_unknown_plan_returns_400(monkeypatch):
    def _boom(plan, customer_email=None):
        raise ValueError(f"Unknown plan '{plan}'")
    monkeypatch.setattr(payments, "create_checkout_session", _boom)
    r = client.post("/checkout/session", json={"plan": "bogus"})
    assert r.status_code == 400


def test_session_returns_url_when_configured(monkeypatch):
    calls = {}
    def _ok(plan, customer_email=None):
        calls["plan"] = plan
        calls["email"] = customer_email
        return {"url": "https://checkout.stripe.com/c/pay/cs_test_123", "session_id": "cs_test_123"}
    monkeypatch.setattr(payments, "create_checkout_session", _ok)
    r = client.post("/checkout/session", json={"plan": "developer", "email": "buyer@test.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("https://checkout.stripe.com/")
    assert body["session_id"] == "cs_test_123"
    assert calls == {"plan": "developer", "email": "buyer@test.com"}


def test_session_defaults_to_developer(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        payments, "create_checkout_session",
        lambda plan, customer_email=None: seen.update(plan=plan) or {"url": "u", "session_id": "s"},
    )
    r = client.post("/checkout/session", json={})
    assert r.status_code == 200
    assert seen["plan"] == "developer"


def test_session_missing_package_returns_503(monkeypatch):
    def _boom(plan, customer_email=None):
        raise RuntimeError("stripe package not installed")
    monkeypatch.setattr(payments, "create_checkout_session", _boom)
    r = client.post("/checkout/session", json={"plan": "developer"})
    assert r.status_code == 503


# ── /webhook/stripe ───────────────────────────────────────────

def test_webhook_bad_signature_returns_400(monkeypatch):
    def _boom(payload, sig):
        raise ValueError("Webhook signature invalid")
    monkeypatch.setattr(payments, "handle_webhook", _boom)
    r = client.post("/webhook/stripe", content=b"{}", headers={"Stripe-Signature": "bad"})
    assert r.status_code == 400


def test_webhook_success_does_not_leak_key(monkeypatch):
    captured = {}
    def _ok(payload, sig):
        captured["payload"] = payload
        captured["sig"] = sig
        return {
            "event": "checkout.session.completed",
            "email": "buyer@test.com",
            "tier": "developer",
            "api_key": "sk-SECRET-should-not-leak",
        }
    monkeypatch.setattr(payments, "handle_webhook", _ok)
    r = client.post(
        "/webhook/stripe", content=b'{"id":"evt_1"}',
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["received"] is True
    assert body["event"] == "checkout.session.completed"
    assert body["tier"] == "developer"
    assert "api_key" not in body            # never echo the provisioned key
    assert captured["payload"] == b'{"id":"evt_1"}'   # raw body passed through
    assert captured["sig"] == "t=1,v1=abc"


def test_webhook_ignored_event(monkeypatch):
    monkeypatch.setattr(
        payments, "handle_webhook",
        lambda payload, sig: {"event": "invoice.paid", "ignored": True},
    )
    r = client.post("/webhook/stripe", content=b"{}", headers={"Stripe-Signature": "t=1,v1=x"})
    assert r.status_code == 200
    assert r.json()["ignored"] is True
