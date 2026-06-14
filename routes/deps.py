import os
import sqlite3
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cognitive OS session (singleton for local single-user setup)
_COS_SESSION_ID = "cos-session-main"
try:
    from models.cognitive_state import get_session_state as _get_cos
    _cos = _get_cos(_COS_SESSION_ID)
except Exception as _e:
    _cos = None
    print(f"[api] cognitive_state unavailable: {_e}")

session_history = []

from infrastructure.db import path as _dbpath
_SESSIONS_DB       = _dbpath("sessions")
_FEEDBACK_DB       = _dbpath("feedback")
_CONTRADICTIONS_DB = _dbpath("contradictions")


def _init_sessions():
    os.makedirs(os.path.dirname(_SESSIONS_DB), exist_ok=True)
    conn = sqlite3.connect(_SESSIONS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            user_input  TEXT,
            response    TEXT,
            agent       TEXT,
            duration_ms INTEGER,
            confidence  REAL
        )
    """)
    conn.commit()
    conn.close()

    _dc = sqlite3.connect(_SESSIONS_DB)
    try:
        _dc.execute("ALTER TABLE sessions ADD COLUMN decision_id INTEGER")
        _dc.commit()
    except Exception:
        pass
    _dc.close()

    _decisions_path = _dbpath("decisions")
    if os.path.exists(_decisions_path):
        _dc2 = sqlite3.connect(_decisions_path)
        try:
            _dc2.execute("ALTER TABLE brain_decisions ADD COLUMN session_id INTEGER")
            _dc2.commit()
        except Exception:
            pass
        _dc2.close()


def _init_feedback():
    conn = sqlite3.connect(_FEEDBACK_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            query       TEXT,
            response    TEXT,
            agent       TEXT,
            rating      INTEGER,
            note        TEXT
        )
    """)
    conn.commit()
    conn.close()


def _init_contradictions():
    os.makedirs(os.path.dirname(_CONTRADICTIONS_DB), exist_ok=True)
    conn = sqlite3.connect(_CONTRADICTIONS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contradictions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT,
            agent         TEXT,
            query         TEXT,
            response_snip TEXT,
            reflect_level TEXT
        )
    """)
    conn.commit()
    conn.close()


_init_sessions()
_init_feedback()
_init_contradictions()


class FeedbackRequest(BaseModel):
    query:    str
    response: str
    agent:    str
    rating:   int
    note:     str = ""


def _init_threads():
    conn = sqlite3.connect(_SESSIONS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id         TEXT PRIMARY KEY,
            title      TEXT,
            created_at TEXT,
            updated_at TEXT,
            turn_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            ts        TEXT NOT NULL,
            user_msg  TEXT NOT NULL,
            agent_msg TEXT NOT NULL,
            agent     TEXT NOT NULL
        )
    """)
    # Migration: archive flag for thread management (added v1.1). Idempotent —
    # older sessions.db files predate the column.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(threads)")}
    if "archived" not in cols:
        conn.execute("ALTER TABLE threads ADD COLUMN archived INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


_init_threads()


class AskRequest(BaseModel):
    message:             str
    force_agent:         str | None = None
    force_reflect_level: str | None = None
    thread_id:           str | None = None
    provider:            str | None = None        # "anthropic" | "ollama" | None (auto)
    context_files:       list[str] | None = None  # filenames previously uploaded via /documents/upload


class ForkRequest(BaseModel):
    agent_override:      str | None = None
    exclude_memory_ids:  list[int]  = []
    force_reflect_level: str | None = None
    note:                str         = ""


class AskResponse(BaseModel):
    response:       str
    agent_used:     str
    routing_reason: str
    duration_ms:    int
    timestamp:      str
    signal_domain:    str   = "general"
    signal_shape:     str   = "explanation"
    signal_verbosity: str   = "normal"
    signal_conf:      float = 0.0
    action:       str   = "unknown"
    complexity:   str   = "simple"
    model_tier:   str   = "fast"
    reflect_level: str  = "none"
    confidence:   float = 0.67
    regret:       float = 0.0
    contradiction_detected: bool = False
    memories_used: list = []
    gram_winner: str = ""
    gram_log:    str = ""
    weight_before: float = 0.0
    weight_after:  float = 0.0
    weight_delta:  float = 0.0
    pipeline_agents:    list = []
    pipeline_responses: list = []
    context_id: str = ""
    thread_id:  str = ""
    model_used: str = ""


class CreateKeyRequest(BaseModel):
    owner: str
    tier: str = "developer"
