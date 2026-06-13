"""
API key management for agentic-ai.

Keys are stored as SHA-256 hashes; the raw key is shown once at creation.
Tiers: "free" | "developer" | "team" | "enterprise"
"""

import hashlib
import secrets
import sqlite3
import os
from datetime import datetime, timezone

from infrastructure.db import path as _dbpath
_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = _dbpath("api_keys")

TIERS = {"free", "developer", "team", "enterprise"}

# Daily request limits per tier (0 = unlimited)
TIER_LIMITS = {
    "free":       100,
    "developer":  5_000,
    "team":       50_000,
    "enterprise": 0,
}


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash          TEXT    UNIQUE NOT NULL,
                owner             TEXT    NOT NULL,
                tier              TEXT    NOT NULL DEFAULT 'developer',
                active            INTEGER NOT NULL DEFAULT 1,
                created_at        TEXT    NOT NULL,
                requests_today    INTEGER NOT NULL DEFAULT 0,
                last_request_date TEXT,
                org_id            TEXT    DEFAULT NULL
            )
        """)
        # Migration: add org_id to existing tables
        try:
            conn.execute("ALTER TABLE api_keys ADD COLUMN org_id TEXT DEFAULT NULL")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_key(owner: str, tier: str = "developer", org_id: str | None = None) -> str:
    """Create a new API key and return the raw key (shown once)."""
    if tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")
    raw = "sk-" + secrets.token_urlsafe(32)
    h   = _hash(raw)
    ts  = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO api_keys (key_hash, owner, tier, active, created_at, org_id) "
            "VALUES (?,?,?,1,?,?)",
            (h, owner, tier, ts, org_id),
        )
        conn.commit()
    finally:
        conn.close()
    return raw


def verify_key(raw_key: str) -> dict | None:
    """Return key record dict if key is valid and active, else None."""
    h = _hash(raw_key)
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash=? AND active=1", (h,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def increment_usage(key_id: int) -> dict:
    """Increment requests_today (resets on new UTC day). Returns updated row."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            return {}
        last = row["last_request_date"]
        new_count = (row["requests_today"] + 1) if last == today else 1
        conn.execute(
            "UPDATE api_keys SET requests_today=?, last_request_date=? WHERE id=?",
            (new_count, today, key_id),
        )
        conn.commit()
        return {"requests_today": new_count, "tier": row["tier"], "limit": TIER_LIMITS[row["tier"]]}
    finally:
        conn.close()


def get_usage(raw_key: str) -> dict | None:
    """Return usage stats for a key, or None if not found."""
    h = _hash(raw_key)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, owner, tier, active, created_at, requests_today, last_request_date "
            "FROM api_keys WHERE key_hash=?", (h,)
        ).fetchone()
        if not row:
            return None
        row = dict(row)
        # Reset counter if stale date
        if row["last_request_date"] != today:
            row["requests_today"] = 0
        row["daily_limit"] = TIER_LIMITS[row["tier"]]
        row["remaining"]   = (
            max(0, row["daily_limit"] - row["requests_today"])
            if row["daily_limit"] > 0 else None
        )
        return row
    finally:
        conn.close()


def list_keys() -> list[dict]:
    """Admin: list all keys (hashes only, no raw keys)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, owner, tier, active, created_at, requests_today, last_request_date "
            "FROM api_keys ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def deactivate_key(key_id: int) -> bool:
    conn = _connect()
    try:
        conn.execute("UPDATE api_keys SET active=0 WHERE id=?", (key_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# Initialize on import
init_db()
