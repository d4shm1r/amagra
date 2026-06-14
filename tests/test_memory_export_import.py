"""
Tests for memory JSON/Markdown export + JSON import (memory_core/db.py).

Runs fully offline: get_embedding is stubbed deterministically, and the
embedding-preserving import path reuses stored vectors without any model call.
"""

import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_core.db as mdb


def _fake_embedding(text: str) -> list:
    rng = random.Random(int(hashlib.md5(text.encode()).hexdigest(), 16))
    return [rng.random() for _ in range(768)]


def _setup(tmp_path, name="mem.db"):
    db = str(tmp_path / name)
    orig_path, orig_emb = mdb.DB_PATH, mdb.get_embedding
    mdb.DB_PATH = db
    mdb.get_embedding = _fake_embedding
    mdb.init_db()
    return db, orig_path, orig_emb


def _teardown(orig_path, orig_emb):
    mdb.DB_PATH, mdb.get_embedding = orig_path, orig_emb


def _seed(n=3):
    for i in range(n):
        assert mdb.save("python_dev", "chat", f"distinct memory number {i}", {"i": i})


def test_export_json_structure(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        _seed(3)
        data = json.loads(mdb.export_memories_json())
        assert data["format"] == "amagra.memory/1"
        assert data["count"] == 3
        assert data["embedding_dim"] == 768
        assert len(data["memories"]) == 3
        assert all("embedding_b64" in m for m in data["memories"])
        assert data["memories"][0]["agent"] == "python_dev"
    finally:
        _teardown(op, oe)


def test_export_json_without_embeddings(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        _seed(2)
        data = json.loads(mdb.export_memories_json(include_embeddings=False))
        assert all("embedding_b64" not in m for m in data["memories"])
        assert data["embedding_dim"] == 0
    finally:
        _teardown(op, oe)


def test_export_markdown_human_readable(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        _seed(2)
        md = mdb.export_memories_markdown()
        assert "# Amagra memory export" in md
        assert "## python_dev" in md
        assert "distinct memory number 0" in md
    finally:
        _teardown(op, oe)


def test_roundtrip_preserves_embeddings_offline(tmp_path):
    # Export from one DB...
    _, op, oe = _setup(tmp_path, "src.db")
    try:
        _seed(3)
        exported = mdb.export_memories_json()
    finally:
        _teardown(op, oe)

    # ...import into a fresh DB with get_embedding DISABLED to prove the stored
    # vectors are reused (no model call on the embedding-preserving path).
    db = str(tmp_path / "dst.db")
    orig_path, orig_emb = mdb.DB_PATH, mdb.get_embedding
    mdb.DB_PATH = db

    def _boom(_):
        raise AssertionError("get_embedding must not be called when embeddings are present")

    mdb.get_embedding = _boom
    mdb.init_db()
    try:
        result = mdb.import_memories_json(exported)
        assert result["imported"] == 3
        assert result["skipped_duplicates"] == 0
        assert result["errors"] == 0
        rows = mdb.export_memories_json()
        assert json.loads(rows)["count"] == 3
    finally:
        mdb.DB_PATH, mdb.get_embedding = orig_path, orig_emb


def test_import_is_idempotent(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        _seed(3)
        exported = mdb.export_memories_json()
        result = mdb.import_memories_json(exported)
        # Everything already present -> all flagged as duplicates, none added.
        assert result["imported"] == 0
        assert result["skipped_duplicates"] == 3
    finally:
        _teardown(op, oe)


def test_import_reembed_uses_model(tmp_path):
    _, op, oe = _setup(tmp_path, "src.db")
    try:
        _seed(2)
        exported = mdb.export_memories_json()
    finally:
        _teardown(op, oe)

    db = str(tmp_path / "dst.db")
    orig_path, orig_emb = mdb.DB_PATH, mdb.get_embedding
    mdb.DB_PATH = db
    calls = {"n": 0}

    def _counting(text):
        calls["n"] += 1
        return _fake_embedding(text)

    mdb.get_embedding = _counting
    mdb.init_db()
    try:
        result = mdb.import_memories_json(exported, reembed=True)
        assert result["imported"] == 2
        assert calls["n"] == 2  # re-embedded each
    finally:
        mdb.DB_PATH, mdb.get_embedding = orig_path, orig_emb


def test_import_rejects_bad_payload(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        try:
            mdb.import_memories_json({"not_memories": 1})
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        _teardown(op, oe)


def test_import_accepts_bare_list(tmp_path):
    _, op, oe = _setup(tmp_path)
    try:
        result = mdb.import_memories_json(
            [{"content": "hand-written note", "agent": "writer"}]
        )
        # No embedding_b64 -> falls back to get_embedding (the fake one).
        assert result["imported"] == 1
    finally:
        _teardown(op, oe)
