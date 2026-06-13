# pip install numpy requests
# ollama pull nomic-embed-text

import sqlite3
import threading
import requests
import numpy as np
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join("memory", "agent_memory.db")
_lock = threading.Lock()


def init_db():
    """Create DB and memories table if not exists. Call once at startup."""
    os.makedirs("memory", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_name TEXT,
                mem_type  TEXT,
                content   TEXT,
                metadata  TEXT,
                embedding BLOB
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_name);")
        conn.commit()
    finally:
        conn.close()


def get_embedding(text: str) -> list:
    """
    Call nomic-embed-text via Ollama.
    Raises RuntimeError if Ollama is unreachable.
    """
    try:
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        raise RuntimeError(f"Ollama embedding failed: {e}")


def _normalize(vec) -> np.ndarray:
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr


def save(agent_name: str, mem_type: str, content: str, metadata: dict = None) -> bool:
    """
    Save a memory entry with embedding.
    Returns True on success, False on any failure — never raises.
    Thread-safe via Lock + WAL.
    """
    try:
        emb_bytes = _normalize(get_embedding(content)).tobytes()
    except Exception as e:
        print(f"[memory] Embedding error for {agent_name}: {e}")
        return False

    with _lock:
        conn = sqlite3.connect(DB_PATH, timeout=15)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """INSERT INTO memories
                   (timestamp, agent_name, mem_type, content, metadata, embedding)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    agent_name,
                    mem_type,
                    content,
                    json.dumps(metadata) if metadata else None,
                    emb_bytes,
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


def search(query: str, top_k: int = 5, agent_name: str = None) -> list:
    """
    Semantic search across all memories.
    Optional filter by agent_name.
    Returns list of dicts: {agent, type, content, score, timestamp}
    """
    try:
        q_emb = _normalize(get_embedding(query))
    except Exception as e:
        print(f"[memory] Search embedding error: {e}")
        return []

    conn = sqlite3.connect(DB_PATH, timeout=15)
    try:
        rows = conn.execute(
            "SELECT timestamp, agent_name, mem_type, content, embedding FROM memories"
        ).fetchall()
    finally:
        conn.close()

    results = []
    for ts, agent, mtype, content, emb_blob in rows:
        if agent_name and agent != agent_name:
            continue
        db_emb = _normalize(np.frombuffer(emb_blob, dtype=np.float32))
        score = float(np.dot(q_emb, db_emb))
        results.append({
            "agent": agent,
            "type": mtype,
            "content": content,
            "score": round(score, 4),
            "timestamp": ts,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_recent(agent_name: str, limit: int = 10) -> list:
    """
    Return most recent N memory entries for a specific agent.
    Returns list of dicts: {type, content, timestamp}
    """
    conn = sqlite3.connect(DB_PATH, timeout=15)
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

    ok = save("personal_projects", "project", "Build a mushroom farmer game in Unity", {"test": True})
    check("save() returns True", ok)

    results = search("mushroom game Unity")
    check("search() returns results", len(results) > 0)
    check("search result has expected keys", all(k in results[0] for k in ["agent","type","content","score","timestamp"]))
    check("top result is relevant (score > 0.5)", results[0]["score"] > 0.5)

    recent = get_recent("personal_projects")
    check("get_recent() returns results", len(recent) > 0)
    check("get_recent result has correct keys", all(k in recent[0] for k in ["type","content","timestamp"]))

    print("\n  Done. Check ✓/✗ above.")
