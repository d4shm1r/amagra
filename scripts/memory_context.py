# ~/agentic-ai/memory_context.py
# ─────────────────────────────────────────────────────────────
# Utility used by all 8 specialist agents.
# Two functions only:
#   get_memory_context()  → call BEFORE llm.invoke()
#   save_to_memory()      → call AFTER  llm.invoke()
#
# Both are silent on failure — agents always respond
# even if memory_db is unavailable.
# ─────────────────────────────────────────────────────────────

import sys
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_memory_context(query: str, agent_name: str, top_k: int = 3, min_score: float = 0.65) -> str:
    """
    Search memory_db for relevant past context.
    Returns a formatted string to inject into the agent's system prompt.
    Returns "" if nothing relevant found or on any error.

    min_score 0.65 = reasonably relevant (not exact match required)
    Searches both agent-specific AND cross-agent memories.
    """
    if not query or not query.strip():
        return ""
    try:
        from memory_db import search
        results = search(query.strip(), top_k=top_k, agent_name=None)
        relevant = [r for r in results if r.get("score", 0) >= min_score]
        if not relevant:
            return ""

        lines = ["[MEMORY — relevant context from past sessions:]"]
        for r in relevant:
            agent  = r.get("agent", "?").replace("_", " ")
            mtype  = r.get("type", "?")
            content = r.get("content", "").strip()
            score  = r.get("score", 0)
            if len(content) > 300:
                content = content[:300] + "…"
            lines.append(f"• [{agent} / {mtype} / relevance {score:.2f}] {content}")

        return "\n".join(lines)

    except Exception as e:
        print(f"[memory_context] get_memory_context failed silently: {e}")
        return ""


def save_to_memory(agent_name: str, mem_type: str, content: str, metadata: dict = None) -> None:
    """
    Save agent response to memory_db after llm.invoke().
    Silent on failure — never raises, never blocks the agent.

    agent_name: exact agent id (e.g. "it_networking")
    mem_type:   "chat", "lesson", "research", "project", "code"
    content:    the agent's response text
    metadata:   optional dict (e.g. {"task": "explain DNS"})
    """
    if not content or not content.strip():
        return
    try:
        from memory_db import save
        ok = save(agent_name, mem_type, content.strip(), metadata)
        if ok:
            print(f"[memory] ✅ saved to {agent_name} ({mem_type})")
        else:
            print(f"[memory] ⚠️ save returned False for {agent_name}")
    except Exception as e:
        print(f"[memory_context] save_to_memory failed silently: {e}")


# ── Memory type guide per agent ─────────────────────────────
# it_networking     → "chat"     general IT responses
# python_dev        → "code"     code it writes
# blazor_dev        → "code"     Blazor components
# ai_ml             → "chat"     AI/ML explanations
# documents         → "chat"     document drafts
# personal_projects → "project"  project updates
# research          → "research" research findings
# knowledge_learning→ "lesson"   lessons and tutorials


# ── Standalone test ─────────────────────────────────────────
if __name__ == "__main__":
    print("Testing memory_context.py...")
    print("(Requires Ollama running with nomic-embed-text)")
    print()

    # Test 1: save something
    print("Test 1: saving test entry...")
    save_to_memory("python_dev", "code", "def hello(): return 'Hello World'", {"task": "test"})

    # Test 2: search for it
    print("\nTest 2: searching for relevant context...")
    ctx = get_memory_context("write a python function", "python_dev")
    if ctx:
        print("FOUND context:")
        print(ctx)
    else:
        print("No context found (may need more entries in DB)")

    # Test 3: empty query guard
    print("\nTest 3: empty query guard...")
    ctx2 = get_memory_context("", "it_networking")
    assert ctx2 == "", "Should return empty string for empty query"
    print("PASS — empty query returns empty string")

    # Test 4: save_to_memory with empty content
    print("\nTest 4: empty content guard...")
    save_to_memory("research", "research", "")
    print("PASS — empty content handled silently")

    print("\nAll tests done.")
