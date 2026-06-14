"""
Route tests for /sandbox/* — the gated code-execution surface.

Disabled by default (403); enabled via AMAGRA_SANDBOX=1 (read live per request).
"""

import os
import sys
import unittest.mock as mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not hasattr(os, "setsid"):
    pytest.skip("POSIX sandbox only", allow_module_level=True)

for _mod in (
    "langchain_ollama", "langchain_core", "langchain_core.messages",
    "langchain_core.documents", "langchain_core.documents.base",
    "langchain_core.runnables", "langchain_core.runnables.base",
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.prebuilt",
    "faiss", "sentence_transformers",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="sbx-test@test.com", tier="developer")}


def teardown_module(module):
    os.environ.pop("AMAGRA_SANDBOX", None)


def test_disabled_by_default_returns_403():
    os.environ.pop("AMAGRA_SANDBOX", None)
    r = client.post("/sandbox/run", json={"code": "print(1)"}, headers=HEADERS)
    assert r.status_code == 403


def test_status_reports_disabled():
    os.environ.pop("AMAGRA_SANDBOX", None)
    r = client.get("/sandbox/status", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_enabled_runs_code():
    os.environ["AMAGRA_SANDBOX"] = "1"
    r = client.post("/sandbox/run", json={"code": "print(6*7)"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["stdout"].strip() == "42"
    assert body["exit_code"] == 0


def test_empty_code_returns_400():
    os.environ["AMAGRA_SANDBOX"] = "1"
    r = client.post("/sandbox/run", json={"code": ""}, headers=HEADERS)
    assert r.status_code in (400, 422)  # 422 if pydantic rejects, 400 from tool
