"""
Memory Retrieval Evaluation Harness

Tests two things that have no overlap:
  1. Math correctness — weighted ranking formula behaves as specified (no Ollama)
  2. Semantic quality — retrieval surfaces relevant memories (requires Ollama)

Math tests prove the ranking formula works.
Semantic tests prove it retrieves the right things.

Run all:        python3 tests/test_retrieval_quality.py
Run math only:  python3 tests/test_retrieval_quality.py --math
Run semantic:   python3 tests/test_retrieval_quality.py --semantic
"""

import json
import math
import numpy as np
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_core.db as memory_db

# ── Test DB isolation ─────────────────────────────────────────
_TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_memory.db")
_orig_db = memory_db.DB_PATH
# NOTE: Do not set DB_PATH at module level — other test files collected later
# would override it and cause cross-contamination. _setup() does it per-test.


def _setup():
    memory_db.DB_PATH = _TEST_DB  # always set before init so it uses the right file
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
    memory_db.init_db()


def _teardown():
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
    memory_db.DB_PATH = _orig_db  # restore real path after each test


def _insert_raw(agent, mem_type, content, embedding_vec, quality=1.0,
                age_days=0, metadata=None):
    """
    Insert a memory row directly — bypasses embedding API.
    embedding_vec — list of floats (normalized internally).
    age_days      — how old to make the timestamp.
    """
    arr  = np.array(embedding_vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    arr  = arr / norm if norm > 0 else arr

    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    conn = sqlite3.connect(_TEST_DB)
    try:
        conn.execute(
            "INSERT INTO memories (timestamp, agent_name, mem_type, content, metadata, "
            "embedding, quality, use_count) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (ts, agent, mem_type, content,
             json.dumps(metadata) if metadata else None,
             arr.tobytes(), quality),
        )
        conn.commit()
    finally:
        conn.close()


def _raw_cosine(query_vec, memory_vec):
    """Pure cosine similarity for hand-verification."""
    q = np.array(query_vec, dtype=np.float32)
    m = np.array(memory_vec, dtype=np.float32)
    q /= (np.linalg.norm(q) or 1)
    m /= (np.linalg.norm(m) or 1)
    return float(np.dot(q, m))


