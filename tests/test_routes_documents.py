"""
Document upload / list / delete route tests.

Patches memory_core.db.get_embedding so no Ollama is needed. Uses a real
temp SQLite DB so chunking + storage logic is fully exercised.

Run: python3 -m pytest tests/test_routes_documents.py -v
"""

import io
import os
import sys
import sqlite3
import tempfile
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

# ── Temp memory DB with correct schema ───────────────────────────────────────
_tmp_mem = tempfile.NamedTemporaryFile(suffix="_docs_test.db", delete=False)
_tmp_mem.close()

_conn = sqlite3.connect(_tmp_mem.name)
_conn.execute("""
    CREATE TABLE IF NOT EXISTS memories (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT,
        agent_name    TEXT,
        mem_type      TEXT,
        content       TEXT,
        embedding     BLOB,
        metadata      TEXT,
        quality       REAL    DEFAULT 1.0,
        use_count     INTEGER DEFAULT 0,
        last_used     TEXT,
        owner_key_id  INTEGER
    )
""")
_conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_name)")
_conn.commit()
_conn.close()

import memory_core.db as _mdb
import memory_core.backend as _mbe
import hashlib as _hashlib
import random as _random

def _fake_embedding(text: str) -> list:
    """Deterministic unique-ish vector per text so dedup doesn't fire between different chunks."""
    seed = int(_hashlib.md5(text.encode()).hexdigest(), 16)
    rng  = _random.Random(seed)
    return [rng.random() for _ in range(768)]


_orig_get_embedding = None
_orig_db_path = None

def setup_module(module):
    """Apply DB + embedding patches at test-execution time, not collection time."""
    global _orig_get_embedding, _orig_db_path
    _orig_get_embedding = _mdb.get_embedding
    _orig_db_path = _mdb.DB_PATH
    _mdb.DB_PATH = _tmp_mem.name
    _mdb.get_embedding = _fake_embedding
    _mbe._default_backend = None  # force get_backend() to re-init with patched DB_PATH


def teardown_module(module):
    """Restore original get_embedding and DB_PATH so later test files aren't affected."""
    if _orig_get_embedding is not None:
        _mdb.get_embedding = _orig_get_embedding
    if _orig_db_path is not None:
        _mdb.DB_PATH = _orig_db_path
    _mbe._default_backend = None

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="docs-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upload(filename: str, content: str, content_type: str = "text/plain"):
    return client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content.encode()), content_type)},
        headers=HEADERS,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_upload_plain_text():
    text = "Python is a high-level programming language.\n\n" * 10
    r = _upload("test_readme.txt", text)
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "test_readme.txt"
    assert body["chunks_stored"] >= 1
    assert body["chars"] > 0


def test_upload_markdown():
    md = "# Title\n\nSome **bold** text here.\n\n## Section\n\nMore content.\n" * 8
    r = _upload("notes.md", md, "text/markdown")
    assert r.status_code == 200
    assert r.json()["chunks_stored"] >= 1


def test_upload_python_file():
    code = "def add(a, b):\n    return a + b\n\n" * 20
    r = _upload("utils.py", code, "text/x-python")
    assert r.status_code == 200
    assert r.json()["chunks_stored"] >= 1


def test_upload_unsupported_type_returns_422():
    r = _upload("binary.exe", "garbage data")
    assert r.status_code == 422
    assert "Unsupported" in r.json()["detail"]


def test_upload_empty_file_returns_422():
    r = _upload("empty.txt", "")
    assert r.status_code == 422


def test_list_documents_returns_dict():
    r = client.get("/documents", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "documents" in body
    assert isinstance(body["documents"], list)


def test_list_documents_shows_uploaded_file():
    _upload("listed_file.txt", "content for listing test " * 20)
    r = client.get("/documents", headers=HEADERS)
    filenames = [d["filename"] for d in r.json()["documents"]]
    assert "listed_file.txt" in filenames


def test_delete_document():
    _upload("to_delete.txt", "this file will be deleted " * 20)
    r = client.delete("/documents/to_delete.txt", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] >= 0
    assert body["filename"] == "to_delete.txt"


def test_delete_removes_from_list():
    _upload("ephemeral.txt", "temporary file content " * 20)
    client.delete("/documents/ephemeral.txt", headers=HEADERS)
    r = client.get("/documents", headers=HEADERS)
    filenames = [d["filename"] for d in r.json()["documents"]]
    assert "ephemeral.txt" not in filenames


def test_reupload_is_idempotent():
    content = "Idempotency test content for chunking. " * 30
    r1 = _upload("idempotent.txt", content)
    r2 = _upload("idempotent.txt", content)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second upload should replace chunks, not accumulate them
    r = client.get("/documents", headers=HEADERS)
    docs = {d["filename"]: d["chunks"] for d in r.json()["documents"]}
    assert docs.get("idempotent.txt") == r1.json()["chunks_stored"]


def test_upload_json_file():
    data = '{"key": "value", "items": [1, 2, 3]}\n' * 15
    r = _upload("config.json", data, "application/json")
    assert r.status_code == 200


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [
        test_upload_plain_text, test_upload_markdown, test_upload_python_file,
        test_upload_unsupported_type_returns_422, test_upload_empty_file_returns_422,
        test_list_documents_returns_dict, test_list_documents_shows_uploaded_file,
        test_delete_document, test_delete_removes_from_list,
        test_reupload_is_idempotent, test_upload_json_file,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
