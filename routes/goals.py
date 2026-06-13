import asyncio
import os
import sqlite3
from fastapi import APIRouter, HTTPException

from infrastructure.task_graph import create_graph, get_graph, list_graphs, retry_step
from infrastructure.executor import execute_graph
from .deps import _ROOT

router = APIRouter()


@router.post("/goals/create")
async def goal_create(data: dict):
    goal  = (data.get("goal") or "").strip()
    steps = data.get("steps") or []
    if not goal:
        raise HTTPException(400, "goal is required")
    if not steps:
        raise HTTPException(400, "steps is required")
    try:
        graph_id = create_graph(goal, steps)
        return {"goal_id": graph_id, "status": "pending", "steps": len(steps)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/goals/{goal_id}/run")
async def goal_run(goal_id: int):
    graph = get_graph(goal_id)
    if not graph:
        raise HTTPException(404, f"goal {goal_id} not found")
    if graph["status"] == "running":
        return {"message": "already running", "goal_id": goal_id}
    if graph["status"] == "completed":
        return {"message": "already completed", "goal_id": goal_id}
    asyncio.create_task(execute_graph(goal_id))
    return {"message": "started", "goal_id": goal_id, "goal": graph["goal"][:80]}


@router.get("/goals")
async def goals_list(limit: int = 30):
    return {"goals": list_graphs(limit)}


@router.get("/goals/{goal_id}")
async def goal_get(goal_id: int):
    graph = get_graph(goal_id)
    if not graph:
        raise HTTPException(404, f"goal {goal_id} not found")
    return graph


@router.post("/goals/{goal_id}/retry/{step_id}")
async def goal_retry_step(goal_id: int, step_id: str):
    ok = retry_step(goal_id, step_id)
    if not ok:
        raise HTTPException(400, f"step '{step_id}' is not in failed state")
    asyncio.create_task(execute_graph(goal_id))
    return {"message": f"retrying step '{step_id}'", "goal_id": goal_id}


@router.delete("/goals/{goal_id}")
async def goal_delete(goal_id: int):
    graph = get_graph(goal_id)
    if not graph:
        raise HTTPException(404, f"goal {goal_id} not found")
    if graph["status"] == "running":
        raise HTTPException(400, "cannot delete a running goal")
    c = sqlite3.connect(os.path.join(_ROOT, "tasks.db"))
    c.execute("DELETE FROM task_steps  WHERE graph_id=?", (goal_id,))
    c.execute("DELETE FROM task_graphs WHERE id=?",       (goal_id,))
    c.commit()
    c.close()
    return {"deleted": goal_id}
