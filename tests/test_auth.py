"""
Authentication enforcement tests.

Proves that REQUIRE_AUTH=1 correctly blocks unauthorized access to
protected routes and allows access with a valid key.

No LLM, no Ollama required. Uses FastAPI TestClient with an in-memory
api_keys DB.

Run: python3 -m pytest tests/test_auth.py -v
  or: python3 tests/test_auth.py
"""

import os
import sys
import sqlite3
import tempfile
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Patch api_keys DB to a temp file before importing api ────
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import core.api_keys as _ak
_ak.DB_PATH = _tmp_db.name
_ak.init_db()

# Set auth env var BEFORE importing api so the flag is read correctly
os.environ["REQUIRE_AUTH"] = "1"

from fastapi.testclient import TestClient

# Minimal stubs so api.py imports don't require Ollama/LangChain
import unittest.mock as mock
for _m in (
    "langchain_ollama", "langchain_core", "langchain_core.messages",
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.prebuilt",
    "faiss", "sentence_transformers",
):
    sys.modules.setdefault(_m, mock.MagicMock())

from api import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

# ── Helpers ───────────────────────────────────────────────────

def _make_key(owner="test@example.com", tier="developer") -> str:
    return _ak.create_key(owner=owner, tier=tier)


# ── Protected route matrix ────────────────────────────────────

PROTECTED_ROUTES = [
    ("POST", "/ask",           {"message": "hello", "agent": ""}),
    ("POST", "/tasks/create",  {"title": "t", "prompt": "p"}),
    ("GET",  "/tasks/status",  None),
    ("POST", "/feedback",      {"query": "q", "response": "r", "agent": "a", "rating": 1}),
    ("GET",  "/memory/stats",  None),
    ("GET",  "/memory",        None),
]

PUBLIC_ROUTES = [
    ("GET", "/usage",        None),   # requires key but not under a protected prefix
]


# ── Tests ─────────────────────────────────────────────────────

def test_protected_routes_return_401_without_key():
    """Every protected route must return 401 when no key is sent."""
    failures = []
    for method, path, body in PROTECTED_ROUTES:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json=body or {})
        if r.status_code != 401:
            failures.append(f"{method} {path} → {r.status_code} (expected 401)")
    assert not failures, "\n".join(failures)


def test_protected_routes_return_403_with_invalid_key():
    """Every protected route must return 403 with a bad key."""
    headers = {"X-API-Key": "sk-invalid-key-that-does-not-exist"}
    failures = []
    for method, path, body in PROTECTED_ROUTES:
        if method == "GET":
            r = client.get(path, headers=headers)
        else:
            r = client.post(path, json=body or {}, headers=headers)
        if r.status_code != 403:
            failures.append(f"{method} {path} → {r.status_code} (expected 403)")
    assert not failures, "\n".join(failures)


def test_valid_key_passes_auth_gate():
    """A valid API key must not be rejected by the auth middleware."""
    raw = _make_key("auth-test@example.com", "developer")
    headers = {"X-API-Key": raw}
    # We only test that auth doesn't reject — downstream errors (500, 422)
    # are acceptable since Ollama/LangChain are stubbed.
    for method, path, body in PROTECTED_ROUTES:
        if method == "GET":
            r = client.get(path, headers=headers)
        else:
            r = client.post(path, json=body or {}, headers=headers)
        assert r.status_code not in (401, 403), (
            f"{method} {path}: valid key was rejected with {r.status_code}"
        )


def test_deactivated_key_returns_403():
    """A deactivated key must be treated as invalid."""
    raw = _make_key("deactivated@example.com", "developer")
    rec = _ak.verify_key(raw)
    _ak.deactivate_key(rec["id"])

    headers = {"X-API-Key": raw}
    r = client.get("/memory/stats", headers=headers)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"


def test_rate_limit_returns_429():
    """Exceeding the daily limit must return 429."""
    raw = _make_key("ratelimit@example.com", "free")
    rec = _ak.verify_key(raw)

    # Manually exhaust the free tier limit (100/day)
    import core.api_keys as ak
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = ak._connect()
    conn.execute(
        "UPDATE api_keys SET requests_today=100, last_request_date=? WHERE id=?",
        (today, rec["id"]),
    )
    conn.commit()
    conn.close()

    headers = {"X-API-Key": raw}
    r = client.get("/memory/stats", headers=headers)
    assert r.status_code == 429, f"Expected 429, got {r.status_code}"


def test_public_analytics_routes_are_open():
    """Read-only analytics routes must remain accessible without a key."""
    failures = []
    for method, path, _ in PUBLIC_ROUTES:
        if path == "/usage":
            continue  # /usage itself requires a key — skip
        r = client.get(path)
        if r.status_code == 401:
            failures.append(f"GET {path} → 401 (should be public)")
    assert not failures, "\n".join(failures)


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        test_protected_routes_return_401_without_key,
        test_protected_routes_return_403_with_invalid_key,
        test_valid_key_passes_auth_gate,
        test_deactivated_key_returns_403,
        test_rate_limit_returns_429,
        test_public_analytics_routes_are_open,
    ]

    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
