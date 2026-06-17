"""
Tests for /launch/readiness — auto-detected launch-readiness status driven by
config flags. No secret values are ever returned, only booleans + descriptions.
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

import routes.readiness as readiness
import core.payments as payments
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)


def test_public_base_url_helper():
    assert readiness._is_public_base_url("https://amagra.dev") is True
    assert readiness._is_public_base_url("http://amagra.dev") is False     # not https
    assert readiness._is_public_base_url("https://localhost:8000") is False
    assert readiness._is_public_base_url("https://127.0.0.1") is False
    assert readiness._is_public_base_url("") is False


def test_endpoint_returns_all_known_ids(monkeypatch):
    monkeypatch.setattr(payments, "is_configured", lambda: False)
    monkeypatch.setattr(payments, "is_webhook_configured", lambda: False)
    r = client.get("/launch/readiness")
    assert r.status_code == 200
    items = r.json()["items"]
    for k in ("s5", "s6", "t1", "t2", "t4", "t6", "r1", "r2"):
        assert k in items
        assert set(items[k]) == {"done", "detail"}
        assert isinstance(items[k]["done"], bool)


def test_unconfigured_deployment_is_not_ready(monkeypatch):
    for var in ("REQUIRE_AUTH", "ADMIN_TOKEN", "BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(payments, "is_configured", lambda: False)
    monkeypatch.setattr(payments, "is_webhook_configured", lambda: False)
    monkeypatch.setattr(readiness, "_has_paying_customer", lambda: False)
    items = readiness.compute_readiness()
    assert all(v["done"] is False for v in items.values())


def test_configured_deployment_flips_to_ready(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    monkeypatch.setenv("ADMIN_TOKEN", "x" * 64)
    monkeypatch.setenv("BASE_URL", "https://amagra.dev")
    monkeypatch.setattr(payments, "is_configured", lambda: True)
    monkeypatch.setattr(payments, "is_webhook_configured", lambda: True)
    monkeypatch.setattr(readiness, "_has_paying_customer", lambda: True)
    items = readiness.compute_readiness()
    assert all(v["done"] is True for v in items.values())


def test_no_secret_values_leak(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "super-secret-token-value")
    r = client.get("/launch/readiness")
    body = r.text
    assert "super-secret-token-value" not in body
