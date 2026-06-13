# ─────────────────────────────────────────────────────────────
# TASK QUEUE — add these to your existing ~/agentic-ai/api.py
#
# HOW TO APPLY:
#   1. Add the imports block near the top of api.py
#   2. Add everything else after your existing code
#   3. Do NOT modify any existing endpoints
#   4. Restart uvicorn after saving
# ─────────────────────────────────────────────────────────────


# ══ STEP 1 — ADD THESE IMPORTS near top of api.py ════════════
# (alongside your existing imports)

import sqlite3
import asyncio
from datetime import datetime, timezone


# ══ STEP 2 — ADD AFTER app = FastAPI(...) ════════════════════

TASKS_DB = "tasks.db"

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
    """
    On every server startup: any task left as 'running'
    from a previous crash gets reset to 'pending'.
    Without this, crashed tasks stay stuck forever.
    """
    conn = get_tasks_db()
    conn.execute("""
        UPDATE tasks
        SET status = 'pending', started_at = NULL
        WHERE status = 'running'
    """)
    conn.commit()
    conn.close()

# Call both at startup
init_tasks_db()
reset_orphaned_tasks()

# Worker state — asyncio.Event is cleaner than a plain bool
worker_event  = asyncio.Event()   # set = worker is running
task_db_lock  = asyncio.Lock()    # serializes all DB writes


# ══ STEP 3 — COORDINATOR WRAPPER ════════════════════════════
# Uses your exact .invoke() pattern from coordinator.py

def run_coordinator_sync(prompt: str) -> str:
    """
    Synchronous wrapper around your LangGraph coordinator.
    Called via asyncio.to_thread() so it does not block FastAPI.
    """
    from coordinator import coordinator  # your compiled StateGraph
    initial_state = {
        "messages":     [{"role": "user", "content": prompt}],
        "active_agent": "",
        "task":         prompt,
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    }
    result = coordinator.invoke(initial_state)

    # Extract response text from final state
    if "messages" in result and result["messages"]:
        return result["messages"][-1].content
    elif "result" in result and result["result"]:
        return result["result"]
    else:
        raise ValueError(f"Unexpected coordinator output: {result}")


# ══ STEP 4 — BACKGROUND WORKER ══════════════════════════════

async def task_worker():
    """
    Sequential task queue worker.
    - Runs tasks one at a time (Llama3 on CPU cannot handle parallel)
    - Self-restarting on crash (marks task failed, sleeps, continues)
    - Stops cleanly when queue is empty
    - asyncio.to_thread() keeps FastAPI /ask responsive during execution
    """
    if worker_event.is_set():
        return  # already running

    worker_event.set()
    print("[task_worker] started")

    while True:
        task_id = None
        try:
            # ── Pick next pending task ────────────────────────
            async with task_db_lock:
                conn = get_tasks_db()
                cur  = conn.cursor()
                cur.execute(
                    "SELECT id, prompt FROM tasks WHERE status='pending' ORDER BY id LIMIT 1"
                )
                row = cur.fetchone()

                if not row:
                    conn.close()
                    break  # queue empty — stop worker cleanly

                task_id, prompt = row
                cur.execute(
                    "UPDATE tasks SET status='running', started_at=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), task_id),
                )
                conn.commit()
                conn.close()

            print(f"[task_worker] running task {task_id}")

            # ── Run coordinator in thread (non-blocking) ──────
            result = await asyncio.to_thread(run_coordinator_sync, prompt)

            # ── Save result ───────────────────────────────────
            async with task_db_lock:
                conn = get_tasks_db()
                conn.execute(
                    """UPDATE tasks
                       SET status='done', result=?, finished_at=?
                       WHERE id=?""",
                    (result, datetime.now(timezone.utc).isoformat(), task_id),
                )
                conn.commit()
                conn.close()

            print(f"[task_worker] task {task_id} done")

        except Exception as e:
            print(f"[task_worker] task {task_id} failed: {e}")

            # Mark current task as failed if we started it
            if task_id is not None:
                try:
                    async with task_db_lock:
                        conn = get_tasks_db()
                        conn.execute(
                            """UPDATE tasks
                               SET status='failed', error=?, finished_at=?
                               WHERE id=?""",
                            (str(e), datetime.now(timezone.utc).isoformat(), task_id),
                        )
                        conn.commit()
                        conn.close()
                except Exception as db_err:
                    print(f"[task_worker] failed to update DB: {db_err}")

            # Sleep before next task — avoid tight loop on persistent errors
            await asyncio.sleep(5)
            continue  # keep worker alive, try next task

    worker_event.clear()
    print("[task_worker] queue empty, stopped")


# ══ STEP 5 — ENDPOINTS ══════════════════════════════════════

@app.post("/tasks/create")
async def create_task(data: dict):
    """Create a new task. Returns task_id."""
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


@app.post("/tasks/run")
async def run_tasks():
    """Start the background worker if not already running."""
    if worker_event.is_set():
        return {"message": "queue already running"}
    asyncio.create_task(task_worker())
    return {"message": "task queue started"}


@app.get("/tasks/status")
async def task_status():
    """Get all tasks with their current status."""
    conn = get_tasks_db()
    rows = conn.execute(
        """SELECT id, title, status, agents, created_at, started_at, finished_at
           FROM tasks ORDER BY id DESC"""
    ).fetchall()
    conn.close()

    return {"tasks": [
        {
            "id":       r[0],
            "title":    r[1],
            "status":   r[2],
            "agents":   r[3],
            "created":  r[4],
            "started":  r[5],
            "finished": r[6],
        }
        for r in rows
    ]}


@app.get("/tasks/results/{task_id}")
async def task_result(task_id: int):
    """Get the full result of a completed task."""
    conn = get_tasks_db()
    row = conn.execute(
        "SELECT id, title, status, result, error, agents FROM tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"error": f"task {task_id} not found"}

    return {
        "id":     row[0],
        "title":  row[1],
        "status": row[2],
        "result": row[3],
        "error":  row[4],
        "agents": row[5],
    }


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """Delete a task (only if pending or done — not if running)."""
    async with task_db_lock:
        conn = get_tasks_db()
        row = conn.execute(
            "SELECT status FROM tasks WHERE id=?", (task_id,)
        ).fetchone()

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


# ══ QUICK TEST (run in terminal after restarting uvicorn) ════
#
# Create a task:
#   curl -X POST http://localhost:8000/tasks/create \
#     -H "Content-Type: application/json" \
#     -d '{"title":"Test task","prompt":"What is DNS?","agents":["it_networking"]}'
#
# Start the queue:
#   curl -X POST http://localhost:8000/tasks/run
#
# Check status:
#   curl http://localhost:8000/tasks/status
#
# Get result (replace 1 with your task_id):
#   curl http://localhost:8000/tasks/results/1
