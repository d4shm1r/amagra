# PATCH — replace the existing save_to_memory() in memory_context.py
# with this version. Everything else in the file stays identical.
#
# Changes vs original:
#   Line +1: import should_save from memory_filter
#   Lines +2-4: call should_save() before embedding; drop if rejected
#
# That's it. No other changes.

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
        from memory_filter import should_save          # ← NEW
        ok_to_save, reason = should_save(             # ← NEW
            content.strip(), mem_type, agent_name     # ← NEW
        )                                             # ← NEW
        if not ok_to_save:                            # ← NEW
            print(f"[memory] ⏭ skipped {agent_name} ({mem_type}): {reason}")  # ← NEW
            return                                    # ← NEW

        from memory_db import save
        ok = save(agent_name, mem_type, content.strip(), metadata)
        if ok:
            print(f"[memory] ✅ saved to {agent_name} ({mem_type})")
        else:
            print(f"[memory] ⚠️ save returned False for {agent_name}")
    except Exception as e:
        print(f"[memory_context] save_to_memory failed silently: {e}")
