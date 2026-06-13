# ~/agentic-ai/context_snapshot.py
# ─────────────────────────────────────────────────────────────
# Execution context snapshot — records every stage of a request
# so it can be inspected, diffed, and replayed.
#
# Each request gets a context_id (= run_tracer run_id).
# Components call record_*() during the request lifecycle.
# api.py calls finalize() at the end to persist to SQLite.
#
# Schema is a single JSON blob — extensible without migrations.
# ─────────────────────────────────────────────────────────────

import sqlite3
import json
import hashlib
import os
import threading
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "snapshots.db")

# Thread-local: active context_id for the current request thread
_local = threading.local()

# In-flight buffers: context_id → partial snapshot dict
_buffers: dict = {}
_lock = threading.Lock()


# ── Init ─────────────────────────────────────────────────────

def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            context_id  TEXT NOT NULL,
            session_id  INTEGER,
            timestamp   TEXT NOT NULL,
            snapshot    TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ctx ON snapshots(context_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON snapshots(timestamp);")
    conn.commit()
    conn.close()


# ── Accumulator API (called during a request) ─────────────────

def _make_buffer(context_id: str, query: str, normalized_query: str = "",
                 parent_context_id: str = "", fork_overrides: dict = None) -> dict:
    buf = {
        "request_id":       context_id,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "input": {
            "query":            query,
            "normalized_query": normalized_query,
        },
        "routing":  {},
        "prompt":   {},
        "memory":   {"retrieved": []},
        "tools":    {"available": [], "invoked": []},
        "model": {
            "name":           "phi4-mini",
            "temperature":    0.7,
            "max_tokens":     256,
            "context_window": 2048,
        },
        "output":     {},
        "evaluation": {},
    }
    if parent_context_id:
        buf["parent_context_id"] = parent_context_id
    if fork_overrides:
        buf["fork_overrides"] = fork_overrides
    return buf


def begin(context_id: str, query: str, normalized_query: str = "") -> None:
    """Open a snapshot buffer for this request. Call at the top of /ask."""
    _local.context_id = context_id
    with _lock:
        _buffers[context_id] = _make_buffer(context_id, query, normalized_query)


def begin_fork(context_id: str, query: str, parent_context_id: str,
               overrides: dict, normalized_query: str = "") -> None:
    """Open a snapshot buffer for a fork replay. Records parent lineage and overrides."""
    _local.context_id = context_id
    with _lock:
        _buffers[context_id] = _make_buffer(
            context_id, query, normalized_query,
            parent_context_id=parent_context_id,
            fork_overrides=overrides,
        )


def record_routing(agent: str, confidence: float, action: str,
                   complexity: str, reason: str = "") -> None:
    """Record the brain routing decision. Called from coordinator."""
    ctx = getattr(_local, 'context_id', None)
    if not ctx:
        return
    with _lock:
        buf = _buffers.get(ctx)
        if buf:
            buf["routing"] = {
                "agent":      agent,
                "confidence": round(confidence, 4),
                "action":     action,
                "complexity": complexity,
                "reason":     reason,
            }
            buf["tools"]["available"] = _AGENT_TOOLS.get(agent, [])


def record_prompt(agent_name: str) -> None:
    """Hash and record the agent system prompt. Called from coordinator."""
    ctx = getattr(_local, 'context_id', None)
    if not ctx:
        return
    prompt_text = _get_system_prompt(agent_name)
    if not prompt_text:
        return
    with _lock:
        buf = _buffers.get(ctx)
        if buf:
            buf["prompt"] = {
                "agent":       agent_name,
                "hash":        _short_hash(prompt_text),
                "token_count": _token_estimate(prompt_text),
            }


def record_memories(records: list) -> None:
    """Record retrieved memories. Called from memory_context after retrieval."""
    ctx = getattr(_local, 'context_id', None)
    if not ctx:
        return
    with _lock:
        buf = _buffers.get(ctx)
        if buf:
            entries = []
            for r in records:
                content = getattr(r, 'content', '') or ''
                entries.append({
                    "id":      getattr(r, 'id', None),
                    "score":   round(float(getattr(r, 'score', 0.0)), 4),
                    "hash":    _short_hash(content),
                    "agent":   getattr(r, 'agent', ''),
                    "type":    getattr(r, 'mem_type', ''),
                    "preview": content[:100],
                })
            buf["memory"]["retrieved"] = entries


def record_reflection(score_initial: float, score_final: float) -> None:
    """Record reflection evaluation scores. Called from coordinator."""
    ctx = getattr(_local, 'context_id', None)
    if not ctx:
        return
    with _lock:
        buf = _buffers.get(ctx)
        if buf:
            buf["evaluation"] = {
                "reflection_score":       round(score_initial, 4),
                "reflection_score_final": round(score_final, 4),
                "reflection_delta":       round(score_final - score_initial, 4),
            }


def finalize(context_id: str, response: str, session_id: int = None) -> dict:
    """
    Seal the snapshot with the output, persist to DB, return the full dict.
    Call at the end of /ask just before returning.
    """
    with _lock:
        buf = _buffers.pop(context_id, {})

    buf["output"] = {
        "response_hash":    _short_hash(response),
        "response_tokens":  _token_estimate(response),
        "response_preview": response[:500],
    }

    row_id = _persist(buf, session_id)
    buf["_snapshot_id"] = row_id

    if getattr(_local, 'context_id', None) == context_id:
        _local.context_id = None

    return buf


# ── Storage ───────────────────────────────────────────────────

def _persist(snapshot: dict, session_id: int = None) -> int:
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.execute(
            "INSERT INTO snapshots (context_id, session_id, timestamp, snapshot) "
            "VALUES (?,?,?,?)",
            (
                snapshot.get("request_id", ""),
                session_id,
                snapshot.get("timestamp", datetime.now(timezone.utc).isoformat()),
                json.dumps(snapshot),
            ),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id
    except Exception as e:
        print(f"[context_snapshot] persist error: {e}")
        return -1


# ── Read API ──────────────────────────────────────────────────

def get_by_id(snapshot_id: int) -> dict | None:
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        row = conn.execute(
            "SELECT id, session_id, snapshot FROM snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        s = json.loads(row[2])
        s["_snapshot_id"] = row[0]
        s["_session_id"]  = row[1]
        return s
    except Exception as e:
        print(f"[context_snapshot] get_by_id error: {e}")
        return None


def get_by_context_id(context_id: str) -> dict | None:
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        row = conn.execute(
            "SELECT id, session_id, snapshot FROM snapshots "
            "WHERE context_id=? ORDER BY id DESC LIMIT 1",
            (context_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        s = json.loads(row[2])
        s["_snapshot_id"] = row[0]
        s["_session_id"]  = row[1]
        return s
    except Exception as e:
        print(f"[context_snapshot] get_by_context_id error: {e}")
        return None


def recent(n: int = 50) -> list:
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        rows = conn.execute(
            "SELECT id, session_id, timestamp, snapshot FROM snapshots "
            "ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        conn.close()
        result = []
        for row in rows:
            s = json.loads(row[3])
            s["_snapshot_id"] = row[0]
            s["_session_id"]  = row[1]
            result.append(s)
        return result
    except Exception as e:
        print(f"[context_snapshot] recent error: {e}")
        return []


def diff(id_a: int, id_b: int) -> dict:
    """
    Structured diff between two context snapshots.
    Returns changed fields across routing, prompt, memory, model, and output.
    This is the foundation for Phase 3 (Snapshot Diff).
    """
    a = get_by_id(id_a)
    b = get_by_id(id_b)
    if not a or not b:
        return {"error": "one or both snapshots not found"}

    def _cmp(va, vb, label: str) -> dict:
        return {"changed": va != vb, "from": va, "to": vb, "label": label}

    mem_a = {m.get("id") for m in a.get("memory", {}).get("retrieved", []) if m.get("id")}
    mem_b = {m.get("id") for m in b.get("memory", {}).get("retrieved", []) if m.get("id")}

    return {
        "a": {"snapshot_id": id_a, "timestamp": a.get("timestamp"),
              "query": a.get("input", {}).get("query", "")[:80]},
        "b": {"snapshot_id": id_b, "timestamp": b.get("timestamp"),
              "query": b.get("input", {}).get("query", "")[:80]},
        "routing": {
            "agent":      _cmp(a.get("routing", {}).get("agent"),
                               b.get("routing", {}).get("agent"),      "agent"),
            "confidence": _cmp(a.get("routing", {}).get("confidence"),
                               b.get("routing", {}).get("confidence"), "confidence"),
            "action":     _cmp(a.get("routing", {}).get("action"),
                               b.get("routing", {}).get("action"),     "action"),
        },
        "prompt": {
            "hash":        _cmp(a.get("prompt", {}).get("hash"),
                                b.get("prompt", {}).get("hash"),        "hash"),
            "token_count": _cmp(a.get("prompt", {}).get("token_count"),
                                b.get("prompt", {}).get("token_count"), "token_count"),
        },
        "memory": {
            "added":   sorted(mem_b - mem_a),
            "removed": sorted(mem_a - mem_b),
            "count_a": len(mem_a),
            "count_b": len(mem_b),
            "changed": mem_a != mem_b,
        },
        "model": {
            "name":        _cmp(a.get("model", {}).get("name"),
                                b.get("model", {}).get("name"),        "name"),
            "temperature": _cmp(a.get("model", {}).get("temperature"),
                                b.get("model", {}).get("temperature"), "temperature"),
        },
        "output": {
            "response_hash": _cmp(a.get("output", {}).get("response_hash"),
                                  b.get("output", {}).get("response_hash"), "response_hash"),
            "same_response": a.get("output", {}).get("response_hash") ==
                             b.get("output", {}).get("response_hash"),
        },
    }


# ── Helpers ───────────────────────────────────────────────────

def _short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def _token_estimate(text: str) -> int:
    return max(1, len(text.split()))


_AGENT_TOOLS: dict = {
    "it_networking":     ["ping_host"],
    "python_dev":        [],
    "dotnet_dev":        [],
    "ai_ml":             [],
    "knowledge_learning": [],
    "terse":             [],
}


def _get_system_prompt(agent_name: str) -> str:
    try:
        mapping = {
            "python_dev":        ("agents.python_dev",        "PYTHON_SYSTEM_PROMPT"),
            "it_networking":     ("agents.it_networking",     "IT_SYSTEM_PROMPT"),
            "dotnet_dev":        ("agents.dotnet_dev",        "DOTNET_SYSTEM_PROMPT"),
            "ai_ml":             ("agents.ai_ml",             "AI_ML_SYSTEM_PROMPT"),
            "knowledge_learning":("agents.knowledge_learning","KNOWLEDGE_SYSTEM_PROMPT"),
            "terse":             ("agents.terse",             "TERSE_SYSTEM_PROMPT"),
        }
        if agent_name not in mapping:
            return ""
        module_path, attr = mapping[agent_name]
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr, "")
    except Exception:
        return ""


# Auto-init on import
init()
