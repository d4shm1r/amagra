"""
Tests for routes/docs_api.py:
  GET /docs/{name} — get content of a specific doc

Note: GET /docs (list) is shadowed by FastAPI's built-in Swagger UI, so
only the parameterized endpoint is testable via TestClient.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="docs-api@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def test_docs_get_not_in_allowed_list():
    r = client.get("/docs/nonexistent-doc-name", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_allowed_but_deleted_failures():
    # 'failures' was in _ALLOWED_DOCS but doc was deleted during refactorization
    r = client.get("/docs/failures", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_allowed_but_deleted_known_issues():
    r = client.get("/docs/known-issues", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_random_name_not_allowed():
    r = client.get("/docs/some-random-name", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_model_overview():
    # ModelOverview was deleted during refactorization
    r = client.get("/docs/ModelOverview", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_tracker():
    r = client.get("/docs/tracker", headers=HEADERS)
    # Either exists (200) or was deleted (404) — not 500
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert "content" in data
        assert "name" in data
