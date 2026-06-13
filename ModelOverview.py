#!/usr/bin/env python3
# ~/agentic-ai/ModelOverview.py
# ─────────────────────────────────────────────────────────────
# Generates ModelOverview.md — a shareable snapshot of your
# 9-agent system's current state, memory, and growth.
#
# Usage:
#   cd ~/agentic-ai
#   source ~/langgraph-env/bin/activate
#   python3 ModelOverview.py
#
# Output: ~/agentic-ai/ModelOverview.md
# Share:  Paste into any chatbot, upload to Claude, or open in
#         any markdown viewer.
# ─────────────────────────────────────────────────────────────

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
OUTPUT_FILE = PROJECT_DIR / "ModelOverview.md"

AGENTS = [
    {"id": "coordinator",        "label": "Coordinator",         "icon": "👑"},
    {"id": "it_networking",      "label": "IT & Networking",      "icon": "🌐"},
    {"id": "python_dev",         "label": "Python Dev",           "icon": "🐍"},
    {"id": "dotnet_dev",         "label": "Blazor Dev",           "icon": "⚡"},
    {"id": "ai_ml",              "label": "AI & ML",              "icon": "🤖"},
    {"id": "documents",          "label": "Documents",            "icon": "📄"},
    {"id": "personal_projects",  "label": "Personal Projects",    "icon": "🎯"},
    {"id": "research",           "label": "Research",             "icon": "🔬"},
    {"id": "knowledge_learning", "label": "Knowledge & Learning", "icon": "📚"},
]

# ── Data collectors ──────────────────────────────────────────

def get_memory_stats():
    """Read memory_db.db and return per-agent stats."""
    db_path = PROJECT_DIR / "memory" / "agent_memory.db"
    if not db_path.exists():
        return {}, 0

    conn = sqlite3.connect(str(db_path))
    stats = {}
    total = 0

    for agent in AGENTS:
        aid = agent["id"]
        rows = conn.execute(
            "SELECT mem_type, content, timestamp FROM memories WHERE agent_name=? ORDER BY id DESC",
            (aid,)
        ).fetchall()
        stats[aid] = {
            "count":   len(rows),
            "by_type": {},
            "recent":  [],
        }
        for row in rows:
            mtype, content, ts = row
            stats[aid]["by_type"][mtype] = stats[aid]["by_type"].get(mtype, 0) + 1
            if len(stats[aid]["recent"]) < 3:
                stats[aid]["recent"].append({
                    "type":    mtype,
                    "content": content[:200],
                    "ts":      ts,
                })
        total += len(rows)

    conn.close()
    return stats, total


def get_task_stats():
    """Read tasks.db and return summary."""
    db_path = PROJECT_DIR / "tasks.db"
    if not db_path.exists():
        return [], {}

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT id, title, status, agents, result, created_at, finished_at FROM tasks ORDER BY id"
    ).fetchall()
    conn.close()

    tasks = []
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
    for row in rows:
        tid, title, status, agents, result, created, finished = row
        tasks.append({
            "id":      tid,
            "title":   title,
            "status":  status,
            "agents":  agents,
            "result":  (result or "")[:300],
            "created": created,
            "finished": finished,
        })
        counts[status] = counts.get(status, 0) + 1

    return tasks, counts


def get_lesson_files():
    """List lesson markdown files."""
    path = PROJECT_DIR / "memory" / "lessons"
    if not path.exists():
        return []
    return [f.name for f in sorted(path.glob("*.md"))]


def get_research_files():
    """List research markdown files."""
    path = PROJECT_DIR / "memory" / "research"
    if not path.exists():
        return []
    return [f.name for f in sorted(path.glob("*.md"))]


def get_projects():
    """Read projects.json."""
    path = PROJECT_DIR / "memory" / "projects.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def get_agent_file_stats():
    """Check which agent files exist and their sizes."""
    agents_dir = PROJECT_DIR / "agents"
    result = {}
    for agent in AGENTS:
        if agent["id"] == "coordinator":
            p = PROJECT_DIR / "coordinator.py"
        else:
            p = agents_dir / f"{agent['id']}.py"
        result[agent["id"]] = {
            "exists": p.exists(),
            "size":   p.stat().st_size if p.exists() else 0,
            "memory_wired": p.exists() and "get_memory_context" in p.read_text() if p.exists() else False,
        }
    return result


