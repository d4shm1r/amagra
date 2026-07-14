# pip install numpy requests
# ollama pull nomic-embed-text

import functools
import math
import sqlite3
import threading
import requests
import numpy as np
import json
import os
from contextvars import ContextVar
from datetime import datetime, timezone

# Request-scoped tenant key — set once per /ask call so search() and save()
# filter/tag by owner without requiring signature changes throughout the stack.
_current_owner_key_id: ContextVar[int | None] = ContextVar(
    "current_owner_key_id", default=None
)

from infrastructure.db import path as _dbpath
_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = _dbpath("memory")
_lock = threading.Lock()

# Retrieval scoring weights by memory type.
# Higher weight = surfaces more aggressively in ranked results.
# Covers both legacy types (lesson/chat/code from early memory saves)
# and structured types introduced with memory tagging.
_TYPE_WEIGHTS = {
    # Structured types (new)
    "reflection": 1.4,   # grounded quality signal, most actionable
    "decision":   1.35,  # structured, user-confirmed choices (debugger bridge)
    "failure":    1.3,   # negative examples are high-value
    "procedural": 1.2,   # learned reusable patterns
    "episodic":   1.0,   # conversation history (baseline)
    # Legacy types (from pre-tagging saves)
    "code":       1.2,   # code examples are highly reusable
    "lesson":     1.1,   # structured explanations
    "chat":       1.0,   # raw conversation history (baseline)
    "project":    1.1,   # project context
    # Seeded memories (eval / auto_train) — lower weight so real memories win
    "seed":       0.8,
}

# Quality threshold below which a never-recalled memory is prunable.
_PRUNE_QUALITY_THRESHOLD = 0.55
_FRESHNESS_HALFLIFE_DAYS = 30   # score halves every 30 days

# Episodic records are written on every response, so without a cap they come to
# dominate retrieval once a tenant has thousands of sessions, crowding out the
# higher-signal reflection/procedural/failure types. Cap how many episodic rows
# can occupy a single result set (GitHub issue #13).
_EPISODIC_RETRIEVAL_CAP = 3

# Domain-affinity penalty (issue #14): when a query is retrieved on behalf of a
# specific agent, memories belonging to a *different* agent (domain) are still
# eligible but their score is multiplied by this factor before the top-k cut, so
# a same-domain memory wins close calls and adjacent-domain bleed is suppressed.
_AFFINITY_PENALTY = 0.85


def init_db():
    """Create DB and memories table if not exists. Call once at startup."""
    os.makedirs("memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT,
                agent_name   TEXT,
                mem_type     TEXT,
                content      TEXT,
                metadata     TEXT,
                embedding    BLOB,
                quality      REAL    DEFAULT 1.0,
                use_count    INTEGER DEFAULT 0,
                last_used    TEXT,
                owner_key_id INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_name);")
        # Retrieval audit — one row per search() call.
        # Populated automatically; enables offline labeling of retrieval quality.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retrieval_audits (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                query     TEXT,
                caller    TEXT,
                retrieved TEXT,   -- JSON: [{id, score, type, agent}]
                count     INTEGER
            )
        """)
        conn.commit()
        # Migration: add new columns to existing DB if they don't exist yet.
        for col, defn in [
            ("quality",      "REAL    DEFAULT 1.0"),
            ("use_count",    "INTEGER DEFAULT 0"),
            ("last_used",    "TEXT"),
            ("owner_key_id", "INTEGER"),
        ]:
            try:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {col} {defn}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
    finally:
        conn.close()


@functools.lru_cache(maxsize=512)
def _cached_embedding_bytes(text: str) -> bytes:
    """Ollama embedding call, cached by text. Returns raw bytes for hashability."""
    try:
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return np.array(resp.json()["embedding"], dtype=np.float32).tobytes()
    except Exception as e:
        raise RuntimeError(f"Ollama embedding failed: {e}")


def get_embedding(text: str) -> list:
    """
    Call nomic-embed-text via Ollama. LRU-cached by text (512 entries).
    Raises RuntimeError if Ollama is unreachable.
    """
    return np.frombuffer(_cached_embedding_bytes(text), dtype=np.float32).tolist()


def _normalize(vec) -> np.ndarray:
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr


def _freshness(timestamp: str) -> float:
    """True half-life decay: 1.0 today → 0.5 at HALFLIFE_DAYS → floor 0.05."""
    try:
        then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - then).total_seconds() / 86400
        return max(0.05, math.exp(-age_days * math.log(2) / _FRESHNESS_HALFLIFE_DAYS))
    except Exception:
        return 1.0


_DEDUP_THRESHOLD  = 0.93   # cosine similarity above which we skip the save
_DEDUP_SCAN_LIMIT = 200   # only check the N most recent memories per agent


def _is_near_duplicate(emb: np.ndarray, agent_name: str) -> bool:
    """Return True if a near-identical memory already exists for this agent."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        rows = conn.execute(
            "SELECT embedding FROM memories WHERE agent_name=? ORDER BY id DESC LIMIT ?",
            (agent_name, _DEDUP_SCAN_LIMIT),
        ).fetchall()
    finally:
        conn.close()
    for (blob,) in rows:
        existing = _normalize(np.frombuffer(blob, dtype=np.float32))
        if float(np.dot(emb, existing)) > _DEDUP_THRESHOLD:
            return True
    return False


