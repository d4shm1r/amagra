"""
Extra coverage for memory_core/db.py — functions not hit by existing tests:
  update_quality, prune (dry_run + actual), at_risk_memories, consolidate,
  auto_resolve_conflicts, memory_stats deeper paths.
"""

import os
import sys
import sqlite3
import hashlib
import random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_core.db as mdb

# ── helpers ───────────────────────────────────────────────────────────────────

def _fake_embedding(text: str) -> list:
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    rng  = random.Random(seed)
    return [rng.random() for _ in range(768)]

def _setup_tmp_db(tmp_path):
    db = str(tmp_path / "mem.db")
    orig_path = mdb.DB_PATH
    mdb.DB_PATH = db
    orig_emb   = mdb.get_embedding
    mdb.get_embedding = _fake_embedding
    mdb.init_db()
    return db, orig_path, orig_emb

def _teardown_tmp_db(orig_path, orig_emb):
    mdb.DB_PATH = orig_path
    mdb.get_embedding = orig_emb

def _insert_memory(db, agent, content, quality=1.0, use_count=0):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO memories (timestamp, agent_name, mem_type, content, quality, use_count) "
        "VALUES (datetime('now'), ?, 'chat', ?, ?, ?)",
        (agent, content, quality, use_count),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return row_id


# ── update_quality ────────────────────────────────────────────────────────────

