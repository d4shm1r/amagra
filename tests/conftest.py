"""
Shared pytest setup.

Stubs out LLM / LangGraph modules before any test module triggers the first
`from api import app` import.  Each test file may add its own setdefault()
stubs — they're no-ops if conftest already registered the module.

A valid API key is created once per session and exposed via the `auth_headers`
fixture so tests work whether REQUIRE_AUTH is 0 or 1.
"""

import os
import sys
import tempfile
import unittest.mock as mock
import pytest

# ── Ensure project root is importable ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Stub heavy deps before any api import ────────────────────────────────────
_STUB_MODS = (
    "langchain_ollama",
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.messages.ai",
    "langchain_core.messages.human",
    "langchain_core.documents",
    "langchain_core.documents.base",
    "langchain_core.runnables",
    "langchain_core.runnables.base",
    "langgraph",
    "langgraph.graph",
    "langgraph.graph.message",
    "langgraph.checkpoint",
    "langgraph.checkpoint.memory",
    "langgraph.prebuilt",
    "faiss",
    "sentence_transformers",
)
for _mod in _STUB_MODS:
    sys.modules.setdefault(_mod, mock.MagicMock())

# ── Patch api_keys DB to a shared temp file ───────────────────────────────────
_tmp_keys = tempfile.NamedTemporaryFile(suffix="_conftest_keys.db", delete=False)
_tmp_keys.close()

import core.api_keys as _ak
if not getattr(_ak, "_conftest_patched", False):
    _ak.DB_PATH = _tmp_keys.name
    _ak.init_db()
    _ak._conftest_patched = True

# ── Pre-create a developer key for protected-route tests ─────────────────────
_TEST_KEY = _ak.create_key(owner="pytest@amagra.dev", tier="developer")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def auth_headers():
    return {"X-API-Key": _TEST_KEY}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app, raise_server_exceptions=False)
