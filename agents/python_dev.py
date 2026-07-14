import subprocess
import tempfile
import os

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

# Files may only be read from within this directory tree. The temp dir is
# resolved per-OS (gettempdir() = /tmp on Linux/Mac, %TEMP% on Windows) so the
# read jail and the exec scratch file agree across platforms.
_TMP_DIR = tempfile.gettempdir()
_ALLOWED_ROOTS = (
    os.path.abspath(os.path.dirname(__file__) + "/.."),
    _TMP_DIR,
)

# ── System Prompt ─────────────────────────────────────────────
PYTHON_SYSTEM_PROMPT = """
{user_profile}
You are an expert Python Developer agent.
Your expertise covers:
- Clean, idiomatic Python 3.11+ code
- Automation scripts and task scheduling
- Popular libraries: requests, pandas, pathlib, asyncio, FastAPI
- Debugging, profiling, and code review
- Best practices: type hints, docstrings, error handling
- Virtual environments and dependency management

When writing code always include:
- Type hints on all functions
- Docstrings explaining what the code does
- Error handling with try/except
- A working example at the bottom

When reviewing code point out: bugs, style issues, and improvements."""


# ── Tools ─────────────────────────────────────────────────────
def run_python_code(code: str) -> str:
    """Safely execute Python code in a temp file and return output."""
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py',
            delete=False, dir=_TMP_DIR
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True,
            timeout=15
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            return f"✅ Output:\n{result.stdout}"
        else:
            return f"❌ Error:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "❌ Code execution timed out (15s limit)"
    except Exception as e:
        return f"❌ Execution failed: {str(e)}"


def read_python_file(path: str) -> str:
    """Read a Python file — restricted to the project directory and /tmp."""
    try:
        abs_path = os.path.realpath(os.path.expanduser(path))
        if not any(abs_path.startswith(root) for root in _ALLOWED_ROOTS):
            return f"❌ Access denied: {path} is outside the allowed scope"
        with open(abs_path, 'r') as f:
            content = f.read()
        lines = content.split('\n')
        numbered = '\n'.join(f"{i+1:3}: {line}" for i, line in enumerate(lines))
        return f"📄 {path} ({len(lines)} lines):\n{numbered}"
    except FileNotFoundError:
        return f"❌ File not found: {path}"
    except Exception as e:
        return f"❌ Read failed: {str(e)}"


def check_python_env() -> str:
    """Check current Python environment and installed packages."""
    try:
        version = subprocess.run(
            ["python3", "--version"],
            capture_output=True, text=True
        ).stdout.strip()

        pip_list = subprocess.run(
            ["pip", "list", "--format=columns"],
            capture_output=True, text=True
        ).stdout

        return f"🐍 {version}\n\nInstalled packages:\n{pip_list}"
    except Exception as e:
        return f"❌ Env check failed: {str(e)}"


# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="python_dev",
    prompt=PYTHON_SYSTEM_PROMPT,
    memory_kind="code",
    probes=(
        Probe(
            triggers=("environment", "packages", "installed", "version"),
            label="PYTHON ENVIRONMENT",
            run=lambda _task: check_python_env(),
        ),
    ),
)

python_agent = Agent(SPEC)