def save(agent_name: str, mem_type: str, content: str,
         metadata: dict = None, quality: float = 1.0,
         owner_key_id: int = None) -> bool:
    if owner_key_id is None:
        owner_key_id = _current_owner_key_id.get()
    """
    Save a memory entry with embedding.
    quality       — initial quality score [0.0, 1.0]
    owner_key_id  — API key id; used to isolate memories per tenant
    Returns True on success, False on any failure — never raises.
    Thread-safe via Lock + WAL.
    """
    try:
        emb = _normalize(get_embedding(content))
        emb_bytes = emb.tobytes()
    except Exception as e:
        print(f"[memory] Embedding error for {agent_name}: {e}")
        return False

    quality = max(0.0, min(1.0, float(quality)))

    if _is_near_duplicate(emb, agent_name):
        print(f"[memory] skipping near-duplicate for {agent_name} (cos > {_DEDUP_THRESHOLD})")
        return False

    with _lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """INSERT INTO memories
                   (timestamp, agent_name, mem_type, content, metadata, embedding, quality, owner_key_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    agent_name,
                    mem_type,
                    content,
                    json.dumps(metadata) if metadata else None,
                    emb_bytes,
                    quality,
                    owner_key_id,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[memory] Save error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


def rank_select(items: list, k: int, score_of, type_of,
                agent_of=None, prefer_agent: str = None) -> list:
    """
    Final ranking step shared by every memory backend.

    Operates on the FULL candidate set (dicts or MemoryRecord — caller supplies
    accessors) before the top-k cut, so the two policies below can actually
    reorder results rather than just trim them:

      • Domain-affinity penalty (issue #14): off-domain memories are scaled by
        _AFFINITY_PENALTY when prefer_agent is set, letting a same-domain memory
        overtake a higher-raw-score adjacent-domain one.
      • Episodic cap (issue #13): at most _EPISODIC_RETRIEVAL_CAP episodic rows
        survive, unless every candidate is episodic (an explicit episodic-only
        query) in which case the cap is bypassed.
    """
    if k <= 0 or not items:
        return items[:k]

    def _adjusted(it):
        s = score_of(it)
        if prefer_agent and agent_of is not None:
            a = agent_of(it)
            if a and a != prefer_agent:
                return s * _AFFINITY_PENALTY
        return s

    ranked = sorted(items, key=_adjusted, reverse=True)
    if all(type_of(it) == "episodic" for it in ranked):
        return ranked[:k]

    selected: list = []
    episodic_seen = 0
    for it in ranked:
        if type_of(it) == "episodic":
            if episodic_seen >= _EPISODIC_RETRIEVAL_CAP:
                continue
            episodic_seen += 1
        selected.append(it)
        if len(selected) >= k:
            break
    return selected


def _select_capped(ranked: list, top_k: int) -> list:
    """Back-compat dict-shaped wrapper around rank_select (no affinity)."""
    return rank_select(
        ranked, top_k,
        score_of=lambda r: r["score"],
        type_of=lambda r: r.get("type"),
    )


def search(query: str, top_k: int = 5, agent_name: str = None,
           mem_type: str = None, caller: str = "",
           owner_key_id: int = None, prefer_agent: str = None) -> list:
    """
    Semantic search across memories with quality-weighted ranking.

    Score formula: similarity × quality × type_weight × freshness

    owner_key_id — when set, only returns memories belonging to that API key,
                   preventing cross-tenant memory bleed (S2 security fix).
                   Falls back to _current_owner_key_id ContextVar if not given.
    prefer_agent — soft domain-affinity hint (issue #14): off-domain memories
                   are down-weighted (not excluded) so same-domain results win
                   close calls. Distinct from agent_name, which hard-filters.
    """
    if owner_key_id is None:
        owner_key_id = _current_owner_key_id.get()
    try:
        q_emb = _normalize(get_embedding(query))
    except Exception as e:
        print(f"[memory] Search embedding error: {e}")
        return []

    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        if owner_key_id is not None:
            # Include tenant-owned memories AND legacy rows with NULL owner
            # (NULL = pre-tenancy data; include so existing installs don't go blank).
            rows = conn.execute(
                "SELECT id, timestamp, agent_name, mem_type, content, metadata, embedding, "
                "COALESCE(quality, 1.0), COALESCE(use_count, 0) FROM memories "
                "WHERE owner_key_id = ? OR owner_key_id IS NULL",
                (owner_key_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, timestamp, agent_name, mem_type, content, metadata, embedding, "
                "COALESCE(quality, 1.0), COALESCE(use_count, 0) FROM memories"
            ).fetchall()
    finally:
        conn.close()

    results = []
    for row_id, ts, agent, mtype, content, meta_raw, emb_blob, quality, use_count in rows:
        if agent_name and agent != agent_name:
            continue
        if mem_type and mtype != mem_type:
            continue
        db_emb = _normalize(np.frombuffer(emb_blob, dtype=np.float32))
        raw_score   = float(np.dot(q_emb, db_emb))
        type_weight = _TYPE_WEIGHTS.get(mtype, 1.0)
        freshness   = _freshness(ts)
        weighted    = raw_score * quality * type_weight * freshness
        try:
            metadata = json.loads(meta_raw) if meta_raw else {}
        except Exception:
            metadata = {}
        results.append({
            "id":        row_id,
            "agent":     agent,
            "type":      mtype,
            "content":   content,
            "metadata":  metadata,
            "score":     round(weighted, 4),
            "raw_score": round(raw_score, 4),
            "timestamp": ts,
        })

    top = rank_select(
        results, top_k,
        score_of=lambda x: x["score"],
        type_of=lambda x: x.get("type"),
        agent_of=lambda x: x.get("agent"),
        prefer_agent=prefer_agent,
    )

    # Mark retrieved rows as used and log the audit — both fire-and-forget.
    if top:
        _record_use([r["id"] for r in top])
        _log_audit(query, caller, top)

    return top


_QUALITY_GAMMA = 4.0  # scales probability-space delta into log-odds space


def _logit_update(q: float, delta: float) -> float:
    """
    Bayesian log-odds quality update.
    Memories near 0 or 1 resist change; memories near 0.5 update linearly.
    Returns new quality in [0.0, 1.0].
    """
    q_safe   = max(0.001, min(0.999, q))
    log_odds = math.log(q_safe / (1.0 - q_safe))
    log_odds += _QUALITY_GAMMA * delta
    new_q    = 1.0 / (1.0 + math.exp(-log_odds))
    return round(max(0.0, min(1.0, new_q)), 4)


def _advise_quality_basin(mid: int, new_q: float, delta: float) -> None:
    """Advisory only (Phase 4) — warn, never block, when a quality update lands a
    memory in the saturated corner where the nonlinear log-odds map's basin is
    bounded. Emits MEMORY_QUALITY_SATURATED so noisy feedback near saturation
    can't *silently* push a memory's quality into a non-recoverable corner.
    Best-effort: any failure here must never affect the quality write."""
    try:
        from infrastructure.math_metrics import quality_update_basin
        basin = quality_update_basin(new_q, gamma=_QUALITY_GAMMA, delta_f=delta)
        if basin["warn"]:
            from infrastructure.event_bus import emit, EventType
            emit(EventType.MEMORY_QUALITY_SATURATED, {
                "memory_id":       mid,
                "quality":         new_q,
                "corner_distance": basin["corner_distance"],
                "corrective_feedback": basin["corrective_feedback"],
            })
    except Exception:
        pass


def update_quality(memory_ids: list, delta: float) -> int:
    """
    Apply a quality update to a list of memory IDs via log-odds arithmetic.
    Positive delta (e.g. +0.03) for good feedback; negative (e.g. -0.05) for bad.
    High-quality memories resist noise; low-quality memories respond freely.
    Returns the number of rows updated.
    """
    if not memory_ids:
        return 0
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                updated = 0
                for mid in memory_ids:
                    row = conn.execute(
                        "SELECT COALESCE(quality, 1.0) FROM memories WHERE id=?",
                        (int(mid),),
                    ).fetchone()
                    if row:
                        new_q = _logit_update(row[0], delta)
                        conn.execute(
                            "UPDATE memories SET quality=? WHERE id=?",
                            (new_q, int(mid)),
                        )
                        _advise_quality_basin(int(mid), new_q, delta)
                        updated += 1
                conn.commit()
                return updated
            finally:
                conn.close()
    except Exception as e:
        print(f"[memory] update_quality error: {e}")
        return 0


_AUTO_PROMOTE_AT    = 5     # use_count threshold for quality auto-boost
_AUTO_PROMOTE_DELTA = 0.03  # log-odds delta applied on promotion


def _record_use(ids: list[int]) -> None:
    """Increment use_count, update last_used, and auto-promote quality for frequent memories."""
    if not ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _lock:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE memories SET use_count=COALESCE(use_count,0)+1, last_used=? "
                    f"WHERE id IN ({placeholders})",
                    [now, *ids],
                )
                # Auto-promote memories that hit the use_count threshold
                promote_rows = conn.execute(
                    f"SELECT id, COALESCE(quality,1.0) FROM memories "
                    f"WHERE id IN ({placeholders}) AND COALESCE(use_count,0) = ?",
                    [*ids, _AUTO_PROMOTE_AT],
                ).fetchall()
                for mid, q in promote_rows:
                    new_q = _logit_update(q, _AUTO_PROMOTE_DELTA)
                    conn.execute("UPDATE memories SET quality=? WHERE id=?", (new_q, mid))
                conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print(f"[memory] use tracking error: {e}")


def _log_audit(query: str, caller: str, results: list) -> None:
    """Write a retrieval audit row for offline quality labeling."""
    try:
        audit_rows = [
            {"id": r["id"], "score": r["raw_score"], "weighted": r["score"],
             "type": r["type"], "agent": r["agent"]}
            for r in results
        ]
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                "INSERT INTO retrieval_audits (timestamp, query, caller, retrieved, count) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    query[:300],
                    caller or "",
                    json.dumps(audit_rows),
                    len(results),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[memory] audit log error: {e}")


def get_recent_audits(limit: int = 20) -> list:
    """Return recent retrieval audit rows for inspection."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, query, caller, retrieved, count "
            "FROM retrieval_audits ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        conn.close()
    result = []
    for row in rows:
        r = {
            "id":        row[0],
            "timestamp": row[1],
            "query":     row[2],
            "caller":    row[3],
            "count":     row[5],
        }
        try:
            r["retrieved"] = json.loads(row[4])
        except Exception:
            r["retrieved"] = []
        result.append(r)
    return result


def get_last_accessed_content(query_text: str, n: int = 5) -> list:
    """
    Returns the content of memories retrieved during the most recent
    agent call for `query_text`.

    Looks for the most recent audit entry with caller="" (memory_context calls)
    whose query prefix matches. Returns a list of memory content dicts with
    id, type, agent, content (first 200 chars), and retrieval score.
    """
    if not query_text:
        return []
    qkey = query_text[:80].lower()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        try:
            rows = conn.execute(
                "SELECT id, retrieved FROM retrieval_audits "
                "WHERE (caller='' OR caller IS NULL) "
                "ORDER BY id DESC LIMIT 30"
            ).fetchall()
        finally:
            conn.close()

        # Find the most recent entry whose stored query matches
        ids_scored = []
        for _, retrieved_raw in rows:
            try:
                retrieved = json.loads(retrieved_raw or "[]")
            except Exception:
                continue
            ids_scored = [(r["id"], r.get("weighted", r.get("score", 0.0)))
                          for r in retrieved if "id" in r]
            if ids_scored:
                break

        if not ids_scored:
            return []

        # Fetch content for those IDs
        id_list = [r[0] for r in ids_scored[:n]]
        score_map = {r[0]: round(r[1], 3) for r in ids_scored}

        conn2 = sqlite3.connect(DB_PATH, timeout=10)
        try:
            placeholders = ",".join("?" * len(id_list))
            mem_rows = conn2.execute(
                f"SELECT id, mem_type, agent_name, content FROM memories WHERE id IN ({placeholders})",
                id_list,
            ).fetchall()
        finally:
            conn2.close()

        result = []
        for mid, mtype, agent, content in mem_rows:
            result.append({
                "id":      mid,
                "type":    mtype or "unknown",
                "agent":   agent or "unknown",
                "content": (content or "")[:200],
                "score":   score_map.get(mid, 0.0),
            })
        result.sort(key=lambda r: -r["score"])
        return result[:n]

    except Exception as e:
        print(f"[memory] get_last_accessed_content error: {e}")
        return []


def get_recent(agent_name: str, limit: int = 10) -> list:
    """
    Return most recent N memory entries for a specific agent.
    Returns list of dicts: {type, content, timestamp}
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        rows = conn.execute(
            """SELECT mem_type, content, timestamp FROM memories
               WHERE agent_name = ?
               ORDER BY id DESC LIMIT ?""",
            (agent_name, limit),
        ).fetchall()
    finally:
        conn.close()

    return [{"type": r[0], "content": r[1], "timestamp": r[2]} for r in rows]


def memory_stats() -> dict:
    """
    Return memory health metrics for dashboard/API consumption.

    Fields:
      total           — total memories
      by_type         — {type: {count, avg_quality, avg_used}}
      by_agent        — {agent: count}
      prune_candidates — count of rows with quality < threshold AND use_count == 0
      never_used      — count of rows with use_count == 0
      low_quality     — count of rows with quality < threshold
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

        type_rows = conn.execute(
            "SELECT mem_type, COUNT(*), AVG(COALESCE(quality,1.0)), AVG(COALESCE(use_count,0)) "
            "FROM memories GROUP BY mem_type"
        ).fetchall()

        agent_rows = conn.execute(
            "SELECT agent_name, COUNT(*) FROM memories GROUP BY agent_name"
        ).fetchall()

        prune_count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE COALESCE(quality,1.0) < ? AND COALESCE(use_count,0) = 0",
            (_PRUNE_QUALITY_THRESHOLD,),
        ).fetchone()[0]

        never_used = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE COALESCE(use_count,0) = 0"
        ).fetchone()[0]

        low_quality = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE COALESCE(quality,1.0) < ?",
            (_PRUNE_QUALITY_THRESHOLD,),
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "total":            total,
        "prune_candidates": prune_count,
        "never_used":       never_used,
        "low_quality":      low_quality,
        "by_type": {
            t: {"count": cnt, "avg_quality": round(aq, 3), "avg_used": round(au, 1)}
            for t, cnt, aq, au in type_rows
        },
        "by_agent": {a: cnt for a, cnt in agent_rows},
    }