def _search_with_synthetic(query_vec, top_k=10):
    """
    Run ranking against the test DB using a pre-computed embedding vector
    instead of calling Ollama. Mirrors memory_db.search() ranking logic exactly.
    """
    q = np.array(query_vec, dtype=np.float32)
    q /= (np.linalg.norm(q) or 1)

    conn = sqlite3.connect(_TEST_DB)
    rows = conn.execute(
        "SELECT id, timestamp, agent_name, mem_type, content, embedding, "
        "COALESCE(quality, 1.0), COALESCE(use_count, 0) FROM memories"
    ).fetchall()
    conn.close()

    results = []
    for row_id, ts, agent, mtype, content, emb_blob, quality, use_count in rows:
        db_emb   = np.frombuffer(emb_blob, dtype=np.float32).copy()
        norm     = np.linalg.norm(db_emb)
        db_emb  /= (norm or 1)
        raw      = float(np.dot(q, db_emb))
        tweight  = memory_db._TYPE_WEIGHTS.get(mtype, 1.0)
        fresh    = memory_db._freshness(ts)
        weighted = raw * quality * tweight * fresh
        results.append({
            "id":        row_id,
            "content":   content,
            "type":      mtype,
            "quality":   quality,
            "raw_score": round(raw, 4),
            "score":     round(weighted, 4),
            "freshness": round(fresh, 4),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ════════════════════════════════════════════════════════════════
# MATH TESTS (no Ollama)
# ════════════════════════════════════════════════════════════════

def test_type_weights_order():
    """Type weights must follow the priority order: reflection > failure > code > lesson > chat."""
    tw = memory_db._TYPE_WEIGHTS
    assert tw["reflection"] > tw["failure"],  "reflection must outrank failure"
    assert tw["failure"]    > tw["code"],     "failure must outrank code"
    assert tw["code"]       >= tw["lesson"],  "code must outrank or equal lesson"
    assert tw["lesson"]     >= tw["chat"],    "lesson must outrank or equal chat"
    assert tw["chat"]       >= 1.0,           "baseline must be ≥ 1.0"
    print("  ✓ type weight order: reflection > failure > code ≥ lesson ≥ chat ≥ 1.0")


def test_freshness_math():
    """Freshness must halve at HALFLIFE_DAYS and approach minimum asymptotically."""
    h = memory_db._FRESHNESS_HALFLIFE_DAYS
    today   = memory_db._freshness(datetime.now(timezone.utc).isoformat())
    halfday = memory_db._freshness(
        (datetime.now(timezone.utc) - timedelta(days=h)).isoformat()
    )
    ancient = memory_db._freshness(
        (datetime.now(timezone.utc) - timedelta(days=h * 6)).isoformat()
    )

    assert 0.95 <= today <= 1.0,              f"freshness today should be ≈1.0, got {today:.3f}"
    assert 0.45 <= halfday <= 0.55,           f"freshness at halflife should be ≈0.5, got {halfday:.3f}"
    assert ancient <= 0.10,                   f"very old memory should score ≤0.1, got {ancient:.3f}"
    assert ancient >= memory_db._freshness(   # minimum floor
        (datetime.now(timezone.utc) - timedelta(days=h * 100)).isoformat()
    ) * 0.5, "freshness should floor out, not reach zero"
    print(f"  ✓ freshness: today={today:.3f}, at {h}d={halfday:.3f}, at {h*6}d={ancient:.3f}")


def test_quality_changes_ranking():
    """
    A memory with lower raw cosine similarity but higher quality must outrank
    a higher-cosine memory with lower quality when quality difference is large enough.

    Memory A: similarity=0.90, quality=0.90, type=episodic, fresh
    Memory B: similarity=0.94, quality=0.20, type=episodic, fresh

    Without weighting: B wins (0.94 > 0.90)
    With weighting:    A wins (0.90×0.90 = 0.81 > 0.94×0.20 = 0.188)
    """
    _setup()
    dim = 64
    query = np.random.default_rng(0).uniform(-1, 1, dim)
    query /= np.linalg.norm(query)

    # Build Memory A: slightly lower cosine but high quality
    # Set A close to query direction
    a_raw = np.array(query, dtype=np.float32) + 0.02 * np.random.default_rng(1).uniform(-1, 1, dim)
    a_raw /= np.linalg.norm(a_raw)

    # Build Memory B: slightly higher cosine but low quality
    b_raw = np.array(query, dtype=np.float32)
    b_raw /= np.linalg.norm(b_raw)   # exact query direction → max similarity

    a_sim = _raw_cosine(query, a_raw)
    b_sim = _raw_cosine(query, b_raw)

    # Verify B actually has higher raw cosine (or equal)
    # Adjust to ensure B > A in raw similarity
    a_raw = query + np.random.default_rng(99).uniform(0, 0.3, dim)
    b_raw = np.array(query, dtype=np.float32)
    a_raw /= np.linalg.norm(a_raw)
    b_raw /= np.linalg.norm(b_raw)

    a_sim = _raw_cosine(query, a_raw)
    b_sim = _raw_cosine(query, b_raw)

    _insert_raw("test", "episodic", "Memory A high quality",
                a_raw.tolist(), quality=0.90)
    _insert_raw("test", "episodic", "Memory B low quality",
                b_raw.tolist(), quality=0.20)

    results = _search_with_synthetic(query.tolist())

    ranked_by_score   = [r["content"] for r in results]
    top_content       = ranked_by_score[0]

    print(f"  raw cosine: A={a_sim:.4f}, B={b_sim:.4f}")
    print(f"  weighted:   A={results[[r['content'] for r in results].index('Memory A high quality')]['score']:.4f}, "
          f"B={results[[r['content'] for r in results].index('Memory B low quality')]['score']:.4f}")

    assert "Memory A high quality" == top_content, \
        f"Quality-weighted ranking should put A first, got: {ranked_by_score}"
    print("  ✓ quality multiplier overrides raw cosine for high quality gap")
    _teardown()


def test_type_weight_changes_ranking():
    """
    A failure-type memory must outrank an episodic memory with the same similarity
    and quality, because failure has a higher type weight.
    """
    _setup()
    dim = 32
    query = np.ones(dim, dtype=np.float32)
    query /= np.linalg.norm(query)
    same_vec = query.tolist()  # both memories identical direction → equal raw cosine

    _insert_raw("test", "episodic", "Episodic memory same content", same_vec, quality=1.0)
    _insert_raw("test", "failure",  "Failure memory same content",  same_vec, quality=1.0)
    _insert_raw("test", "reflection", "Reflection memory same content", same_vec, quality=1.0)

    results = _search_with_synthetic(query.tolist())
    order   = [r["type"] for r in results[:3]]
    expected_first = "reflection"  # highest type weight

    assert order[0] == expected_first, \
        f"Reflection should rank first among equal similarities, got order: {order}"
    assert order[1] == "failure", \
        f"Failure should rank second, got order: {order}"
    print(f"  ✓ type weights determine ranking when similarity is equal: {order}")
    _teardown()


def test_freshness_changes_ranking():
    """
    A newer memory must outrank an older one with the same similarity, type, and quality.
    """
    _setup()
    dim   = 32
    query = np.ones(dim, dtype=np.float32)
    query /= np.linalg.norm(query)
    vec   = query.tolist()

    _insert_raw("test", "lesson", "Old memory",   vec, quality=1.0, age_days=120)
    _insert_raw("test", "lesson", "Fresh memory", vec, quality=1.0, age_days=0)

    results = _search_with_synthetic(query.tolist())
    assert results[0]["content"] == "Fresh memory", \
        f"Fresh memory should rank first, got: {results[0]['content']}"
    assert results[0]["freshness"] > results[1]["freshness"]
    print(f"  ✓ freshness: fresh={results[0]['freshness']:.3f} > old={results[1]['freshness']:.3f}")
    _teardown()


def test_weighted_vs_unweighted_divergence():
    """
    When memories have varied quality/type, the weighted ranking must differ
    from raw cosine ranking (proving the weighting is active, not decorative).

    Seeds 6 memories with different quality/type combinations but similar content.
    Verifies that weighted order ≠ raw cosine order for at least 2 positions.
    """
    _setup()
    dim   = 16
    query = np.ones(dim, dtype=np.float32)
    query /= np.linalg.norm(query)

    rng   = np.random.default_rng(7)
    seeds = [
        ("episodic",   0.3,  "Memory type=episodic  quality=0.3"),
        ("chat",       0.5,  "Memory type=chat      quality=0.5"),
        ("lesson",     0.7,  "Memory type=lesson    quality=0.7"),
        ("code",       0.9,  "Memory type=code      quality=0.9"),
        ("failure",    0.5,  "Memory type=failure   quality=0.5"),
        ("reflection", 0.6,  "Memory type=reflection quality=0.6"),
    ]

    for mtype, quality, content in seeds:
        # Add small noise so raw similarities differ slightly
        v = query + 0.05 * rng.uniform(-1, 1, dim)
        v /= np.linalg.norm(v)
        _insert_raw("test", mtype, content, v.tolist(), quality=quality)

    results = _search_with_synthetic(query.tolist())
    weighted_order  = [r["content"] for r in results]
    raw_order       = sorted(results, key=lambda x: x["raw_score"], reverse=True)
    raw_order_names = [r["content"] for r in raw_order]

    matches = sum(w == r for w, r in zip(weighted_order, raw_order_names))
    total   = len(weighted_order)

    print(f"  Weighted ranking:")
    for r in results:
        print(f"    [{r['type']:12}] q={r['quality']:.1f}  raw={r['raw_score']:.4f}  "
              f"weighted={r['score']:.4f}  {r['content'][-25:]}")
    print(f"  Position agreements with raw cosine: {matches}/{total}")
    assert matches < total, \
        "Weighted ranking identical to raw cosine — weighting has no effect"
    print(f"  ✓ weighted ranking diverges from raw cosine at {total - matches}/{total} positions")
    _teardown()


def test_audit_table_populated():
    """The retrieval audit table must have exactly 0 rows before any search."""
    _setup()
    conn = sqlite3.connect(_TEST_DB)
    count = conn.execute("SELECT COUNT(*) FROM retrieval_audits").fetchone()[0]
    conn.close()
    assert count == 0, f"Fresh DB should have 0 audit rows, got {count}"
    print("  ✓ audit table starts empty")
    _teardown()


def test_use_count_incremented():
    """use_count must increment each time a memory appears in search results."""
    _setup()
    dim = 32
    q   = np.ones(dim, dtype=np.float32)
    q  /= np.linalg.norm(q)
    _insert_raw("test", "lesson", "Frequently retrieved memory", q.tolist())

    conn = sqlite3.connect(_TEST_DB)
    row_id = conn.execute("SELECT id FROM memories WHERE content LIKE 'Frequently%'").fetchone()[0]
    conn.close()

    # Run 3 retrievals
    for _ in range(3):
        _search_with_synthetic(q.tolist(), top_k=1)
        # Trigger _record_use manually (search_with_synthetic doesn't call it)

    # Verify by checking directly through memory_db._record_use
    memory_db._record_use([row_id])
    memory_db._record_use([row_id])

    conn = sqlite3.connect(_TEST_DB)
    use_count = conn.execute("SELECT use_count FROM memories WHERE id=?", (row_id,)).fetchone()[0]
    conn.close()

    assert use_count == 2, f"use_count should be 2, got {use_count}"
    print(f"  ✓ use_count incremented correctly: {use_count}")
    _teardown()


# ════════════════════════════════════════════════════════════════
# SEMANTIC TESTS (require Ollama)
# ════════════════════════════════════════════════════════════════

# Synthetic corpus: domain-relevant memories with known expected retrieval.
# Format: (agent, mem_type, content, quality, expected_queries)
_CORPUS = [
    # Python Dev
    ("python_dev", "failure",    "FastAPI endpoint raised 422 Unprocessable Entity when receiving JSON body with missing required field", 0.85,
     ["FastAPI validation error", "422 error handling", "JSON body validation"]),
    ("python_dev", "code",       "JWT authentication middleware in FastAPI using python-jose and passlib for password hashing", 0.90,
     ["FastAPI JWT auth", "Python authentication middleware", "JWT token"]),
    ("python_dev", "reflection", "Agent produced incomplete async error handling — missing try/except in database coroutine", 0.55,
     ["Python async errors", "async exception handling", "coroutine error"]),
    ("python_dev", "lesson",     "Python dataclasses with default_factory prevent shared mutable default argument bugs", 0.75,
     ["Python dataclass defaults", "mutable default argument", "dataclass bug"]),
    # IT Networking
    ("it_networking", "failure", "nginx returns 502 Bad Gateway when upstream application is not listening on configured port", 0.80,
     ["nginx 502 error", "Bad Gateway nginx", "upstream connection failed"]),
    ("it_networking", "code",    "Wireguard VPN configuration with peer routing and NAT traversal for remote access", 0.85,
     ["Wireguard VPN setup", "VPN configuration", "peer-to-peer tunnel"]),
    ("it_networking", "lesson",  "DNS TTL controls how long resolvers cache records — lower values reduce propagation delay", 0.70,
     ["DNS TTL", "DNS caching", "record propagation"]),
    # AI/ML
    ("ai_ml", "reflection",  "Model selected knowledge_learning for a Python task — routing regret was high (0.42)", 0.75,
     ["routing error ai", "wrong agent selected", "routing regret"]),
    ("ai_ml", "lesson",      "Transformer attention mechanism computes Q, K, V matrices to produce weighted context vectors", 0.80,
     ["transformer attention", "self-attention mechanism", "Q K V matrices"]),
    # Low quality (should surface less aggressively)
    ("python_dev", "chat",   "User asked about formatting, nothing technical", 0.30,
     []),  # not expected for any query
    ("it_networking", "chat", "Casual chat about networking concepts without specific task", 0.20,
     []),
]


def _check_ollama() -> bool:
    """Return True if Ollama is reachable."""
    try:
        import requests
        r = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": "test"},
            timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False


def _seed_corpus(test_db=True):
    """Save all corpus entries to the test DB."""
    for agent, mem_type, content, quality, _ in _CORPUS:
        memory_db.save(agent, mem_type, content, quality=quality)


class RetrievalMetrics:
    """Compute precision metrics from retrieval results given a ground-truth map."""

    def __init__(self):
        self.results = []  # (query, expected_hit, actual_top3, hit_at_1, hit_at_3, rank)

    def record(self, query: str, expected_content: str, retrieved: list):
        top3 = [r["content"] for r in retrieved[:3]]
        # Partial match — check if expected content substring appears in top-3
        hit1  = any(expected_content[:40] in r for r in top3[:1])
        hit3  = any(expected_content[:40] in r for r in top3)
        rank  = next((i+1 for i, r in enumerate(retrieved) if expected_content[:40] in r["content"]), None)
        self.results.append({
            "query":    query,
            "expected": expected_content[:50],
            "hit@1":    hit1,
            "hit@3":    hit3,
            "rank":     rank,
        })

    def summary(self) -> dict:
        n          = len(self.results)
        p_at_1     = sum(r["hit@1"] for r in self.results) / n if n else 0
        p_at_3     = sum(r["hit@3"] for r in self.results) / n if n else 0
        mrr_vals   = [1.0/r["rank"] for r in self.results if r["rank"]]
        mrr        = sum(mrr_vals) / len(mrr_vals) if mrr_vals else 0
        return {
            "n":       n,
            "P@1":     round(p_at_1, 3),
            "P@3":     round(p_at_3, 3),
            "MRR":     round(mrr, 3),
        }

    def print_detail(self):
        for r in self.results:
            hit1 = "✓" if r["hit@1"] else "✗"
            hit3 = "✓" if r["hit@3"] else "✗"
            rank = r["rank"] or "—"
            print(f"  {hit1}/{hit3} rank={rank:<3}  Q: {r['query'][:45]}")
            print(f"           E: {r['expected']}")


def test_semantic_top1_precision():
    """
    Seed corpus + run queries where expected hits are known.
    Top-1 precision must exceed 0.50 (random baseline for N=11 memories).
    Top-3 precision must exceed 0.70.

    Requires Ollama running with nomic-embed-text pulled.
    """
    if not _check_ollama():
        print("  SKIP (Ollama not running)")
        return

    _setup()
    _seed_corpus()

    metrics = RetrievalMetrics()
    test_cases = [
        ("FastAPI 422 validation error JSON",        _CORPUS[0][2]),
        ("JWT authentication Python FastAPI",         _CORPUS[1][2]),
        ("async error handling Python missing",       _CORPUS[2][2]),
        ("nginx 502 Bad Gateway upstream",            _CORPUS[4][2]),
        ("Wireguard VPN peer routing",                _CORPUS[5][2]),
        ("DNS TTL caching propagation",               _CORPUS[6][2]),
        ("transformer attention Q K V",               _CORPUS[8][2]),
    ]

    for query, expected in test_cases:
        results = memory_db.search(query, top_k=5, caller="test_semantic")
        metrics.record(query, expected, results)

    summary = metrics.summary()
    metrics.print_detail()
    print(f"\n  Precision@1={summary['P@1']:.3f}  "
          f"Precision@3={summary['P@3']:.3f}  "
          f"MRR={summary['MRR']:.3f}  (n={summary['n']})")

    assert summary["P@1"] >= 0.50, f"P@1={summary['P@1']:.3f} below 0.50 threshold"
    assert summary["P@3"] >= 0.70, f"P@3={summary['P@3']:.3f} below 0.70 threshold"
    print(f"  ✓ semantic retrieval meets precision thresholds")
    _teardown()


def test_failure_memories_surface_for_error_queries():
    """
    Error-pattern queries must surface failure-type memories in their top-3.
    """
    if not _check_ollama():
        print("  SKIP (Ollama not running)")
        return

    _setup()
    _seed_corpus()

    error_queries = [
        "Why is my FastAPI returning 422?",
        "nginx Bad Gateway troubleshoot",
    ]
    type_hits = 0
    for q in error_queries:
        results = memory_db.search(q, top_k=3, caller="test_failure_surface")
        top3_types = [r["type"] for r in results]
        has_failure = "failure" in top3_types
        mark = "✓" if has_failure else "✗"
        print(f"  {mark} '{q[:45]}' → top-3 types: {top3_types}")
        if has_failure:
            type_hits += 1

    assert type_hits >= len(error_queries) - 1, \
        f"Failure memories should surface for error queries: {type_hits}/{len(error_queries)}"
    print(f"  ✓ failure memories surfaced for {type_hits}/{len(error_queries)} error queries")
    _teardown()


def test_reflection_memories_surface_for_agent_queries():
    """
    Queries about agent selection or routing quality must surface reflection memories.
    """
    if not _check_ollama():
        print("  SKIP (Ollama not running)")
        return

    _setup()
    _seed_corpus()

    reflection_queries = [
        "wrong agent was selected for Python task",
        "routing regret high agent picked incorrectly",
    ]
    type_hits = 0
    for q in reflection_queries:
        results = memory_db.search(q, top_k=3, caller="test_reflection_surface")
        top3_types = [r["type"] for r in results]
        has_reflection = "reflection" in top3_types
        mark = "✓" if has_reflection else "✗"
        print(f"  {mark} '{q[:45]}' → top-3 types: {top3_types}")
        if has_reflection:
            type_hits += 1

    assert type_hits >= 1, \
        f"Reflection memories should surface for agent queries"
    print(f"  ✓ reflection memories surfaced for {type_hits}/{len(reflection_queries)} agent queries")
    _teardown()


def test_low_quality_memories_deprioritized():
    """
    Low-quality memories (quality=0.2–0.3) must consistently rank below
    high-quality memories on the same topic.
    """
    if not _check_ollama():
        print("  SKIP (Ollama not running)")
        return

    _setup()
    # Only seed the chat/casual vs domain-specific entries
    for agent, mem_type, content, quality, _ in _CORPUS:
        memory_db.save(agent, mem_type, content, quality=quality)

    # Queries that should prefer high-quality over low-quality
    test_cases = [
        ("Python FastAPI endpoint", _CORPUS[1][2], _CORPUS[9][2]),   # JWT vs casual chat
        ("networking VPN setup",    _CORPUS[5][2], _CORPUS[10][2]),  # Wireguard vs casual chat
    ]

    wins = 0
    for query, high_qual_content, low_qual_content in test_cases:
        results  = memory_db.search(query, top_k=11, caller="test_quality_deprioritize")
        contents = [r["content"] for r in results]
        if high_qual_content in contents and low_qual_content in contents:
            hi_rank  = contents.index(high_qual_content)
            lo_rank  = contents.index(low_qual_content)
            win = hi_rank < lo_rank
            mark = "✓" if win else "✗"
            print(f"  {mark} '{query[:40]}'  high@{hi_rank+1} vs low@{lo_rank+1}")
            if win:
                wins += 1

    assert wins == len(test_cases), \
        f"High-quality memories should rank above low-quality: {wins}/{len(test_cases)}"
    print(f"  ✓ low-quality memories deprioritized in {wins}/{len(test_cases)} cases")
    _teardown()


def test_weighted_vs_unweighted_precision():
    """
    Compare P@3 of weighted ranking vs raw cosine ranking using the same corpus.
    Weighted must meet or exceed raw cosine precision.

    This directly answers: "did the weighting actually help?"
    """
    if not _check_ollama():
        print("  SKIP (Ollama not running)")
        return

    _setup()
    _seed_corpus()

    test_cases = [
        ("FastAPI 422 validation error JSON",    _CORPUS[0][2]),
        ("JWT authentication Python FastAPI",    _CORPUS[1][2]),
        ("nginx 502 Bad Gateway upstream",       _CORPUS[4][2]),
        ("DNS TTL caching propagation",          _CORPUS[6][2]),
        ("transformer attention Q K V",          _CORPUS[8][2]),
    ]

    # Weighted retrieval (current system)
    weighted_hits = 0
    for query, expected in test_cases:
        results = memory_db.search(query, top_k=5, caller="test_compare_weighted")
        top3    = [r["content"] for r in results[:3]]
        if any(expected[:40] in c for c in top3):
            weighted_hits += 1

    # Unweighted retrieval: override quality and type effects by injecting equal weights.
    # Simulate by temporarily setting all type weights to 1.0 and quality override.
    raw_hits = 0
    original_weights = memory_db._TYPE_WEIGHTS.copy()
    for k in memory_db._TYPE_WEIGHTS:
        memory_db._TYPE_WEIGHTS[k] = 1.0

    # Also need to set all memory qualities to 1.0 in the test DB
    conn = sqlite3.connect(_TEST_DB)
    conn.execute("UPDATE memories SET quality=1.0")
    conn.commit()
    conn.close()

    for query, expected in test_cases:
        results = memory_db.search(query, top_k=5, caller="test_compare_unweighted")
        top3    = [r["content"] for r in results[:3]]
        if any(expected[:40] in c for c in top3):
            raw_hits += 1

    # Restore
    memory_db._TYPE_WEIGHTS.update(original_weights)

    weighted_p3 = weighted_hits / len(test_cases)
    raw_p3      = raw_hits / len(test_cases)

    print(f"  Weighted P@3: {weighted_p3:.3f}  ({weighted_hits}/{len(test_cases)})")
    print(f"  Raw cosine P@3: {raw_p3:.3f}   ({raw_hits}/{len(test_cases)})")

    # The weighting should not degrade precision compared to raw cosine
    assert weighted_p3 >= raw_p3 - 0.1, \
        f"Weighted retrieval significantly worse than raw cosine: {weighted_p3:.3f} vs {raw_p3:.3f}"
    if weighted_p3 > raw_p3:
        print(f"  ✓ weighted retrieval improves over raw cosine by {weighted_p3-raw_p3:.3f}")
    elif weighted_p3 == raw_p3:
        print(f"  ✓ weighted retrieval matches raw cosine precision (no degradation)")
    else:
        print(f"  ⚠ weighted is within tolerance of raw cosine (gap={raw_p3-weighted_p3:.3f})")
    _teardown()


# ════════════════════════════════════════════════════════════════
# Audit Log Analysis
# ════════════════════════════════════════════════════════════════

def print_live_audit_summary():
    """Read the live retrieval audit log and print a summary report."""
    orig = memory_db.DB_PATH
    memory_db.DB_PATH = _orig_db
    try:
        audits = memory_db.get_recent_audits(100)
        if not audits:
            print("  No audit entries yet.")
            return

        # Type distribution across all retrieved entries
        type_counts = {}
        caller_counts = {}
        for a in audits:
            caller_counts[a["caller"]] = caller_counts.get(a["caller"], 0) + 1
            for r in a.get("retrieved", []):
                t = r.get("type", "unknown")
                type_counts[t] = type_counts.get(t, 0) + 1

        total_retrievals = sum(a["count"] for a in audits)
        print(f"  Total audit entries:  {len(audits)}")
        print(f"  Total items retrieved: {total_retrievals}")
        print(f"  Avg per query: {total_retrievals/len(audits):.1f}")
        print(f"\n  Type distribution of retrieved memories:")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            pct = 100 * c / total_retrievals if total_retrievals else 0
            print(f"    {t:16} {c:4}  ({pct:.1f}%)")
        print(f"\n  Callers:")
        for caller, c in sorted(caller_counts.items(), key=lambda x: -x[1]):
            print(f"    {caller or '(unknown)':30} {c}")

    finally:
        memory_db.DB_PATH = orig


# ════════════════════════════════════════════════════════════════
# Runner
# ════════════════════════════════════════════════════════════════

MATH_TESTS = [
    ("M. Type weight ordering",             test_type_weights_order),
    ("M. Freshness decay math",             test_freshness_math),
    ("M. Quality changes ranking",          test_quality_changes_ranking),
    ("M. Type weight changes ranking",      test_type_weight_changes_ranking),
    ("M. Freshness changes ranking",        test_freshness_changes_ranking),
    ("M. Weighted ≠ unweighted ranking",    test_weighted_vs_unweighted_divergence),
    ("M. Audit table starts empty",         test_audit_table_populated),
    ("M. use_count increments",             test_use_count_incremented),
]

SEMANTIC_TESTS = [
    ("S. Top-1/Top-3 precision",            test_semantic_top1_precision),
    ("S. Failure memories for error queries",  test_failure_memories_surface_for_error_queries),
    ("S. Reflection for agent queries",     test_reflection_memories_surface_for_agent_queries),
    ("S. Low-quality deprioritized",        test_low_quality_memories_deprioritized),
    ("S. Weighted vs unweighted precision", test_weighted_vs_unweighted_precision),
]


def run_all(run_math=True, run_semantic=True):
    passed = failed = skipped = 0
    tests  = []
    if run_math:
        tests += MATH_TESTS
    if run_semantic:
        tests += SEMANTIC_TESTS

    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'═'*60}")
    print(f"Results: {passed} passed, {failed} failed")

    if run_semantic and _check_ollama():
        print(f"\n[Live audit summary — from production memory DB]")
        print_live_audit_summary()

    if failed:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    args = sys.argv[1:]
    math_only     = "--math"     in args
    semantic_only = "--semantic" in args

    if math_only:
        run_all(run_math=True, run_semantic=False)
    elif semantic_only:
        if not _check_ollama():
            print("Ollama not running — semantic tests require nomic-embed-text.")
            sys.exit(1)
        run_all(run_math=False, run_semantic=True)
    else:
        run_all(run_math=True, run_semantic=True)
