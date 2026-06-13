import os

PROJECT = os.path.expanduser("~/agentic-ai")

# ── 1. Patch ModelOverview.py ─────────────────────────────────
mo_path = f"{PROJECT}/ModelOverview.py"
with open(mo_path) as f:
    content = f.read()

TRACKER_FUNC = '''
# ── Tracker updater ──────────────────────────────────────────

def update_tracker_snapshot():
    """Write current stats into tracker.md."""
    tracker_path = PROJECT_DIR / "docs" / "tracker.md"
    if not tracker_path.exists():
        return
    _, total_memories = get_memory_stats()
    _, task_counts    = get_task_stats()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    snapshot = (
        "\\n## Latest Snapshot (auto-updated)\\n"
        f"**Generated:** {now}  \\n"
        f"**Memories:** {total_memories}  \\n"
        f"**Tasks:** {task_counts.get('done',0)} done · "
        f"{task_counts.get('failed',0)} failed · "
        f"{task_counts.get('pending',0)} pending  \\n"
    )
    text = tracker_path.read_text()
    pattern = r"\\n## Latest Snapshot.*"
    if re.search(pattern, text, re.DOTALL):
        text = re.sub(pattern, snapshot, text, flags=re.DOTALL)
    else:
        text = text.rstrip() + "\\n" + snapshot + "\\n"
    tracker_path.write_text(text)
    print("  tracker.md snapshot updated")

'''

OLD_MAIN = "# ── Main ─────────────────────────────────────────────────────\n\ndef main():"
assert OLD_MAIN in content, "main pattern not found"
content = content.replace(OLD_MAIN, TRACKER_FUNC + OLD_MAIN, 1)

OLD_SUMMARY = "    # Quick summary to terminal"
assert OLD_SUMMARY in content
content = content.replace(OLD_SUMMARY, "    update_tracker_snapshot()\n\n    # Quick summary to terminal", 1)

# Add import re at top if not present
if "import re" not in content:
    content = content.replace("import json", "import json\nimport re", 1)

with open(mo_path, 'w') as f:
    f.write(content)
print("✓ ModelOverview.py patched")

# ── 2. Add /status endpoint to api.py ────────────────────────
api_path = f"{PROJECT}/api.py"
with open(api_path) as f:
    api = f.read()

if '"/status"' not in api:
    STATUS = '''
@app.get("/status")
def get_status():
    """System status + next pending phases for React."""
    import sqlite3 as _sq
    memories, by_agent = 0, {}
    done, failed, pending = 0, 0, 0
    try:
        conn = _sq.connect("memory/agent_memory.db")
        memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        rows = conn.execute("SELECT agent_name, COUNT(*) FROM memories GROUP BY agent_name").fetchall()
        by_agent = {r[0]: r[1] for r in rows}
        conn.close()
    except Exception: pass
    try:
        conn = _sq.connect("tasks.db")
        done    = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
        failed  = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]
        conn.close()
    except Exception: pass
    return {
        "memories": memories,
        "by_agent": by_agent,
        "tasks": {"done": done, "failed": failed, "pending": pending},
        "model": "llama3:8b-instruct-q3_K_M",
        "gpu": "RTX 2050",
        "next_phases": [
            {"phase": 10, "title": "Continuous Learning",  "items": ["Async memory saves", "Coordinator context window", "Reflection layer"]},
            {"phase": 11, "title": "Belief Mapping Agent", "items": ["Seven-stance taxonomy", "Challenge behavior", "Contradiction flagging"]},
            {"phase": 12, "title": "Hybrid System",        "items": ["Groq API", "LangSmith tracing", "Daily driver"]},
            {"phase": 13, "title": "LangGraph Mastery",    "items": ["ReAct pattern", "Tool calling", "LangSmith"]},
        ],
    }

'''
    api = api.replace('\n@app.get("/metrics")', STATUS + '\n@app.get("/metrics")', 1)
    with open(api_path, 'w') as f:
        f.write(api)
    print("✓ /status endpoint added to api.py")
else:
    print("⏭ /status already exists")

print("\nDone.")