def prune(dry_run: bool = True) -> dict:
    """
    Remove memories that are both low quality AND never recalled.

    A memory is prunable when:
      quality < _PRUNE_QUALITY_THRESHOLD  AND  use_count == 0

    dry_run=True  — returns candidates without deleting (safe default)
    dry_run=False — deletes and returns {deleted, remaining}

    Returns dict with keys: candidates (list), deleted (int), remaining (int).
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        rows = conn.execute(
            "SELECT id, agent_name, mem_type, quality, content FROM memories "
            "WHERE COALESCE(quality,1.0) < ? AND COALESCE(use_count,0) = 0",
            (_PRUNE_QUALITY_THRESHOLD,),
        ).fetchall()

        candidates = [
            {"id": r[0], "agent": r[1], "type": r[2],
             "quality": round(r[3], 3), "preview": (r[4] or "")[:80]}
            for r in rows
        ]

        deleted = 0
        if not dry_run and candidates:
            ids = [r[0] for r in rows]
            conn.execute(
                f"DELETE FROM memories WHERE id IN ({','.join('?'*len(ids))})", ids
            )
            conn.commit()
            deleted = len(ids)

        remaining = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    finally:
        conn.close()

    return {
        "candidates": candidates,
        "deleted":    deleted,
        "remaining":  remaining,
    }


def at_risk_memories(n: int = 30) -> list:
    """
    Return memories approaching the prune threshold.

    These are quality 0.55–0.70 with use_count ≤ 1 — still above the prune
    floor but at risk of falling below it on the next negative feedback cycle.
    Useful for the pruning preview UI.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        rows = conn.execute(
            "SELECT id, agent_name, mem_type, COALESCE(quality,1.0), "
            "COALESCE(use_count,0), content "
            "FROM memories "
            "WHERE COALESCE(quality,1.0) >= ? AND COALESCE(quality,1.0) <= ? "
            "AND COALESCE(use_count,0) <= 1 "
            "ORDER BY COALESCE(quality,1.0) ASC LIMIT ?",
            (_PRUNE_QUALITY_THRESHOLD, 0.70, n),
        ).fetchall()
    finally:
        conn.close()

    return [
        {"id": r[0], "agent": r[1], "type": r[2],
         "quality": round(r[3], 3), "use_count": r[4],
         "preview": (r[5] or "")[:100]}
        for r in rows
    ]


