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

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "runtime.db"
)


class RunLog:
    def __init__(self, path: str = _DEFAULT_PATH) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        con = sqlite3.connect(path)
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