def test_update_quality_empty_list(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        result = mdb.update_quality([], +0.05)
        assert result == 0
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_update_quality_existing_memory(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        mid = _insert_memory(db, "python_dev", "some content", quality=0.8)
        updated = mdb.update_quality([mid], +0.10)
        assert updated == 1
        conn = sqlite3.connect(db)
        q = conn.execute("SELECT quality FROM memories WHERE id=?", (mid,)).fetchone()[0]
        conn.close()
        assert q > 0.8  # quality increased
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_update_quality_negative_delta(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        mid = _insert_memory(db, "python_dev", "content", quality=0.9)
        mdb.update_quality([mid], -0.20)
        conn = sqlite3.connect(db)
        q = conn.execute("SELECT quality FROM memories WHERE id=?", (mid,)).fetchone()[0]
        conn.close()
        assert q < 0.9  # quality decreased
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_update_quality_nonexistent_id(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        updated = mdb.update_quality([99999], +0.05)
        assert updated == 0
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_update_quality_multiple_ids(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        ids = [_insert_memory(db, "python_dev", f"content {i}") for i in range(3)]
        updated = mdb.update_quality(ids, +0.05)
        assert updated == 3
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── prune ─────────────────────────────────────────────────────────────────────

def test_prune_dry_run_no_candidates(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "good content", quality=0.9, use_count=0)
        result = mdb.prune(dry_run=True)
        assert "candidates" in result
        assert result["deleted"] == 0
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_prune_dry_run_finds_candidates(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "low quality", quality=0.30, use_count=0)
        result = mdb.prune(dry_run=True)
        assert len(result["candidates"]) >= 1
        assert result["deleted"] == 0  # dry run — no deletion
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_prune_actual_delete(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "prunable memory", quality=0.30, use_count=0)
        before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        result = mdb.prune(dry_run=False)
        assert result["deleted"] >= 1
        after = sqlite3.connect(db).execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        assert after < before
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_prune_never_deletes_used_memories(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "used but low quality", quality=0.30, use_count=3)
        result = mdb.prune(dry_run=False)
        assert result["deleted"] == 0  # use_count > 0 protects it
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── at_risk_memories ──────────────────────────────────────────────────────────

def test_at_risk_memories_empty(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        result = mdb.at_risk_memories()
        assert isinstance(result, list)
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_at_risk_memories_finds_borderline(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "ai_ml", "borderline memory", quality=0.62, use_count=0)
        result = mdb.at_risk_memories()
        assert any(m["quality"] > 0.55 and m["quality"] <= 0.70 for m in result)
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── memory_stats ──────────────────────────────────────────────────────────────

def test_memory_stats_empty_db(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        stats = mdb.memory_stats()
        assert stats["total"] == 0
        assert stats["prune_candidates"] == 0
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_memory_stats_with_data(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "good content", quality=0.9, use_count=2)
        _insert_memory(db, "it_networking", "net content", quality=0.7, use_count=0)
        _insert_memory(db, "python_dev", "prunable", quality=0.3, use_count=0)
        stats = mdb.memory_stats()
        assert stats["total"] == 3
        assert stats["prune_candidates"] >= 1
        assert "python_dev" in stats["by_agent"]
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── consolidate ───────────────────────────────────────────────────────────────

def test_consolidate_dry_run_empty_db(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        # Empty DB — consolidate returns zero pairs
        result = mdb.consolidate(threshold=0.93, dry_run=True)
        assert "pairs" in result
        assert "removed" in result
        assert result["removed"] == 0
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── auto_resolve_conflicts ────────────────────────────────────────────────────

def test_auto_resolve_conflicts_empty(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        result = mdb.auto_resolve_conflicts(threshold=0.90, dry_run=True)
        assert isinstance(result, dict)
        assert "resolved" in result or "pairs" in result or "candidates" in result
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── _logit_update ─────────────────────────────────────────────────────────────

def test_logit_update_increases_quality():
    q = mdb._logit_update(0.7, 0.1)
    assert q > 0.7

def test_logit_update_decreases_quality():
    q = mdb._logit_update(0.7, -0.1)
    assert q < 0.7

def test_logit_update_bounded():
    q = mdb._logit_update(0.999, 100.0)
    assert q <= 1.0
    q = mdb._logit_update(0.001, -100.0)
    assert q >= 0.0


# ── _normalize ────────────────────────────────────────────────────────────────

def test_normalize_unit_vector():
    import numpy as np
    v = np.array([3.0, 4.0], dtype=np.float32)
    result = mdb._normalize(v)
    assert abs(np.linalg.norm(result) - 1.0) < 1e-5

def test_normalize_zero_vector():
    import numpy as np
    v = np.array([0.0, 0.0], dtype=np.float32)
    result = mdb._normalize(v)
    # Zero vector stays zero (no division by zero)
    assert np.allclose(result, v)


# ── _freshness ────────────────────────────────────────────────────────────────

def test_freshness_recent():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    score = mdb._freshness(now)
    assert score > 0.9  # very recent

def test_freshness_old():
    score = mdb._freshness("2020-01-01T00:00:00+00:00")
    assert score == 0.05  # minimum floor

def test_freshness_invalid_timestamp():
    score = mdb._freshness("not a timestamp")
    assert score == 1.0  # exception fallback


# ── get_recent ────────────────────────────────────────────────────────────────

def test_get_recent_empty(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        result = mdb.get_recent("python_dev", limit=5)
        assert isinstance(result, list)
        assert result == []
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_get_recent_with_data(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        _insert_memory(db, "python_dev", "content A")
        _insert_memory(db, "python_dev", "content B")
        _insert_memory(db, "it_networking", "other content")
        result = mdb.get_recent("python_dev", limit=10)
        assert len(result) == 2
        assert all(r["type"] == "chat" for r in result)
    finally:
        _teardown_tmp_db(orig_path, orig_emb)

def test_get_recent_respects_limit(tmp_path):
    db, orig_path, orig_emb = _setup_tmp_db(tmp_path)
    try:
        for i in range(5):
            _insert_memory(db, "python_dev", f"content {i}")
        result = mdb.get_recent("python_dev", limit=3)
        assert len(result) == 3
    finally:
        _teardown_tmp_db(orig_path, orig_emb)


# ── _select_capped(): episodic retrieval cap (issue #13) ──────────────────────

def _ranked(types):
    """Build a descending-score result list from a list of mem types."""
    return [
        {"id": i, "type": t, "score": round(1.0 - i * 0.01, 4)}
        for i, t in enumerate(types)
    ]

def test_select_capped_limits_episodic():
    # 8 episodic + 4 reflection, ask for 6 → 3 episodic + 3 reflection.
    ranked = _ranked(["episodic"] * 8 + ["reflection"] * 4)
    top = mdb._select_capped(ranked, top_k=6)
    assert len(top) == 6
    assert sum(1 for r in top if r["type"] == "episodic") == mdb._EPISODIC_RETRIEVAL_CAP
    # The higher-signal reflection rows are pulled in despite lower raw rank.
    assert sum(1 for r in top if r["type"] == "reflection") == 3

def test_select_capped_shrinks_when_only_episodic_left():
    # 8 episodic + 2 reflection, ask for 6: cap leaves only 3+2 eligible rows.
    ranked = _ranked(["episodic"] * 8 + ["reflection", "reflection"])
    top = mdb._select_capped(ranked, top_k=6)
    assert len(top) == 5
    assert sum(1 for r in top if r["type"] == "episodic") == mdb._EPISODIC_RETRIEVAL_CAP

def test_select_capped_keeps_order_and_under_cap():
    ranked = _ranked(["episodic", "reflection", "episodic"])
    top = mdb._select_capped(ranked, top_k=5)
    # Under the cap, nothing is dropped and original order is preserved.
    assert [r["id"] for r in top] == [0, 1, 2]

def test_select_capped_bypasses_when_homogeneous():
    # An explicit mem_type="episodic" query is homogeneous → cap must not apply.
    ranked = _ranked(["episodic"] * 5)
    top = mdb._select_capped(ranked, top_k=5)
    assert len(top) == 5


# ── rank_select(): domain-affinity penalty (issue #14) ────────────────────────

def _scored(rows):
    """rows: list of (agent, score) → ranked dict items with chat type."""
    return [
        {"id": i, "agent": a, "type": "chat", "score": s}
        for i, (a, s) in enumerate(rows)
    ]

def _select(items, k, prefer_agent=None):
    return mdb.rank_select(
        items, k,
        score_of=lambda r: r["score"],
        type_of=lambda r: r.get("type"),
        agent_of=lambda r: r.get("agent"),
        prefer_agent=prefer_agent,
    )

def test_affinity_lets_same_domain_overtake():
    # Off-domain memory has higher raw score, but the penalty flips the order.
    items = _scored([("python_dev", 0.90), ("it_networking", 0.80)])
    top = _select(items, k=1, prefer_agent="it_networking")
    # 0.90 * 0.85 = 0.765 < 0.80 → the same-domain memory wins.
    assert top[0]["agent"] == "it_networking"

def test_affinity_keeps_offdomain_when_gap_is_large():
    # A strongly-relevant off-domain memory still survives the penalty.
    items = _scored([("python_dev", 0.95), ("it_networking", 0.60)])
    top = _select(items, k=1, prefer_agent="it_networking")
    # 0.95 * 0.85 = 0.8075 > 0.60 → off-domain stays on top (not excluded).
    assert top[0]["agent"] == "python_dev"

def test_affinity_noop_without_prefer_agent():
    items = _scored([("python_dev", 0.90), ("it_networking", 0.80)])
    top = _select(items, k=2, prefer_agent=None)
    assert [r["agent"] for r in top] == ["python_dev", "it_networking"]

def test_rank_select_applies_both_affinity_and_cap():
    items = (
        [{"id": 0, "agent": "x", "type": "episodic", "score": 0.99},
         {"id": 1, "agent": "x", "type": "episodic", "score": 0.98},
         {"id": 2, "agent": "x", "type": "episodic", "score": 0.97},
         {"id": 3, "agent": "x", "type": "episodic", "score": 0.96},
         {"id": 4, "agent": "it_networking", "type": "reflection", "score": 0.70}]
    )
    top = mdb.rank_select(
        items, k=4,
        score_of=lambda r: r["score"],
        type_of=lambda r: r["type"],
        agent_of=lambda r: r["agent"],
        prefer_agent="it_networking",
    )
    # Episodic capped at 3; the same-domain reflection is retained.
    assert sum(1 for r in top if r["type"] == "episodic") == mdb._EPISODIC_RETRIEVAL_CAP
    assert any(r["id"] == 4 for r in top)