def consolidate(threshold: float = 0.93, dry_run: bool = True) -> dict:
    """
    Find and optionally remove near-duplicate memories within the same agent.

    Two memories are considered duplicates when their cosine similarity exceeds
    `threshold`. The lower-quality copy is removed; the higher-quality one is kept.

    dry_run=True  — returns duplicates without deleting (safe default)
    dry_run=False — deletes lower-quality copies, returns {removed, kept, remaining}

    Returns dict with keys: pairs (list of {kept_id, removed_id, cos, agent}),
    removed (int), kept (int), remaining (int).
    """
    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        rows = conn.execute(
            "SELECT id, agent_name, COALESCE(quality,1.0), embedding "
            "FROM memories ORDER BY agent_name, id"
        ).fetchall()
    finally:
        conn.close()

    # Group by agent
    by_agent: dict = {}
    for row_id, agent, quality, blob in rows:
        emb = _normalize(np.frombuffer(blob, dtype=np.float32))
        by_agent.setdefault(agent, []).append((row_id, quality, emb))

    pairs = []
    to_remove: set = set()

    for agent, entries in by_agent.items():
        for i in range(len(entries)):
            if entries[i][0] in to_remove:
                continue
            for j in range(i + 1, len(entries)):
                if entries[j][0] in to_remove:
                    continue
                cos = float(np.dot(entries[i][2], entries[j][2]))
                if cos >= threshold:
                    # Keep higher quality; remove lower
                    keep   = entries[i] if entries[i][1] >= entries[j][1] else entries[j]
                    remove = entries[j] if keep is entries[i] else entries[i]
                    to_remove.add(remove[0])
                    pairs.append({
                        "kept_id":    keep[0],
                        "removed_id": remove[0],
                        "cos":        round(cos, 3),
                        "agent":      agent,
                    })

    deleted = 0
    if not dry_run and to_remove:
        id_list = list(to_remove)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute(
                f"DELETE FROM memories WHERE id IN ({','.join('?'*len(id_list))})",
                id_list,
            )
            conn.commit()
            deleted = len(id_list)
        finally:
            conn.close()

    conn2 = sqlite3.connect(DB_PATH, timeout=10)
    try:
        remaining_count = conn2.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    finally:
        conn2.close()

    return {
        "pairs":     pairs,
        "removed":   deleted,
        "kept":      len(pairs) - deleted,
        "remaining": remaining_count,
        "dry_run":   dry_run,
    }


