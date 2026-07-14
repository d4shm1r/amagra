import os
import json
from datetime import datetime

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── System Prompt ─────────────────────────────────────────────
KNOWLEDGE_SYSTEM_PROMPT = """
{user_profile}
You are the Knowledge & Learning agent.
Your job: teach clearly, correct wrong analogies directly, skip the cheerleading.
You are a patient, structured, and inspiring tutor.
Your expertise covers:
- IT fundamentals: networking, operating systems, hardware
- Programming concepts from beginner to advanced
- AI and machine learning concepts made accessible
- Breaking down complex topics into digestible lessons
- Socratic teaching: asking questions that guide discovery
- Spaced repetition and learning best practices
- Creating study plans and learning roadmaps
- Analogies and real-world examples for abstract concepts

Response style:
- One sentence definition first. Always.
- If the question is simple → stop there or add one short clarification.
- If the question asks for depth → then expand with structure and details.
- Use basic analogies to familiar things.
- Short by default. No multi-step lessons unless explicitly requested.
- No self-checks unless asked.
- Correct wrong analogies directly.
"""
# ── Tools ─────────────────────────────────────────────────────
def save_lesson(topic: str, content: str) -> str:
    """Save a lesson to the personal knowledge base."""
    lessons_dir = os.path.join(_ROOT, "memory", "lessons")
    os.makedirs(lessons_dir, exist_ok=True)
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "_" for c in topic)
    filename = f"{safe_topic[:50]}_{datetime.now().strftime('%Y%m%d')}.md"
    path = os.path.join(lessons_dir, filename)
    full_content = (
        f"# Lesson: {topic}\n"
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"{content}"
    )
    try:
        with open(path, 'w') as f:
            f.write(full_content)
        return f"✅ Lesson saved: {path}"
    except Exception as e:
        return f"❌ Save failed: {str(e)}"

def load_learning_progress() -> dict:
    """Load the student's learning progress tracker."""
    progress_file = os.path.join(_ROOT, "memory", "learning_progress.json")
    try:
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                return json.load(f)
        return {"topics_covered": [], "current_path": "IT Fundamentals", "lessons_completed": 0}
    except Exception:
        return {"topics_covered": [], "current_path": "IT Fundamentals", "lessons_completed": 0}

def _is_real_lesson_topic(text: str) -> bool:
    """Filter out conversational fragments and junk so progress reflects real questions."""
    if not text or len(text) > 100:
        return False
    if "\n" in text:
        return False
    text_lower = text.lower().strip()
    bad_starts = ("i will", "i want", "i feel", "well ", "when ", "a phase", "phase ")
    if text_lower.startswith(bad_starts):
        return False
    return True

