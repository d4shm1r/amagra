from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
import sys
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from models.llm import llm

# ── System Prompt ─────────────────────────────────────────────
TERSE_SYSTEM_PROMPT = """You answer in the fewest words possible.

Rules:
- If asked for a command: output the command only. No explanation, no preamble.
- If asked for code: output the code only, in a code block. No commentary.
- If asked for syntax: one line showing the syntax.
- If asked for a definition: one short sentence. No analogy, no expansion.
- Never start with "Sure", "Here is", "You can", "To do this".
- Never end with "Let me know if...", "Hope this helps".
- If the question is ambiguous, pick the most common interpretation and answer. Do not ask.
- If you genuinely cannot answer in one line, give the shortest possible answer and stop.

Examples:
Q: give me the command for new dotnet blazor project
A: dotnet new blazor -o MyApp

Q: git rebase syntax
A: git rebase <base-branch>

Q: what is a daemon one line
A: A background process that runs without direct user interaction.

Q: python list comprehension syntax
A: [expression for item in iterable if condition]
"""

# ── Agent Node ────────────────────────────────────────────────
def terse_agent_node(state: AgentState):
    """Terse agent — one-line answers, no fluff."""
    task = state.get("task", "")

    from core.context_tools import trim_messages
    trimmed = trim_messages(state["messages"], max_messages=4)

    messages = [
        SystemMessage(content=TERSE_SYSTEM_PROMPT),
        *trimmed,
    ]

    response = llm.invoke(messages)

    return {
        "messages":     [response],
        "active_agent": "terse",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_terse_agent():
    graph = StateGraph(AgentState)
    graph.add_node("terse_agent", terse_agent_node)
    graph.add_edge(START, "terse_agent")
    graph.add_edge("terse_agent", END)
    return graph.compile()

terse_agent = build_terse_agent()

# ── Standalone Test ───────────────────────────────────────────
if __name__ == "__main__":
    print("⚡ Testing Terse Agent...\n")
    result = terse_agent.invoke({
        "messages":     [{"role": "user", "content": "give me the command for new dotnet blazor project"}],
        "active_agent": "",
        "task":         "give me the command for new dotnet blazor project",
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    })
    print("── TERSE AGENT RESPONSE ──")
    print(result["messages"][-1].content)
