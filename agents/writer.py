from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
import sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from core.context_tools import trim_messages

# ── System Prompt ─────────────────────────────────────────────
WRITER_SYSTEM_PROMPT = """
{user_profile}
You are an expert Technical Writer and Editor agent.
Your expertise covers:
- Technical documentation: READMEs, API docs, architecture guides
- Markdown: formatting, tables, diagrams, badges
- Blog posts and articles: structure, flow, clarity
- Code comments and inline documentation
- Commit messages and PR descriptions
- Email and professional communication
- Editing and proofreading: grammar, clarity, conciseness
- Style guides: Google Developer Docs, Microsoft Writing Style

When writing technical documentation always include:
- A one-line "what this does" summary at the top
- Prerequisites section if setup is required
- Code examples with context (not raw snippets)
- A table of contents for documents over 300 words

When editing text:
- Fix grammar and spelling
- Remove redundant phrases ("in order to" → "to")
- Prefer active voice over passive
- Keep sentences under 25 words where possible

When writing commit messages:
- Imperative mood: "Add X" not "Added X" or "Adding X"
- 50-char subject line, blank line, body if needed
- Body explains WHY, not what (the diff shows the what)"""

# ── Agent Node ────────────────────────────────────────────────
def writer_agent_node(state: AgentState):
    task = state.get("task", "")

    _mem_ctx = get_memory_context(task, "writer")
    from core.user_profile import get_profile_context
    _effective_prompt = WRITER_SYSTEM_PROMPT.format(user_profile=get_profile_context(task))
    if _mem_ctx:
        _effective_prompt += f"\n\n{_mem_ctx}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    from tools.agent_runtime import respond_with_optional_tools
    response = respond_with_optional_tools(messages, _effective_prompt, task)

    save_to_memory("writer", "chat", response.content,
                   {"task": task[:120] if task else ""})

    return {
        "messages":     [response],
        "active_agent": "writer",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_writer_agent():
    graph = StateGraph(AgentState)
    graph.add_node("writer_agent", writer_agent_node)
    graph.add_edge(START, "writer_agent")
    graph.add_edge("writer_agent", END)
    return graph.compile()

writer_agent = build_writer_agent()

if __name__ == "__main__":
    result = writer_agent.invoke({
        "messages": [{"role": "user", "content": "Write a README for a Python FastAPI project that does JWT authentication."}],
        "active_agent": "", "task": "write readme for fastapi jwt project", "result": "", "next_agent": "", "memory": {},
    })
    print(result["messages"][-1].content)
