import subprocess

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

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

# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="it_networking",
    prompt=IT_SYSTEM_PROMPT,
    probe_intro="Here are the live diagnostic results from this system:",
    probe_outro="Now answer the user's question using these real results.",
    probes=(
        Probe(
            triggers=("ping", "latency", "slow", "speed", "connection"),
            label="PING google.com",
            run=lambda _task: ping_host("google.com"),
        ),
        Probe(
            triggers=("interface", "ip", "wifi", "ethernet", "network"),
            label="NETWORK INTERFACES",
            run=lambda _task: check_network_interfaces(),
        ),
        Probe(
            triggers=("dns", "domain", "resolve", "website"),
            label="DNS CHECK",
            run=lambda _task: check_dns(),
        ),
        Probe(
            triggers=("port", "service", "listening", "firewall"),
            label="OPEN PORTS",
            run=lambda _task: check_open_ports(),
        ),
    ),
)

it_agent = Agent(SPEC)
