from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import os, sys, json
from datetime import datetime
from memory_core.context import get_memory_context, save_to_memory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from models.state import AgentState
from models.llm import llm
from core.context_tools import trim_messages

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
        f"📖 Learning Progress",
        f"Total lessons: {progress['lessons_completed']}",
        f"Current path: {progress.get('current_path', 'IT Fundamentals')}",
        f"Last lesson: {progress.get('last_lesson', 'none')}",
        f"\nTopics covered:",
    ]
    for topic in progress["topics_covered"]:
        lines.append(f"  ✅ {topic}")
    return "\n".join(lines)

# ── Agent Node ────────────────────────────────────────────────
def knowledge_agent_node(state: AgentState):
    """Main Knowledge & Learning agent node."""
    task = state.get("task", "")

    # -- Memory: search before responding --
    _mem_ctx = get_memory_context(task, "knowledge_learning")
    from core.user_profile import get_profile_context
    _effective_prompt = KNOWLEDGE_SYSTEM_PROMPT.format(user_profile=get_profile_context())
    if _mem_ctx:
        _effective_prompt = KNOWLEDGE_SYSTEM_PROMPT + chr(10) + chr(10) + _mem_ctx
    # ----------------------------------------

    tool_context = ""

    # Load progress only when user asks about it
    progress = load_learning_progress()

    if any(w in task.lower() for w in ["roadmap", "path", "where to start", "learn", "study plan"]):
        for subject in ["networking", "python", "ai", "linux"]:
            if subject in task.lower():
                tool_context += f"\n[ROADMAP]\n{get_learning_roadmap(subject)}"
                break

    if any(w in task.lower() for w in ["progress", "history", "what have i", "lessons"]):
        tool_context += f"\n[STUDENT PROGRESS]\nLessons completed: {progress['lessons_completed']}\nTopics: {', '.join(progress['topics_covered']) or 'none yet'}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"Student context:\n{tool_context}\n\nTeach accordingly."
        ))

    response = llm.invoke(messages)

    # -- Memory: save after responding --
    save_to_memory("knowledge_learning", "lesson", response.content,
                   {"task": task[:120] if task else ""})
    # ------------------------------------


    # Auto-save lesson and update progress
    save_lesson(task[:60], response.content)
    progress_result = save_learning_progress(task[:60])
    print(f"\n💾 {progress_result}")

    return {
        "messages":     [response],
        "active_agent": "knowledge_learning",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_knowledge_agent():
    graph = StateGraph(AgentState)
    graph.add_node("knowledge_agent", knowledge_agent_node)
    graph.add_edge(START, "knowledge_agent")
    graph.add_edge("knowledge_agent", END)
    return graph.compile()

knowledge_agent = build_knowledge_agent()

# ── Standalone Test ───────────────────────────────────────────
if __name__ == "__main__":
    print("📚 Testing Knowledge & Learning Agent...\n")
    result = knowledge_agent.invoke({
        "messages": [{"role": "user", "content": "Explain how LangGraph StateGraph works. I understand basic Python but I'm new to agent frameworks. Use an analogy to make it click."}],
        "active_agent": "",
        "task":         "Explain LangGraph StateGraph for Python developer new to agents",
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    })
    print("\n── KNOWLEDGE AGENT RESPONSE ──")
    print(result["messages"][-1].content)
