"""
Append-only SQLite run log — the "transparent state" the manifesto promised.

One table, one row per run, readable with a plain SELECT. No ORM, no nested
JSON state machine to decode. This is the debugging surface that the 265-line
god-wrapper's scattered logs never gave us.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time

from core.contract import Result

def _default_path() -> str:
    """logs/runtime.db under the data root. Resolved via infrastructure.paths
    so AMAGRA_DATA_DIR relocates it (packaged app, test isolation) — the old
    hardcoded repo path wrote into the install dir and leaked test rows into
    the real logs/ tree."""
    try:
        from infrastructure.paths import base_dir
        root = base_dir()
    except Exception:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "logs", "runtime.db")


class RunLog:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or _default_path()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        con = sqlite3.connect(self.path)
        con.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                   id     INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts     REAL,
                   task   TEXT,
                   ext_id TEXT,
                   output TEXT,
                   meta   TEXT
               )"""
        )
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()
        con.close()

    def append(self, task: str, ext_id: str, result: Result) -> None:
        con = sqlite3.connect(self.path)
        con.execute(
            "INSERT INTO runs (ts, task, ext_id, output, meta) VALUES (?,?,?,?,?)",
            (time.time(), task, ext_id, result.output, json.dumps(dict(result.meta))),
        )
        con.commit()
        con.close()
