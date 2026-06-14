"""
Thread management route tests — rename, fork, archive (v1.1).

Seeds a thread + turns directly into sessions.db, then drives the endpoints via
the API. No LLM required.
"""

import os
import sqlite3
import sys
import unittest.mock as mock
import uuid

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

import core.api_keys as _ak
import routes.deps as _deps
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="threads-test@test.com", tier="developer")}


def _seed_thread(title="Seed thread", turns=2):
    tid = f"test-{uuid.uuid4()}"
    conn = sqlite3.connect(_deps._SESSIONS_DB)
    conn.execute(
        "INSERT INTO threads (id, title, created_at, updated_at, turn_count) "
        "VALUES (?,?,datetime('now'),datetime('now'),?)",
        (tid, title, turns),
    )
    for i in range(turns):
        conn.execute(
            "INSERT INTO turns (thread_id, ts, user_msg, agent_msg, agent) "
            "VALUES (?,datetime('now'),?,?,?)",
            (tid, f"q{i}", f"a{i}", "knowledge_learning"),
        )
    conn.commit()
    conn.close()
    return tid


def test_rename_thread():
    tid = _seed_thread()
    r = client.patch(f"/threads/{tid}", json={"title": "Renamed"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    # Reflected in the listing.
    listing = client.get("/threads?limit=200", headers=HEADERS).json()["threads"]
    assert any(t["id"] == tid and t["title"] == "Renamed" for t in listing)


def test_rename_empty_title_400():
    tid = _seed_thread()
    r = client.patch(f"/threads/{tid}", json={"title": "   "}, headers=HEADERS)
    assert r.status_code == 400


def test_rename_missing_thread_404():
    r = client.patch("/threads/does-not-exist", json={"title": "x"}, headers=HEADERS)
    assert r.status_code == 404


def test_fork_thread_copies_turns():
    tid = _seed_thread(title="Original", turns=3)
    r = client.post(f"/threads/{tid}/fork", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["forked_from"] == tid
    assert body["turn_count"] == 3
    assert body["title"].endswith("(fork)")
    # Fork's turns are an independent copy.
    forked = client.get(f"/threads/{body['id']}/turns", headers=HEADERS).json()
    assert len(forked["turns"]) == 3


def test_fork_upto_truncates():
    tid = _seed_thread(turns=4)
    r = client.post(f"/threads/{tid}/fork?upto=2", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["turn_count"] == 2


def test_fork_missing_thread_404():
    r = client.post("/threads/nope/fork", headers=HEADERS)
    assert r.status_code == 404


def test_archive_hides_from_default_list():
    tid = _seed_thread()
    assert client.post(f"/threads/{tid}/archive", headers=HEADERS).json()["archived"] is True
    default = client.get("/threads?limit=200", headers=HEADERS).json()["threads"]
    assert all(t["id"] != tid for t in default)
    # Visible when explicitly included.
    witharch = client.get("/threads?limit=200&include_archived=true", headers=HEADERS).json()["threads"]
    assert any(t["id"] == tid for t in witharch)


def test_unarchive_restores():
    tid = _seed_thread()
    client.post(f"/threads/{tid}/archive", headers=HEADERS)
    assert client.post(f"/threads/{tid}/archive?archived=false", headers=HEADERS).json()["archived"] is False
    default = client.get("/threads?limit=200", headers=HEADERS).json()["threads"]
    assert any(t["id"] == tid for t in default)


def test_archive_missing_thread_404():
    r = client.post("/threads/nope/archive", headers=HEADERS)
    assert r.status_code == 404
