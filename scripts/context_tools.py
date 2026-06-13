# No new pip packages needed

from typing import List
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage


def trim_messages(messages: List[BaseMessage], max_messages: int = 20) -> List[BaseMessage]:
    """
    Hard truncate message list to max_messages.
    - Preserves SystemMessage at index 0 if present
    - Injects truncation notice as AIMessage (never HumanMessage)
    - NO summarization — hard cut only (avoids double LLM call)
    - Safe to call on every agent invocation
    """
    if not messages:
        return []

    result = list(messages)

    # Extract system prompt if present
    system_msg = None
    if isinstance(result[0], SystemMessage):
        system_msg = result.pop(0)

    # No trimming needed
    if len(result) <= max_messages:
        return ([system_msg] if system_msg else []) + result

    original_count = len(result)
    result = result[-max_messages:]

    notice = AIMessage(
        content=f"[Context trimmed: {original_count} → {max_messages} messages kept]"
    )
    result = [notice] + result

    if system_msg:
        result = [system_msg] + result

    return result


# ── UNIT TESTS ───────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("CONTEXT TRIM TEST SUITE")
    print("=" * 55)

    def check(name, condition):
        print(f"  {'✓' if condition else '✗'} {name}")
        return condition

    def make_msgs(n, with_system=True):
        msgs = []
        if with_system:
            msgs.append(SystemMessage(content="System prompt"))
        for i in range(n):
            msgs.append(HumanMessage(content=f"msg {i}") if i % 2 == 0
                        else AIMessage(content=f"reply {i}"))
        return msgs

    all_pass = True

    # Test 1 — under limit, nothing changes
    msgs = make_msgs(10)
    out = trim_messages(msgs, max_messages=20)
    all_pass &= check("Under limit: no change", out == msgs)

    # Test 2 — system prompt preserved after trim
    msgs = make_msgs(30)
    out = trim_messages(msgs, max_messages=20)
    all_pass &= check("System prompt at index 0", isinstance(out[0], SystemMessage))
    all_pass &= check("Truncation notice is AIMessage", isinstance(out[1], AIMessage))
    all_pass &= check("Total length correct (system+notice+20)", len(out) == 22)

    # Test 3 — no system prompt
    msgs = make_msgs(30, with_system=False)
    out = trim_messages(msgs, max_messages=20)
    all_pass &= check("No system: notice at index 0", isinstance(out[0], AIMessage))
    all_pass &= check("No system: length = notice+20", len(out) == 21)

    # Test 4 — empty list
    out = trim_messages([])
    all_pass &= check("Empty list returns empty", out == [])

    # Test 5 — single system message
    out = trim_messages([SystemMessage(content="only")])
    all_pass &= check("Single system msg unchanged", len(out) == 1 and isinstance(out[0], SystemMessage))

    # Test 6 — notice is NOT HumanMessage (critical — agents must not reply to it)
    msgs = make_msgs(30)
    out = trim_messages(msgs, max_messages=5)
    notice = out[1] if isinstance(out[0], SystemMessage) else out[0]
    all_pass &= check("Notice is AIMessage not HumanMessage", isinstance(notice, AIMessage))
    all_pass &= check("Notice not HumanMessage", not isinstance(notice, HumanMessage))

    print(f"\n  {'ALL PASS ✅' if all_pass else 'FAILURES FOUND ⚠️'}")
