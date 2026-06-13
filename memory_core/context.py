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
import threading as _threading
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Thread-local: memory IDs excluded during a fork replay
_fork_local = _threading.local()

def _set_fork_excluded_ids(ids) -> None:
    _fork_local.excluded_ids = set(ids or [])

def _clear_fork_excluded_ids() -> None:
    _fork_local.excluded_ids = set()


def get_memory_context(query: str, agent_name: str, top_k: int = 3, min_score: float = 0.65) -> str:
    """
    Semantic search over stored memories using the active backend (FAISS or SQLite).
    Returns a formatted string to inject into the agent's system prompt.
    Returns "" if nothing relevant found or on any error.

    min_score 0.65 = reasonably relevant (not exact match required)
    Searches both agent-specific AND cross-agent memories.
    """
    if not query or not query.strip():
        return ""
    try:
        from memory_core.backend import get_backend
        backend = get_backend()
        records = backend.retrieve(query.strip(), k=top_k, agent_name=None,
                                   caller="memory_context")
        relevant = [r for r in records if r.score >= min_score]
        _excl = getattr(_fork_local, 'excluded_ids', set())
        if _excl:
            relevant = [r for r in relevant if getattr(r, 'id', None) not in _excl]
        if not relevant:
            return ""

        try:
            import cognition.context_snapshot as _cs
            _cs.record_memories(relevant)
        except Exception:
            pass

        lines = ["[MEMORY — relevant context from past sessions:]"]
        for r in relevant:
            agent   = r.agent.replace("_", " ")
            mtype   = r.mem_type
            content = r.content.strip()
            if len(content) > 300:
                content = content[:300] + "…"
            lines.append(f"• [{agent} / {mtype} / relevance {r.score:.2f}] {content}")

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
        from memory_core.filter import should_save, clean_content   # ← updated
        content = clean_content(content.strip())               # ← NEW
        ok_to_save, reason = should_save(content, mem_type, agent_name)
        if not ok_to_save:
            print(f"[memory] ⏭ skipped {agent_name} ({mem_type}): {reason}")
            return
    except Exception:
        pass
        
    from memory_core.backend import get_backend
    get_backend().store(content.strip(), agent_name, mem_type, metadata)


# ── Memory type guide per agent ─────────────────────────────
# it_networking     → "chat"     general IT responses
# python_dev        → "code"     code it writes
# dotnet_dev        → "code"     Blazor components
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