def save_learning_progress(topic: str) -> str:
    """Update learning progress after a lesson."""
    progress_file = os.path.join(_ROOT, "memory", "learning_progress.json")
    progress = load_learning_progress()
    if _is_real_lesson_topic(topic) and topic not in progress["topics_covered"]:
        progress["topics_covered"].append(topic)
        progress["lessons_completed"] += 1
        progress["last_lesson"]   = topic
        progress["last_date"]     = datetime.now().strftime('%Y-%m-%d')

    try:
        os.makedirs(os.path.dirname(progress_file), exist_ok=True)
        with open(progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
        return (
            f"✅ Progress updated: {progress['lessons_completed']} lessons completed.\n"
            f"Topics covered: {', '.join(progress['topics_covered'][-5:])}"
        )
    except Exception as e:
        return f"❌ Progress save failed: {str(e)}"

def get_learning_roadmap(subject: str) -> str:
    """Return a structured learning roadmap for common subjects."""
    roadmaps = {
        "networking": [
            "1. OSI Model — the 7 layers explained",
            "2. TCP/IP vs UDP — when to use which",
            "3. IP Addressing — IPv4, subnets, CIDR",
            "4. DNS — how domain names resolve",
            "5. DHCP — automatic IP assignment",
            "6. Routing — how packets find their path",
            "7. Firewalls & NAT — network security basics",
            "8. Wi-Fi standards — 802.11 a/b/g/n/ac/ax",
            "9. VLANs — network segmentation",
            "10. VPN — tunneling and encryption",
        ],
        "python": [
            "1. Variables, types, and basic operations",
            "2. Control flow — if/else, loops",
            "3. Functions — def, args, return values",
            "4. Lists, dicts, sets, tuples",
            "5. File I/O — reading and writing files",
            "6. Error handling — try/except",
            "7. Modules and packages — import system",
            "8. Classes and OOP basics",
            "9. List comprehensions and generators",
            "10. Virtual environments and pip",
        ],
        "ai": [
            "1. What is AI? ML vs DL vs LLMs",
            "2. Supervised vs Unsupervised learning",
            "3. Neural networks — neurons and layers",
            "4. Training — loss functions and backprop",
            "5. Overfitting — what it is and how to fix it",
            "6. LLMs — how transformers work",
            "7. Embeddings — turning words into numbers",
            "8. RAG — giving LLMs external knowledge",
            "9. Agents — LLMs that take actions",
            "10. Fine-tuning vs prompt engineering",
        ],
        "linux": [
            "1. Filesystem hierarchy — where everything lives",
            "2. Basic commands — ls, cd, cp, mv, rm",
            "3. Permissions — chmod, chown, rwx",
            "4. Users and groups — sudo and root",
            "5. Package management — apt, snap",
            "6. Processes — ps, top, kill, systemctl",
            "7. Shell scripting — bash basics",
            "8. SSH — remote access and keys",
            "9. Networking commands — ip, ss, ping, nmap",
            "10. Cron — scheduling automated tasks",
        ],
    }
    for key, steps in roadmaps.items():
        if key in subject.lower():
            return f"📚 Learning Roadmap: {key.title()}\n\n" + "\n".join(steps)
    return f"📚 No preset roadmap for '{subject}'. I'll create a custom learning path for you."

def list_completed_lessons() -> str:
    """Show all lessons completed so far."""
    progress = load_learning_progress()
    if not progress["topics_covered"]:
        return "📖 No lessons completed yet — let's start learning!"
    lines = [
        "📖 Learning Progress",
        f"Total lessons: {progress['lessons_completed']}",
        f"Current path: {progress.get('current_path', 'IT Fundamentals')}",
        f"Last lesson: {progress.get('last_lesson', 'none')}",
        "\nTopics covered:",
    ]
    for topic in progress["topics_covered"]:
        lines.append(f"  ✅ {topic}")
    return "\n".join(lines)

# ── Probes ────────────────────────────────────────────────────
def _roadmap_probe(task: str) -> str:
    """A roadmap only fires when the task names a subject we have one for —
    mentioning "learn" alone contributes nothing."""
    lowered = task.lower()
    for subject in ["networking", "python", "ai", "linux"]:
        if subject in lowered:
            return get_learning_roadmap(subject)
    return ""


def _progress_probe(_task: str) -> str:
    progress = load_learning_progress()
    topics = ", ".join(progress["topics_covered"]) or "none yet"
    return f"Lessons completed: {progress['lessons_completed']}\nTopics: {topics}"


def _record_lesson(task: str, answer: str) -> None:
    """The one agent with side effects past memory: it files the lesson and
    advances the student's progress."""
    save_lesson(task[:60], answer)
    print(f"\n💾 {save_learning_progress(task[:60])}")


# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="knowledge_learning",
    prompt=KNOWLEDGE_SYSTEM_PROMPT,
    memory_kind="lesson",
    probe_intro="Student context:",
    probe_outro="Teach accordingly.",
    probes=(
        Probe(
            triggers=("roadmap", "path", "where to start", "learn", "study plan"),
            label="ROADMAP",
            run=_roadmap_probe,
        ),
        Probe(
            triggers=("progress", "history", "what have i", "lessons"),
            label="STUDENT PROGRESS",
            run=_progress_probe,
        ),
    ),
    after=_record_lesson,
)

knowledge_agent = Agent(SPEC)