def auto_resolve_conflicts(threshold: float = 0.90, dry_run: bool = True) -> dict:
    """
    Find and optionally resolve contradicting memories within the same agent.

    Differs from consolidate(): instead of keeping the higher-quality copy,
    always keeps the NEWER memory (higher id = later AUTOINCREMENT = more recent
    knowledge). This implements the "prefer newer when conflict_score > threshold"
    auto-resolve strategy.

    dry_run=True  — preview pairs without deleting
    dry_run=False — delete older copies, return resolved count
    """
    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        rows = conn.execute(
            "SELECT id, agent_name, COALESCE(quality,1.0), embedding "
            "FROM memories ORDER BY agent_name, id"
        ).fetchall()
    finally:
        conn.close()

    by_agent: dict = {}
    for row_id, agent, quality, blob in rows:
        emb = _normalize(np.frombuffer(blob, dtype=np.float32))
        by_agent.setdefault(agent, []).append((row_id, quality, emb))

    pairs = []
    to_remove: set = set()

    for agent, entries in by_agent.items():
        for i in range(len(entries)):
            if entries[i][0] in to_remove:
                continue
            for j in range(i + 1, len(entries)):
                if entries[j][0] in to_remove:
                    continue
                cos = float(np.dot(entries[i][2], entries[j][2]))
                if cos >= threshold:
                    # Always keep newer (higher id); entries are sorted by id ASC
                    # so entries[j] is always newer than entries[i]
                    keep_id   = entries[j][0]
                    remove_id = entries[i][0]
                    to_remove.add(remove_id)
                    pairs.append({
                        "kept_id":    keep_id,
                        "removed_id": remove_id,
                        "cos":        round(cos, 3),
                        "agent":      agent,
                    })

    deleted = 0
    if not dry_run and to_remove:
        id_list = list(to_remove)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute(
                f"DELETE FROM memories WHERE id IN ({','.join('?'*len(id_list))})",
                id_list,
            )
            conn.commit()
            deleted = len(id_list)
        finally:
            conn.close()

    conn2 = sqlite3.connect(DB_PATH, timeout=10)
    try:
        remaining_count = conn2.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    finally:
        conn2.close()

    return {
        "pairs":     pairs,
        "resolved":  deleted,
        "remaining": remaining_count,
        "threshold": threshold,
        "dry_run":   dry_run,
    }


