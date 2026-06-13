import asyncio, sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter

from orchestration.coordinator import coordinator

router = APIRouter()

TASKS_DB = "tasks.db"

worker_event = asyncio.Event()
task_db_lock = asyncio.Lock()


def get_tasks_db():
    conn = sqlite3.connect(TASKS_DB, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_tasks_db():
    conn = get_tasks_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            prompt      TEXT NOT NULL,
            agents      TEXT,
            status      TEXT DEFAULT 'pending',
            result      TEXT,
            error       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at  TIMESTAMP,
            finished_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def reset_orphaned_tasks():
    conn = get_tasks_db()
    conn.execute("""
        UPDATE tasks
        SET status = 'pending', started_at = NULL
        WHERE status = 'running'
    """)
    conn.commit()
    conn.close()


init_tasks_db()
reset_orphaned_tasks()


def run_coordinator_sync(prompt: str, force_agent: str = "") -> str:
    initial_state = {
        "messages":       [{"role": "user", "content": prompt}],
        "active_agent":   "",
        "task":           prompt,
        "result":         "",
        "next_agent":     "",
        "memory":         {},
        "force_agent":    force_agent or "",
        "brain_decision": {},
        "reflect":        False,
        "reflect_type":   "general",
    }
    result = coordinator.invoke(initial_state)
    if "messages" in result and result["messages"]:
        return result["messages"][-1].content
    elif "result" in result and result["result"]:
        return result["result"]
    else:
        raise ValueError(f"Unexpected coordinator output: {result}")


async def task_worker():
    if worker_event.is_set():
        return

    worker_event.set()
    print("[task_worker] started")

    while True:
        task_id = None
        try:
            async with task_db_lock:
                conn = get_tasks_db()
                cur  = conn.cursor()
                cur.execute(
                    "SELECT id, prompt, agents FROM tasks WHERE status='pending' ORDER BY id LIMIT 1"
                )
                row = cur.fetchone()
                if not row:
                    conn.close()
                    break
                task_id, prompt, task_agents = row
                force_agent = task_agents.split(",")[0].strip() if task_agents else ""
                cur.execute(
                    "UPDATE tasks SET status='running', started_at=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), task_id),
                )
                conn.commit()
                conn.close()

            print(f"[task_worker] running task {task_id}")
            result = await asyncio.to_thread(run_coordinator_sync, prompt, force_agent)

            async with task_db_lock:
                conn = get_tasks_db()
                conn.execute(
                    "UPDATE tasks SET status='done', result=?, finished_at=? WHERE id=?",
                    (result, datetime.now(timezone.utc).isoformat(), task_id),
                )
                conn.commit()
                conn.close()

            print(f"[task_worker] task {task_id} done")

        except Exception as e:
            print(f"[task_worker] task {task_id} failed: {e}")
            if task_id is not None:
                try:
                    async with task_db_lock:
                        conn = get_tasks_db()
                        conn.execute(
                            "UPDATE tasks SET status='failed', error=?, finished_at=? WHERE id=?",
                            (str(e), datetime.now(timezone.utc).isoformat(), task_id),
                        )
                        conn.commit()
                        conn.close()
                except Exception as db_err:
                    print(f"[task_worker] failed to update DB: {db_err}")
            await asyncio.sleep(5)
            continue

    worker_event.clear()
    print("[task_worker] queue empty, stopped")


@router.post("/tasks/create")
async def create_task(data: dict):
    title  = data.get("title", "Untitled").strip()
    prompt = data.get("prompt", "").strip()
    agents = ",".join(data.get("agents", []))
    if not prompt:
        return {"error": "prompt is required"}
    async with task_db_lock:
        conn = get_tasks_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO tasks (title, prompt, agents, status) VALUES (?, ?, ?, 'pending')",
            (title, prompt, agents),
        )
        task_id = cur.lastrowid
        conn.commit()
        conn.close()
    return {"task_id": task_id, "status": "pending", "title": title}


@router.post("/tasks/run")
async def run_tasks():
    if worker_event.is_set():
        return {"message": "queue already running"}
    asyncio.create_task(task_worker())
    return {"message": "task queue started"}


@router.get("/tasks/status")
async def task_status():
    conn = get_tasks_db()
    rows = conn.execute(
        "SELECT id, title, status, agents, created_at, started_at, finished_at "
        "FROM tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return {"tasks": [
        {"id": r[0], "title": r[1], "status": r[2], "agents": r[3],
         "created": r[4], "started": r[5], "finished": r[6]}
        for r in rows
    ]}


@router.get("/tasks/results/{task_id}")
async def task_result(task_id: int):
    conn = get_tasks_db()
    row = conn.execute(
        "SELECT id, title, status, result, error, agents FROM tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"error": f"task {task_id} not found"}
    return {"id": row[0], "title": row[1], "status": row[2],
            "result": row[3], "error": row[4], "agents": row[5]}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    async with task_db_lock:
        conn = get_tasks_db()
        row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            conn.close()
            return {"error": "task not found"}
        if row[0] == "running":
            conn.close()
            return {"error": "cannot delete a running task"}
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
    return {"deleted": task_id}
