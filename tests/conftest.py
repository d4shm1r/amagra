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

# ── Isolate all durable-data writes into a throwaway dir ─────────────────────
# Every registry-backed database (infrastructure.db → base_dir()) — the event
# bus (logs/events.db), decisions, runs, memory, … — resolves under
# AMAGRA_DATA_DIR when it is set. Pointing it at a per-session temp dir *before*
# any of those modules import means test telemetry (e.g. a /feedback POST that
# runs a learning update and emits ROUTING_WEIGHT_CHANGED) can never leak into
# the real logs/ tree. Without this, synthetic test agents pollute the live
# event log and break data-dependent checks (see test_neutral_mode_validation).
# Must run before the core.api_keys / memory_core.db imports below, which pull
# in modules that cache their DB path at import time.
_SESSION_DATA_DIR = os.environ.setdefault(
    "AMAGRA_DATA_DIR",
    tempfile.mkdtemp(prefix="amagra_test_data_"),
)

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

# ── Ensure the memory DB schema exists ───────────────────────────────────────
# memory_core.db.init_db() only runs under __main__, so a fresh checkout (CI)
# has no `memories` table. Create the schema at the canonical path that every
# consumer (memory_core.db, routes.memory, cognition.coherence) reads from.
# Idempotent: CREATE TABLE IF NOT EXISTS — a no-op where the DB already exists.
import memory_core.db as _mdb
if not getattr(_mdb, "_conftest_schema_ready", False):
    _mdb.init_db()
    _mdb._conftest_schema_ready = True

# ── Pre-create a developer key for protected-route tests ─────────────────────
_TEST_KEY = _ak.create_key(owner="pytest@amagra.dev", tier="developer")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _guard_data_dir_isolation():
    """Reset the durable-data isolation to the session baseline before each test.

    Several modules point AMAGRA_DB (single-file mode) and/or AMAGRA_DATA_DIR at
    their own temp at *import* time (e.g. test_project_explain,
    test_model_choices_prompt_version) and re-assert it in their own autouse
    fixture. Those import-time assignments and any un-restored teardown leak into
    the session env, so a later test can resolve a DB path with no schema — which
    only fails on a clean checkout (CI), e.g. /memory/records → "no such table:
    memories". Resetting here before every test makes each test start from the
    isolation baseline. Modules that need their own isolation re-assert it in a
    module-local autouse fixture, which pytest runs *after* this conftest one, so
    they are unaffected.
    """
    os.environ.pop("AMAGRA_DB", None)
    os.environ["AMAGRA_DATA_DIR"] = _SESSION_DATA_DIR
    yield


@pytest.fixture(scope="session")
def auth_headers():
    return {"X-API-Key": _TEST_KEY}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app, raise_server_exceptions=False)
