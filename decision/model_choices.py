"""
decision/model_choices.py — the debugger→memory bridge (Tier 0).

A /debug/prompt session already carries everything a decision record needs:
the prompt, the system, the temperature, and N candidate model outputs side by
side. What the stateless endpoint throws away is the part that makes it
*knowledge*: which candidate the user chose, and **why**. This module captures
that and turns each model selection into a durable, structured decision record.

Two trust axes are first-class here, because "memory is only a moat if it is
trustworthy memory":

  * provenance — where the rationale came from.
      'explicit'  the user typed/picked a reason   → high confidence
      'derived'   only the selection, no reason     → medium confidence
    Provenance maps onto the memory backend's `quality` field, so the existing
    relevance×quality×freshness ranking down-weights derived memories
    automatically. "Explain this project" can then trust explicit over derived.

  * currency — whether the record still reflects reality.
      A later decision over the same prompt-intent calls supersede(old, new),
      setting `superseded_by`. A high-provenance record that has gone stale is
      *more* dangerous than a low-provenance fresh one, so synthesis must read
      both axes: only active (superseded_by IS NULL) records are authoritative.

This is deliberately a separate table from decision/log.py's `brain_decisions`
(which logs router agent choices, a different concept).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from infrastructure import db as _db

# Provenance → memory quality weight. The confidence hierarchy, made concrete.
_QUALITY = {"explicit": 1.0, "derived": 0.6}


def _conn():
    c = _db.connect("model_decisions", check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def init():
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS model_decisions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            project         TEXT    DEFAULT '',
            prompt          TEXT    NOT NULL,
            system          TEXT    DEFAULT '',
            temperature     REAL    DEFAULT 0.2,
            candidates      TEXT    DEFAULT '[]',
            chosen_provider TEXT    NOT NULL,
            chosen_model    TEXT    DEFAULT '',
            rationale       TEXT    DEFAULT '',
            rationale_tags  TEXT    DEFAULT '[]',
            provenance      TEXT    DEFAULT 'derived',
            superseded_by   INTEGER DEFAULT NULL,
            memory_mirrored INTEGER DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_md_project ON model_decisions(project);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_md_active  ON model_decisions(superseded_by);")
    c.commit()
    c.close()


def record(prompt: str, chosen_provider: str, *,
           system: str = "", temperature: float = 0.2,
           candidates: list[dict] | None = None,
           chosen_model: str = "", rationale: str = "",
           rationale_tags: list[str] | None = None,
           project: str = "") -> int:
    """
    Persist one model-selection decision. Provenance is derived from whether a
    rationale was supplied: a typed/picked reason is 'explicit', a bare
    selection is 'derived'. Returns the new row id, or -1 on failure.
    """
    provenance = "explicit" if (rationale.strip() or rationale_tags) else "derived"
    try:
        c = _conn()
        cur = c.execute("""
            INSERT INTO model_decisions
            (timestamp, project, prompt, system, temperature, candidates,
             chosen_provider, chosen_model, rationale, rationale_tags, provenance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            project or "",
            prompt,
            system or "",
            float(temperature),
            json.dumps(candidates or []),
            chosen_provider,
            chosen_model or "",
            rationale.strip(),
            json.dumps(rationale_tags or []),
            provenance,
        ))
        row_id = cur.lastrowid
        c.commit()
        c.close()
        return row_id
    except Exception as e:
        print(f"[model_choices] write error: {e}")
        return -1


def quality_for(provenance: str) -> float:
    """Memory-backend quality weight for a provenance tier."""
    return _QUALITY.get(provenance, _QUALITY["derived"])


def mark_mirrored(decision_id: int) -> None:
    """Flag that this decision has been mirrored into long-term memory."""
    try:
        c = _conn()
        c.execute("UPDATE model_decisions SET memory_mirrored=1 WHERE id=?", (decision_id,))
        c.commit()
        c.close()
    except Exception:
        pass


def supersede(old_id: int, new_id: int) -> bool:
    """Mark old_id as superseded by new_id (the currency axis). Idempotent."""
    try:
        c = _conn()
        c.execute("UPDATE model_decisions SET superseded_by=? WHERE id=?", (new_id, old_id))
        c.commit()
        c.close()
        return True
    except Exception:
        return False


def _row_to_dict(r) -> dict:
    return {
        "id":              r[0],
        "timestamp":       r[1],
        "project":         r[2],
        "prompt":          r[3],
        "system":          r[4],
        "temperature":     r[5],
        "candidates":      json.loads(r[6] or "[]"),
        "chosen_provider": r[7],
        "chosen_model":    r[8],
        "rationale":       r[9],
        "rationale_tags":  json.loads(r[10] or "[]"),
        "provenance":      r[11],
        "superseded_by":   r[12],
        "memory_mirrored": bool(r[13]),
        "active":          r[12] is None,
    }


_COLS = ("id, timestamp, project, prompt, system, temperature, candidates, "
         "chosen_provider, chosen_model, rationale, rationale_tags, "
         "provenance, superseded_by, memory_mirrored")


def recent(limit: int = 50, project: str = "", active_only: bool = False) -> list[dict]:
    try:
        c = _conn()
        where, params = [], []
        if project:
            where.append("project = ?")
            params.append(project)
        if active_only:
            where.append("superseded_by IS NULL")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = c.execute(
            f"SELECT {_COLS} FROM model_decisions{clause} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        c.close()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


def get_by_id(decision_id: int) -> dict | None:
    try:
        c = _conn()
        row = c.execute(
            f"SELECT {_COLS} FROM model_decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        c.close()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def coverage(project: str = "") -> dict:
    """
    Structured Knowledge Coverage for model decisions: how much of the captured
    knowledge is explicit (user rationale) vs derived (bare selection), and how
    much is still current. A leading indicator of trustworthiness, not a target.
    """
    try:
        c = _conn()
        clause, params = ("", [])
        if project:
            clause, params = (" WHERE project = ?", [project])
        total = c.execute(
            f"SELECT COUNT(*) FROM model_decisions{clause}", params
        ).fetchone()[0]
        explicit = c.execute(
            f"SELECT COUNT(*) FROM model_decisions{clause}"
            f"{' AND' if clause else ' WHERE'} provenance='explicit'", params
        ).fetchone()[0]
        active = c.execute(
            f"SELECT COUNT(*) FROM model_decisions{clause}"
            f"{' AND' if clause else ' WHERE'} superseded_by IS NULL", params
        ).fetchone()[0]
        c.close()
        return {
            "total":          total,
            "explicit":       explicit,
            "derived":        total - explicit,
            "active":         active,
            "superseded":     total - active,
            "explicit_ratio": round(explicit / total, 3) if total else 0.0,
            "active_ratio":   round(active / total, 3) if total else 0.0,
        }
    except Exception:
        return {"total": 0, "explicit": 0, "derived": 0, "active": 0,
                "superseded": 0, "explicit_ratio": 0.0, "active_ratio": 0.0}


# Auto-init on import, matching decision/log.py.
init()
