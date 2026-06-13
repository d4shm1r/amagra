import sqlite3
from fastapi import APIRouter

router = APIRouter()


@router.get("/learning/drift")
def learning_drift():
    from decision.weights import drift_status
    return drift_status()


@router.get("/decisions")
def get_decisions(limit: int = 50):
    from decision.log import recent, conflict_rate
    from decision.analyzer import summary
    return {
        "decisions": recent(limit),
        "stats":     conflict_rate(limit),
        "agents":    summary(),
    }


@router.get("/replay/{decision_id}")
def replay_decision(decision_id: int):
    from decision.log import get_by_id
    from orchestration.core_brain import think
    from langchain_core.messages import HumanMessage

    original = get_by_id(decision_id)
    if not original:
        return {"error": f"decision {decision_id} not found"}

    task  = original["task"]
    state = {
        "messages":            [HumanMessage(content=task)],
        "active_agent":        "",
        "task":                task,
        "result":              "",
        "next_agent":          "",
        "memory":              {},
        "force_agent":         "",
        "brain_decision":      {},
        "reflect":             False,
        "reflect_type":        "general",
        "reflect_level":       "none",
        "force_reflect_level": "",
    }

    now = think(task, state)

    def changed(a, b):
        return "changed" if a != b else "same"

    level_order = {"none": 0, "light": 1, "full": 2}
    orig_level  = original.get("reflect_level", "none")
    now_level   = now.reflect_level

    return {
        "original": original,
        "now": {
            "action":        now.action,
            "complexity":    now.complexity,
            "agent":         now.agent_strategy[0],
            "confidence":    now.confidence,
            "reflect":       now.reflect,
            "reflect_type":  now.reflect_type,
            "reflect_level": now_level,
        },
        "diff": {
            "action":        changed(original["action"],      now.action),
            "agent":         changed(original["brain_agent"], now.agent_strategy[0]),
            "confidence":    "improved" if now.confidence > original.get("confidence", 0.67)
                             else "same" if now.confidence == original.get("confidence", 0.67)
                             else "declined",
            "reflect":       changed(original["reflect"], now.reflect),
            "reflect_level": "improved" if level_order.get(now_level, 0) < level_order.get(orig_level, 0)
                             else "same"  if now_level == orig_level
                             else "changed",
        },
    }


@router.get("/traces")
def get_traces(limit: int = 50):
    conn = sqlite3.connect("logs/traces.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS traces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, agent TEXT, user_message TEXT,
        routing_reason TEXT, duration_ms INTEGER
    )""")
    for _col, _typ in [("signal_domain", "TEXT"), ("signal_shape", "TEXT"), ("signal_conf", "REAL")]:
        try: conn.execute(f"ALTER TABLE traces ADD COLUMN {_col} {_typ}")
        except Exception: pass
    rows = conn.execute(
        "SELECT timestamp, agent, user_message, routing_reason, duration_ms, signal_domain, signal_shape, signal_conf "
        "FROM traces ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return {"traces": [
        {"timestamp": r[0], "agent": r[1], "user_message": r[2], "routing_reason": r[3],
         "duration_ms": r[4], "signal_domain": r[5], "signal_shape": r[6], "signal_conf": r[7]}
        for r in rows
    ]}
