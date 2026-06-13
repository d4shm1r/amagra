from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
import subprocess
import sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from models.llm import llm

# ── System Prompt ─────────────────────────────────────────────
IT_SYSTEM_PROMPT = """
{user_profile}
You are an expert IT & Networking specialist agent.
You are a personal sysadmin for home and office networks.
Your expertise covers:
- Wi-Fi troubleshooting and optimization
- Router configuration and diagnostics
- Network security best practices
- DNS, DHCP, IP addressing
- Linux networking commands

Always give specific, actionable advice with exact commands.
When you use a tool, explain what it found and what it means.
Be concise but thorough."""

# ── Tools ─────────────────────────────────────────────────────
def ping_host(host: str) -> str:
    """Ping a host and return latency results."""
    try:
        result = subprocess.run(
            ["ping", "-c", "4", host],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"Ping failed: {str(e)}"

def check_network_interfaces() -> str:
    """Show all active network interfaces and their status."""
    try:
        result = subprocess.run(
            ["ip", "addr", "show"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception as e:
        return f"Interface check failed: {str(e)}"

def check_dns(domain: str = "google.com") -> str:
    """Check DNS resolution for a domain."""
    try:
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception as e:
        return f"DNS check failed: {str(e)}"

def check_open_ports(host: str = "localhost") -> str:
    """Check commonly used ports on a host."""
    try:
        result = subprocess.run(
            ["ss", "-tulnp"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception as e:
        return f"Port check failed: {str(e)}"

# ── Agent Node ────────────────────────────────────────────────
def it_agent_node(state: AgentState):
    """Main IT & Networking agent node."""
    task = state.get("task", "")

    # -- Memory: search before responding --
    _mem_ctx = get_memory_context(task, "it_networking")
    from core.user_profile import get_profile_context
    _effective_prompt = IT_SYSTEM_PROMPT.format(user_profile=get_profile_context())
    if _mem_ctx:
        _effective_prompt += "\n\n" + _mem_ctx
    # ----------------------------------------


    # Auto-run relevant tools based on task keywords
    tool_context = ""

    if any(word in task.lower() for word in ["ping", "latency", "slow", "speed", "connection"]):
        tool_context += f"\n[PING google.com]\n{ping_host('google.com')}"

    if any(word in task.lower() for word in ["interface", "ip", "wifi", "ethernet", "network"]):
        tool_context += f"\n[NETWORK INTERFACES]\n{check_network_interfaces()}"

    if any(word in task.lower() for word in ["dns", "domain", "resolve", "website"]):
        tool_context += f"\n[DNS CHECK]\n{check_dns()}"

    if any(word in task.lower() for word in ["port", "service", "listening", "firewall"]):
        tool_context += f"\n[OPEN PORTS]\n{check_open_ports()}"

    # Build messages for LLM
    from core.context_tools import trim_messages
    trimmed = trim_messages(state["messages"], max_messages=10)
    messages = [
        SystemMessage(content=_effective_prompt),
        *trimmed,
    ]

    # Inject tool results if any were collected
    if tool_context:
        from langchain_core.messages import HumanMessage
        messages.append(HumanMessage(
            content=f"Here are the live diagnostic results from this system:\n{tool_context}\n\nNow answer the user's question using these real results."
        ))

    response = llm.invoke(messages)

    # -- Memory: save after responding --
    save_to_memory("it_networking", "chat", response.content,
                   {"task": task[:120] if task else ""})
    # ------------------------------------


    return {
        "messages":     [response],
        "active_agent": "it_networking",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_it_agent():
    graph = StateGraph(AgentState)
    graph.add_node("it_agent", it_agent_node)
    graph.add_edge(START, "it_agent")
    graph.add_edge("it_agent", END)
    return graph.compile()

it_agent = build_it_agent()

# ── Standalone Test ───────────────────────────────────────────
if __name__ == "__main__":
    print("🌐 Testing IT & Networking Agent...\n")
    result = it_agent.invoke({
        "messages":     [{"role": "user", "content": "Check my network connection and DNS, is everything working?"}],
        "active_agent": "",
        "task":         "Check my network connection and DNS, is everything working?",
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    })
    print("── IT AGENT RESPONSE ──")
    print(result["messages"][-1].content)
