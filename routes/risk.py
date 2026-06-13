import os, sqlite3
from fastapi import APIRouter, HTTPException

from .deps import _ROOT

router = APIRouter()


@router.get("/risk/stats")
def risk_stats_endpoint(n: int = 200):
    try:
        from cognition.risk_gate import risk_stats
        return risk_stats(n=n)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/risk/history")
def risk_history(n: int = 100):
    try:
        db = os.path.join(_ROOT, "logs", "risk_gate.db")
        con = sqlite3.connect(db, timeout=3)
        rows = con.execute(
            "SELECT id, action, agent, complexity, total_risk, reflect_level, reflect_type "
            "FROM risk_log ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        con.close()
        return [
            {"id": r[0], "action": r[1], "agent": r[2], "complexity": r[3],
             "total_risk": r[4], "reflect_level": r[5], "reflect_type": r[6]}
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
