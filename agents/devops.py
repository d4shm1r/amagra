import subprocess

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

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

# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="devops",
    prompt=DEVOPS_SYSTEM_PROMPT,
    probe_intro="System tool results:",
    probes=(
        Probe(
            triggers=("docker", "container", "compose", "image"),
            label="DOCKER STATUS",
            run=lambda _task: check_docker(),
        ),
        Probe(
            triggers=("service", "systemd", "nginx", "running", "status"),
            label="SYSTEM SERVICES",
            run=lambda _task: check_system_services(),
        ),
    ),
)

devops_agent = Agent(SPEC)
