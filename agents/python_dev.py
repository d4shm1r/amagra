from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import subprocess
import tempfile
import os
import sys
from memory_core.context import get_memory_context, save_to_memory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.state import AgentState
from core.context_tools import trim_messages

# Files may only be read from within this directory tree.
_ALLOWED_ROOTS = (
    os.path.abspath(os.path.dirname(__file__) + "/.."),
    "/tmp",
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
            delete=False, dir='/tmp'
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

# ── Agent Node ────────────────────────────────────────────────
def python_agent_node(state: AgentState):
    """Main Python Dev agent node."""
    task = state.get("task", "")

    # -- Memory: search before responding --
    _mem_ctx = get_memory_context(task, "python_dev")
    from core.user_profile import get_profile_context
    _effective_prompt = PYTHON_SYSTEM_PROMPT.format(user_profile=get_profile_context(task))
    if _mem_ctx:
        _effective_prompt += "\n\n" + _mem_ctx
    # ----------------------------------------

    tool_context = ""

    if any(word in task.lower() for word in ["environment", "packages", "installed", "version"]):
        tool_context += f"\n[PYTHON ENVIRONMENT]\n{check_python_env()}"

    # Build messages
    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"Tool results from this system:\n{tool_context}\n\nUse these in your response."
        ))

    from tools.agent_runtime import respond_with_optional_tools
    response = respond_with_optional_tools(messages, _effective_prompt, task)

    # -- Memory: save after responding --
    save_to_memory("python_dev", "code", response.content,
                   {"task": task[:120] if task else ""})
    # ------------------------------------


    return {
        "messages":     [response],
        "active_agent": "python_dev",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_python_agent():
    graph = StateGraph(AgentState)
    graph.add_node("python_agent", python_agent_node)
    graph.add_edge(START, "python_agent")
    graph.add_edge("python_agent", END)
    return graph.compile()

python_agent = build_python_agent()

# ── Standalone Test ───────────────────────────────────────────
if __name__ == "__main__":
    print("🐍 Testing Python Dev Agent...\n")
    result = python_agent.invoke({
        "messages":     [{"role": "user", "content": "Write me a Python function that reads all .py files in a folder and counts total lines of code. Include type hints and error handling."}],
        "active_agent": "",
        "task":         "Write a Python function to count lines of code in a folder",
        "result":       "",
        "next_agent":   "",
        "memory":       {},
    })
    print("── PYTHON AGENT RESPONSE ──")
    print(result["messages"][-1].content)
