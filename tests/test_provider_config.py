"""
Provider/model Settings tests:
  - infrastructure.provider_config persistence, key preservation, env mapping, masking
  - routes/settings_provider: GET /settings/llm, POST /settings/llm/test, POST /settings/llm

No network: the transient provider build is monkeypatched, and reload_runtime is
stubbed so saving never tries to rebuild a real LangChain model.

Run: python3 -m pytest tests/test_provider_config.py -v
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

import pytest

import core.api_keys as _ak
import infrastructure.provider_config as pc
import routes.settings_provider as sp
from fastapi.testclient import TestClient
from api import app

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="provider-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Point the config at a temp file and stop save() from rebuilding a real model."""
    monkeypatch.setenv("AMAGRA_PROVIDER_CONFIG", str(tmp_path / "provider_config.json"))
    monkeypatch.setattr(pc, "reload_runtime", lambda: None)
    yield


# ── persistence layer ─────────────────────────────────────────────────────────

def test_load_empty_when_no_file():
    assert pc.load() == {}


def test_save_and_load_round_trip():
    pc.save({"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-abc"})
    stored = pc.load()
    assert stored["provider"] == "anthropic"
    assert stored["api_key"] == "sk-abc"


def test_blank_key_preserves_stored_key():
    pc.save({"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-secret"})
    # re-save without a key (e.g. the user only changed the model)
    pc.save({"provider": "openai", "model": "gpt-4o", "api_key": ""})
    stored = pc.load()
    assert stored["model"] == "gpt-4o"
    assert stored["api_key"] == "sk-secret"  # preserved


def test_current_never_exposes_key():
    pc.save({"provider": "openai", "model": "gpt-4o-mini", "api_key": "sk-leak"})
    view = pc.current()
    assert "api_key" not in view
    assert view["has_api_key"] is True
    assert view["provider"] == "openai"


def test_apply_to_env_sets_both_provider_vars(monkeypatch):
    for v in ("LLM_PROVIDER", "BRAIN_PROVIDER", "OPENAI_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    pc.apply_to_env({"provider": "groq", "model": "llama-3.1", "base_url": "https://api.groq.com/openai/v1"})
    assert os.environ["LLM_PROVIDER"] == "groq"
    assert os.environ["BRAIN_PROVIDER"] == "groq"
    assert os.environ["OPENAI_MODEL"] == "llama-3.1"


def test_unknown_provider_falls_back_to_ollama_in_env(monkeypatch):
    pc.apply_to_env({"provider": "bogus"})
    assert os.environ["LLM_PROVIDER"] == "ollama"


# ── routes ─────────────────────────────────────────────────────────────────────

def test_get_settings_returns_current_and_options():
    body = client.get("/settings/llm", headers=HEADERS).json()
    assert "current" in body and "providers" in body
    assert "ollama" in body["providers"]
    assert "api_key" not in body["current"]


def test_test_endpoint_health_checks_without_saving(monkeypatch):
    fake = mock.MagicMock()
    fake.health.return_value = {"status": "ok", "provider": "ollama"}
    monkeypatch.setattr(sp, "_build_for", lambda cfg: fake)
    r = client.post("/settings/llm/test", headers=HEADERS,
                    json={"provider": "ollama", "model": "phi4-mini:latest"})
    assert r.json()["status"] == "ok"
    assert pc.load() == {}  # nothing persisted by a test


def test_test_endpoint_returns_error_dict_on_exception(monkeypatch):
    def boom(cfg):
        raise RuntimeError("nope")
    monkeypatch.setattr(sp, "_build_for", boom)
    r = client.post("/settings/llm/test", headers=HEADERS, json={"provider": "ollama"})
    assert r.json()["status"] == "error"
    assert "nope" in r.json()["error"]


def test_save_persists_and_applies(monkeypatch):
    monkeypatch.setattr(sp, "get_provider",
                        lambda role: mock.MagicMock(health=lambda: {"status": "ok"}))
    r = client.post("/settings/llm", headers=HEADERS,
                    json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-x"})
    body = r.json()
    assert body["current"]["provider"] == "anthropic"
    assert body["current"]["has_api_key"] is True
    assert pc.load()["api_key"] == "sk-x"


def test_save_rejects_unknown_provider():
    r = client.post("/settings/llm", headers=HEADERS, json={"provider": "totally-fake"})
    assert r.status_code == 400
