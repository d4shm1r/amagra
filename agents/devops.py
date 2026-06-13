from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import subprocess, sys
from memory_core.context import get_memory_context, save_to_memory
import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from models.llm import llm
from core.context_tools import trim_messages

# ── System Prompt ─────────────────────────────────────────────
DEVOPS_SYSTEM_PROMPT = """
{user_profile}
You are an expert DevOps engineer agent.
Your expertise covers:
- Docker: Dockerfiles, Compose, multi-stage builds, networking, volumes
- Kubernetes: pods, deployments, services, ingress, Helm charts
- CI/CD: GitHub Actions, GitLab CI, Jenkins pipelines
- Linux system administration: systemd, cron, permissions, users
- Bash scripting: automation, error handling, argument parsing
- Infrastructure as Code: Terraform, Ansible basics
- Cloud platforms: AWS (EC2, S3, ECS, Lambda), GCP, Azure basics
- Monitoring: Prometheus, Grafana, log aggregation
- Security: SSH hardening, firewall rules, secrets management
- Git: branching strategies, hooks, advanced workflows

When writing Dockerfiles always include:
- Multi-stage builds for production images
- Non-root user for security
- .dockerignore considerations
- Health check instruction

When writing CI/CD pipelines always include:
- Caching for dependencies
- Separate build/test/deploy stages
- Secret handling (never hardcode credentials)

Always give runnable commands with exact flags. Prefer idempotent solutions."""

# ── Tools ─────────────────────────────────────────────────────
def check_docker() -> str:
    """Check Docker installation and running containers."""
    try:
        version = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=5
        )
        if version.returncode != 0:
            return "Docker not found in PATH"
        info = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}"],
            capture_output=True, text=True, timeout=5
        )
        containers = info.stdout.strip() if info.returncode == 0 else "Cannot list containers"
        return f"{version.stdout.strip()}\n\nRunning containers:\n{containers}"
    except FileNotFoundError:
        return "Docker not installed"
    except Exception as e:
        return f"Docker check failed: {e}"

def check_system_services() -> str:
    """Check key systemd service statuses."""
    services = ["docker", "nginx", "ssh", "ufw"]
    results = []
    for svc in services:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=3
            )
            status = r.stdout.strip()
            results.append(f"  {svc:<12} {status}")
        except Exception:
            results.append(f"  {svc:<12} unknown")
    return "System services:\n" + "\n".join(results)

# ── Agent Node ────────────────────────────────────────────────
def devops_agent_node(state: AgentState):
    task = state.get("task", "")

    _mem_ctx = get_memory_context(task, "devops")
    from core.user_profile import get_profile_context
    _effective_prompt = DEVOPS_SYSTEM_PROMPT.format(user_profile=get_profile_context())
    if _mem_ctx:
        _effective_prompt += f"\n\n{_mem_ctx}"

    tool_context = ""

    if any(w in task.lower() for w in ["docker", "container", "compose", "image"]):
        tool_context += f"\n[DOCKER STATUS]\n{check_docker()}"

    if any(w in task.lower() for w in ["service", "systemd", "nginx", "running", "status"]):
        tool_context += f"\n[SYSTEM SERVICES]\n{check_system_services()}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"System tool results:\n{tool_context}\n\nUse these in your response."
        ))

    response = llm.invoke(messages)

    save_to_memory("devops", "chat", response.content,
                   {"task": task[:120] if task else ""})

    return {
        "messages":     [response],
        "active_agent": "devops",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_devops_agent():
    graph = StateGraph(AgentState)
    graph.add_node("devops_agent", devops_agent_node)
    graph.add_edge(START, "devops_agent")
    graph.add_edge("devops_agent", END)
    return graph.compile()

devops_agent = build_devops_agent()

if __name__ == "__main__":
    result = devops_agent.invoke({
        "messages": [{"role": "user", "content": "What Docker containers are currently running on this machine?"}],
        "active_agent": "", "task": "check running docker containers", "result": "", "next_agent": "", "memory": {},
    })
    print(result["messages"][-1].content)
