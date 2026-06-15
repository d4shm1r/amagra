from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import subprocess
import sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from models.llm import llm
from core.context_tools import trim_messages

# ── System Prompt ─────────────────────────────────────────────
DOTNET_SYSTEM_PROMPT = """
{user_profile}
You are an expert .NET Developer agent.
Your expertise covers:
- C# 12+ modern syntax, patterns, and idioms
- .NET 8/9: console apps, web APIs, background services
- ASP.NET Core: minimal APIs, controllers, middleware, filters
- Blazor Server and Blazor WebAssembly (WASM)
- Entity Framework Core: migrations, queries, relationships
- Dependency injection and service registration patterns
- SignalR for real-time features
- xUnit / NUnit for unit and integration testing
- NuGet package management and project structure
- Docker and deployment for .NET applications
- MAUI for cross-platform desktop/mobile

When writing .NET code always include:
- Full namespace and using statements
- Proper async/await patterns (Task, ValueTask)
- Constructor injection over service locator
- Error handling with try/catch or Result types
- XML doc comments on public APIs

When writing Blazor components always include:
- @page, @inject, @code block structure
- OnInitializedAsync lifecycle method
- Loading and error states for async operations"""

# ── Tools ─────────────────────────────────────────────────────
def check_dotnet_sdk() -> str:
    """Check installed .NET SDK versions."""
    try:
        result = subprocess.run(
            ["dotnet", "--list-sdks"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"Installed .NET SDKs:\n{result.stdout.strip()}"
        return "dotnet CLI not found in PATH"
    except FileNotFoundError:
        return "dotnet CLI not installed"
    except Exception as e:
        return f"SDK check failed: {e}"

def check_dotnet_runtimes() -> str:
    """Check installed .NET runtimes."""
    try:
        result = subprocess.run(
            ["dotnet", "--list-runtimes"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return f"Installed .NET runtimes:\n{result.stdout.strip()}"
        return "dotnet CLI not found"
    except FileNotFoundError:
        return "dotnet CLI not installed"
    except Exception as e:
        return f"Runtime check failed: {e}"

# ── Agent Node ────────────────────────────────────────────────
def dotnet_agent_node(state: AgentState):
    task = state.get("task", "")

    _mem_ctx = get_memory_context(task, "dotnet_dev")
    from core.user_profile import get_profile_context
    _effective_prompt = DOTNET_SYSTEM_PROMPT.format(user_profile=get_profile_context(task))
    if _mem_ctx:
        _effective_prompt += f"\n\n{_mem_ctx}"

    tool_context = ""

    if any(w in task.lower() for w in ["sdk", "version", "dotnet", "installed"]):
        tool_context += f"\n[.NET SDK]\n{check_dotnet_sdk()}"
        tool_context += f"\n[.NET RUNTIMES]\n{check_dotnet_runtimes()}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"System tool results:\n{tool_context}\n\nUse these in your response."
        ))

    response = llm.invoke(messages)

    save_to_memory("dotnet_dev", "chat", response.content,
                   {"task": task[:120] if task else ""})

    return {
        "messages":     [response],
        "active_agent": "dotnet_dev",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_dotnet_agent():
    graph = StateGraph(AgentState)
    graph.add_node("dotnet_agent", dotnet_agent_node)
    graph.add_edge(START, "dotnet_agent")
    graph.add_edge("dotnet_agent", END)
    return graph.compile()

dotnet_agent = build_dotnet_agent()

if __name__ == "__main__":
    result = dotnet_agent.invoke({
        "messages": [{"role": "user", "content": "What .NET SDKs do I have installed?"}],
        "active_agent": "", "task": "check dotnet sdk versions", "result": "", "next_agent": "", "memory": {},
    })
    print(result["messages"][-1].content)