# ── Report builder ───────────────────────────────────────────

def build_report():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    memory_stats, total_memories = get_memory_stats()
    tasks, task_counts           = get_task_stats()
    lessons                      = get_lesson_files()
    research_files               = get_research_files()
    projects                     = get_projects()
    file_stats                   = get_agent_file_stats()

    total_done_tasks = task_counts.get("done", 0)

    lines = []

    # ── HEADER ──
    lines += [
        "# 🤖 Agentic AI — Model Overview",
        "",
        f"**Generated:** {now}",
        "**System:** 9-agent local AI on Ubuntu Linux",
        "**Stack:** LangGraph v1.0 · phi4-mini via Ollama · FastAPI · SQLite + embeddings",
        "**Location:** ~/agentic-ai",
        "",
        "---",
        "",
    ]

    # ── SYSTEM STATUS ──
    lines += [
        "## 📊 System Status",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total memories in SQLite | {total_memories} |",
        f"| Tasks completed | {total_done_tasks} |",
        f"| Lessons saved | {len(lessons)} |",
        f"| Research files | {len(research_files)} |",
        f"| Agents with memory wired | {sum(1 for v in file_stats.values() if v['memory_wired'])} / 9 |",
        "",
    ]

    # ── MEMORY GROWTH PER AGENT ──
    lines += [
        "## 🧠 Memory Growth Per Agent",
        "",
        "| Agent | Total Memories | Types |",
        "|-------|---------------|-------|",
    ]
    for agent in AGENTS:
        aid   = agent["id"]
        stats = memory_stats.get(aid, {"count": 0, "by_type": {}})
        types = ", ".join([f"{k}:{v}" for k, v in stats["by_type"].items()]) or "—"
        bar   = "█" * min(stats["count"], 20) + "░" * max(0, 20 - stats["count"])
        lines.append(f"| {agent['icon']} {agent['label']} | {stats['count']} `{bar}` | {types} |")

    lines.append("")

    # ── RECENT MEMORIES (what the system actually knows) ──
    lines += [
        "## 💾 Recent Memories (what agents have learned)",
        "",
    ]
    for agent in AGENTS:
        aid   = agent["id"]
        stats = memory_stats.get(aid, {"count": 0, "recent": []})
        if not stats["recent"]:
            continue
        lines.append(f"### {agent['icon']} {agent['label']}")
        lines.append("")
        for entry in stats["recent"]:
            snippet = entry["content"].replace("\n", " ").strip()[:180]
            lines.append(f"- **[{entry['type']}]** {snippet}…")
        lines.append("")

    if total_memories == 0:
        lines += ["> No memories saved yet — start chatting to build memory.", ""]

    # ── TASK HISTORY ──
    lines += [
        "## ⚡ Task Queue History",
        "",
        f"**Summary:** {task_counts.get('done',0)} done · {task_counts.get('failed',0)} failed · {task_counts.get('pending',0)} pending",
        "",
    ]
    if tasks:
        for task in tasks:
            status_icon = "✅" if task["status"] == "done" else "❌" if task["status"] == "failed" else "⏳"
            lines.append(f"**{status_icon} {task['title']}** (agents: {task['agents'] or 'coordinator'})")
            if task["result"]:
                snippet = task["result"].replace("\n", " ").strip()[:200]
                lines.append(f"> {snippet}…")
            lines.append("")
    else:
        lines += ["> No tasks run yet.", ""]

    # ── KNOWLEDGE FILES ──
    if lessons or research_files:
        lines += [
            "## 📚 Saved Knowledge Files",
            "",
        ]
        if lessons:
            lines.append(f"**Lessons ({len(lessons)}):**")
            for f in lessons:
                lines.append(f"- {f}")
            lines.append("")
        if research_files:
            lines.append(f"**Research ({len(research_files)}):**")
            for f in research_files:
                lines.append(f"- {f}")
            lines.append("")

    # ── PROJECTS ──
    if projects:
        lines += [
            "## 🎯 Personal Projects in Memory",
            "",
        ]
        for p in projects:
            if isinstance(p, dict):
                name = p.get("name", p.get("title", str(p)[:60]))
                lines.append(f"- **{name}**")
            else:
                lines.append(f"- {str(p)[:100]}")
        lines.append("")

    # ── AGENT WIRING STATUS ──
    lines += [
        "## 🔌 Agent Wiring Status",
        "",
        "| Agent | File Exists | Size | Memory Wired |",
        "|-------|------------|------|-------------|",
    ]
    for agent in AGENTS:
        aid  = agent["id"]
        fs   = file_stats.get(aid, {})
        exists = "✅" if fs.get("exists") else "❌"
        size   = f"{fs.get('size', 0) // 1024}KB"
        wired  = "✅ Yes" if fs.get("memory_wired") else "❌ No"
        lines.append(f"| {agent['icon']} {agent['label']} | {exists} | {size} | {wired} |")
    lines.append("")

    # ── HOW TO USE THIS FILE ──
    lines += [
        "## 🤝 How to Use This File for Feedback",
        "",
        "Paste this entire file into any AI chatbot with one of these prompts:",
        "",
        "**For architecture review:**",
        "```",
        "Here is a full overview of my local 9-agent AI system.",
        "Review the memory growth, task history, and agent wiring.",
        "What is working well, what looks weak, and what should I",
        "focus on improving next? Be specific and direct.",
        "```",
        "",
        "**For growth analysis:**",
        "```",
        "Here is my AI system's current state after [X weeks] of use.",
        "Analyze the memory distribution across agents.",
        "Which agents are being underused? Which knowledge gaps",
        "should I address by asking specific questions?",
        "```",
        "",
        "**For bug hunting:**",
        "```",
        "Here is my 9-agent local AI system overview.",
        "Based on the memory counts and task results,",
        "what failure modes or silent bugs might exist",
        "that I would not notice in daily use?",
        "```",
        "",
        "---",
        "*Generated by ModelOverview.py — run anytime to get a fresh snapshot.*",
    ]

    return "\n".join(lines)



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
        "\n## Latest Snapshot (auto-updated)\n"
        f"**Generated:** {now}  \n"
        f"**Memories:** {total_memories}  \n"
        f"**Tasks:** {task_counts.get('done',0)} done · "
        f"{task_counts.get('failed',0)} failed · "
        f"{task_counts.get('pending',0)} pending  \n"
    )
    text = tracker_path.read_text()
    pattern = r"\n## Latest Snapshot.*"
    if re.search(pattern, text, re.DOTALL):
        text = re.sub(pattern, snapshot, text, flags=re.DOTALL)
    else:
        text = text.rstrip() + "\n" + snapshot + "\n"
    tracker_path.write_text(text)
    print("  tracker.md snapshot updated")

# ── Main ─────────────────────────────────────────────────────

def main():
    print("Generating ModelOverview.md...")
    report = build_report()
    OUTPUT_FILE.write_text(report)
    print(f"✅ Written to {OUTPUT_FILE}")
    print(f"   {len(report.splitlines())} lines, {len(report)} characters")
    print()
    print("Share options:")
    print(f"  Paste into chatbot:  cat {OUTPUT_FILE}")
    print(f"  Open in editor:      code {OUTPUT_FILE}")
    print(f"  Copy to clipboard:   xclip -selection clipboard < {OUTPUT_FILE}")
    print()

    update_tracker_snapshot()

    # Quick summary to terminal
    _, total = get_memory_stats()
    _, counts = get_task_stats()
    print("Current snapshot:")
    print(f"  Total memories: {total}")
    print(f"  Tasks done:     {counts.get('done', 0)}")


if __name__ == "__main__":
    main()