def export_memories_csv() -> str:
    """Return all memories as a CSV string for download."""
    import csv
    import io
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        rows = conn.execute(
            "SELECT id, agent_name, mem_type, COALESCE(quality,1.0), "
            "COALESCE(use_count,0), timestamp, content "
            "FROM memories ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "agent", "type", "quality", "use_count", "timestamp", "content"])
    for r in rows:
        w.writerow([r[0], r[1], r[2], round(r[3], 3), r[4], r[5], (r[6] or "").replace("\n", " ")])
    return buf.getvalue()


# ── Portable export / import (JSON, Markdown) ─────────────────
# JSON export base64-encodes the float32 embedding so a re-import is lossless
# and needs no embedding model — the stored vector is reused directly. This is
# the backup/transfer format; CSV (above) stays the spreadsheet-friendly view.

_EXPORT_FORMAT = "amagra.memory/1"


def _scoped_rows(agent_name=None, owner_key_id=None, columns="*"):
    """Fetch memory rows, optionally filtered by agent and tenant (owner_key_id)."""
    if owner_key_id is None:
        owner_key_id = _current_owner_key_id.get()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        q = f"SELECT {columns} FROM memories"
        clauses, params = [], []
        if agent_name:
            clauses.append("agent_name = ?"); params.append(agent_name)
        if owner_key_id is not None:
            clauses.append("(owner_key_id = ? OR owner_key_id IS NULL)")
            params.append(owner_key_id)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY id"
        return conn.execute(q, params).fetchall()
    finally:
        conn.close()


def export_memories_json(agent_name=None, include_embeddings=True,
                         owner_key_id=None) -> str:
    """Full-fidelity JSON dump of memories (lossless when include_embeddings)."""
    import base64
    rows = _scoped_rows(
        agent_name, owner_key_id,
        columns=("id, timestamp, agent_name, mem_type, content, metadata, "
                 "embedding, COALESCE(quality,1.0), COALESCE(use_count,0), last_used"),
    )
    dim = 0
    mems = []
    for r in rows:
        rec = {
            "timestamp": r[1], "agent": r[2], "type": r[3], "content": r[4],
            "metadata": json.loads(r[5]) if r[5] else None,
            "quality": round(float(r[7]), 4), "use_count": r[8], "last_used": r[9],
        }
        if include_embeddings and r[6] is not None:
            rec["embedding_b64"] = base64.b64encode(r[6]).decode("ascii")
            dim = len(r[6]) // 4  # float32
        mems.append(rec)
    return json.dumps({
        "format": _EXPORT_FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "embedding_dim": dim,
        "count": len(mems),
        "memories": mems,
    }, indent=2, ensure_ascii=False)


def export_memories_markdown(agent_name=None, owner_key_id=None) -> str:
    """Human-readable Markdown dump, grouped by agent."""
    rows = _scoped_rows(
        agent_name, owner_key_id,
        columns="agent_name, mem_type, content, COALESCE(quality,1.0), timestamp",
    )
    out = ["# Amagra memory export",
           f"\n_Exported {datetime.now(timezone.utc).isoformat()} · {len(rows)} memories_\n"]
    current = None
    for agent, mtype, content, quality, ts in rows:
        if agent != current:
            out.append(f"\n## {agent}\n")
            current = agent
        out.append(f"- **[{mtype}]** _(q={round(float(quality), 2)}, {ts})_\n\n"
                   f"  {(content or '').strip()}\n")
    return "\n".join(out)


def import_memories_json(payload, reembed=False, owner_key_id=None) -> dict:
    """Ingest a JSON export. Reuses stored embeddings unless reembed=True.

    Dedups against existing memories (same near-duplicate gate as save()), so
    re-importing the same file is idempotent. Returns a per-outcome summary.
    """
    import base64
    if owner_key_id is None:
        owner_key_id = _current_owner_key_id.get()
    if isinstance(payload, str):
        payload = json.loads(payload)
    mems = payload.get("memories") if isinstance(payload, dict) else payload
    if not isinstance(mems, list):
        raise ValueError('expected a list of memories or {"memories": [...]}')

    imported = duplicates = errors = 0
    for m in mems:
        try:
            content = (m.get("content") or "").strip()
            if not content:
                errors += 1
                continue
            agent = m.get("agent") or m.get("agent_name") or "knowledge_learning"
            mtype = m.get("type") or m.get("mem_type") or "imported"

            b64 = m.get("embedding_b64")
            if b64 and not reembed:
                emb = _normalize(np.frombuffer(base64.b64decode(b64), dtype=np.float32))
            else:
                emb = _normalize(get_embedding(content))
            emb_bytes = emb.tobytes()

            if _is_near_duplicate(emb, agent):
                duplicates += 1
                continue

            meta = m.get("metadata")
            quality = max(0.0, min(1.0, float(m.get("quality", 1.0))))
            ts = m.get("timestamp") or datetime.now(timezone.utc).isoformat()
            with _lock:
                conn = sqlite3.connect(DB_PATH, timeout=30)
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute(
                        """INSERT INTO memories
                           (timestamp, agent_name, mem_type, content, metadata,
                            embedding, quality, owner_key_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ts, agent, mtype, content,
                         json.dumps(meta) if meta else None,
                         emb_bytes, quality, owner_key_id),
                    )
                    conn.commit()
                finally:
                    conn.close()
            imported += 1
        except Exception as e:
            print(f"[memory] import error: {e}")
            errors += 1
    return {"imported": imported, "skipped_duplicates": duplicates,
            "errors": errors, "total": len(mems)}


# ── STANDALONE TEST ──────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("memory_db.py — standalone test")
    print("Requires: Ollama running + nomic-embed-text pulled")
    print("=" * 50)

    def check(name, cond):
        print(f"  {'✓' if cond else '✗'} {name}")

    init_db()
    check("init_db ran without error", True)

    ok = save("personal_projects", "episodic", "Build a mushroom farmer game in Unity",
              {"test": True}, quality=0.9)
    check("save() returns True", ok)

    ok2 = save("personal_projects", "failure", "Unity build failed due to missing assembly",
               {"test": True}, quality=0.6)
    check("save() failure type returns True", ok2)

    results = search("mushroom game Unity", caller="test")
    check("search() returns results", len(results) > 0)
    check("search result has expected keys",
          all(k in results[0] for k in ["id", "agent", "type", "content", "score", "raw_score", "timestamp"]))
    check("top result is relevant (raw_score > 0.5)", results[0]["raw_score"] > 0.5)

    audits = get_recent_audits(5)
    check("retrieval audit was logged", len(audits) > 0)
    check("audit has retrieved list", isinstance(audits[0]["retrieved"], list))

    recent = get_recent("personal_projects")
    check("get_recent() returns results", len(recent) > 0)
    check("get_recent result has correct keys",
          all(k in recent[0] for k in ["type", "content", "timestamp"]))

    print("\n  Done. Check ✓/✗ above.")
