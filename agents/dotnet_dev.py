import subprocess

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

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

# ── Spec ──────────────────────────────────────────────────────
# Two probes share one trigger set, so an SDK question reports both blocks —
# the same pairing the hand-written node did.
SPEC = AgentSpec(
    name="dotnet_dev",
    prompt=DOTNET_SYSTEM_PROMPT,
    probe_intro="System tool results:",
    probes=(
        Probe(
            triggers=("sdk", "version", "dotnet", "installed"),
            label=".NET SDK",
            run=lambda _task: check_dotnet_sdk(),
        ),
        Probe(
            triggers=("sdk", "version", "dotnet", "installed"),
            label=".NET RUNTIMES",
            run=lambda _task: check_dotnet_runtimes(),
        ),
    ),
)

dotnet_agent = Agent(SPEC)
