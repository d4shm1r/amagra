import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from .deps import _FEEDBACK_DB, FeedbackRequest

router = APIRouter()


@router.post("/feedback")
def post_feedback(req: FeedbackRequest):
    if req.rating not in (1, -1):
        raise HTTPException(400, "rating must be 1 or -1")
    conn = sqlite3.connect(_FEEDBACK_DB)
    conn.execute(
        "INSERT INTO feedback (timestamp, query, response, agent, rating, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), req.query, req.response[:500],
         req.agent, req.rating, req.note),
    )
    conn.commit()
    conn.close()

    try:
        from training.learning import apply_learning_update
        performance = 0.90 if req.rating == 1 else 0.25
        apply_learning_update(
            agent=req.agent,
            confidence=0.67,
            regret=0.0,
            performance=performance,
            metadata={"source": "user_feedback", "rating": req.rating},
        )
    except Exception as e:
        print(f"[feedback] learning update skipped: {e}")

    try:
        import memory_core.db as _mdb
        import json as _json
        audits = _mdb.get_recent_audits(limit=30)
        for audit in audits:
            aq = audit.get("query", "")
            if req.query[:80] in aq or aq[:80] in req.query:
                retrieved = _json.loads(audit.get("retrieved", "[]"))
                ids = [r["id"] for r in retrieved if isinstance(r, dict) and "id" in r]
                if ids:
                    delta = 0.03 if req.rating == 1 else -0.05
                    updated = _mdb.update_quality(ids, delta)
                    print(f"[feedback] quality update: {updated} memories adjusted by {delta:+.2f}")
                break
    except Exception as e:
        print(f"[feedback] quality propagation skipped: {e}")

    label = "👍" if req.rating == 1 else "👎"
    print(f"[feedback] {label} {req.agent} — {req.query[:60]!r}")
    return {"saved": True}


@router.get("/feedback")
def get_feedback(limit: int = 50):
    conn = sqlite3.connect(_FEEDBACK_DB)
    rows = conn.execute(
        "SELECT id, timestamp, query, agent, rating, note FROM feedback "
        "ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "timestamp": r[1], "query": r[2],
         "agent": r[3], "rating": r[4], "note": r[5]}
        for r in rows
    ]
