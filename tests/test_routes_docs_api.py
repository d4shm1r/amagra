"""
Tests for routes/docs_api.py:
  GET /docs/index  — list the curated project docs
  GET /docs/{name} — get content of a specific doc

Note: the list lives at /docs/index because FastAPI's built-in Swagger UI owns
the exact path /docs and would shadow a route mounted there.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app
from routes.docs_api import _ALLOWED_DOCS, _DOCS_DIR

client = TestClient(app, raise_server_exceptions=False)

import core.api_keys as _ak
_key    = _ak.create_key(owner="docs-api@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


def test_allowed_docs_all_exist_on_disk():
    # The map is curated by hand; this catches a doc being moved or renamed
    # without the API map being updated.
    missing = [
        name for name, rel in _ALLOWED_DOCS.items()
        if not os.path.exists(os.path.join(_DOCS_DIR, rel))
    ]
    assert missing == [], f"_ALLOWED_DOCS entries with no file on disk: {missing}"


def test_docs_index_lists_curated_docs():
    r = client.get("/docs/index", headers=HEADERS)
    assert r.status_code == 200
    docs = r.json()["docs"]
    names = {d["name"] for d in docs}
    assert names == set(_ALLOWED_DOCS)
    for d in docs:
        assert d["size"] > 0
        assert "modified" in d


def test_docs_get_guide_returns_content():
    r = client.get("/docs/guide", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "guide"
    assert len(data["content"]) > 100


def test_docs_get_architecture_returns_content():
    r = client.get("/docs/architecture", headers=HEADERS)
    assert r.status_code == 200
    assert "content" in r.json()


def test_docs_get_unknown_name_404():
    r = client.get("/docs/nonexistent-doc-name", headers=HEADERS)
    assert r.status_code == 404


def test_docs_get_rejects_path_traversal():
    # Names are dict keys, never paths — traversal must 404, not read files.
    r = client.get("/docs/..%2F.env", headers=HEADERS)
    assert r.status_code == 404
