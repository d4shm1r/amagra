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
DATA_ANALYST_SYSTEM_PROMPT = """
{user_profile}
You are an expert Data Analyst agent.
Your expertise covers:
- pandas: dataframe operations, groupby, merge, pivot, apply
- SQL: SELECT, JOIN, window functions, CTEs, query optimization
- NumPy: array operations, broadcasting, linear algebra
- Data visualization: matplotlib, seaborn, plotly
- Statistics: descriptive stats, distributions, hypothesis testing
- Data cleaning: missing values, outliers, type coercion, normalization
- Feature engineering for ML pipelines
- Database systems: PostgreSQL, SQLite, MySQL, basic MongoDB
- Excel/CSV/JSON/Parquet data formats
- Jupyter notebooks best practices
- Exploratory data analysis (EDA) workflows

When writing data analysis code always include:
- Shape/dtypes inspection before operations (df.info(), df.describe())
- Null checks and handling strategy
- Comments explaining the "why" of transformations
- A sample output showing what the result looks like

When writing SQL always include:
- Readable formatting with aligned keywords
- Index hints or optimization notes for large tables
- A brief explanation of what the query returns"""

# ── Tools ─────────────────────────────────────────────────────
def check_data_packages() -> str:
    """Check which data analysis packages are installed."""
    packages = ["pandas", "numpy", "matplotlib", "seaborn",
                "plotly", "scipy", "sklearn", "sqlalchemy", "pyarrow"]
    results = []
    for pkg in packages:
        try:
            r = subprocess.run(
                [sys.executable, "-c", f"import {pkg}; print({pkg}.__version__)"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                results.append(f"  ✅ {pkg:<18} {r.stdout.strip()}")
            else:
                results.append(f"  ❌ {pkg:<18} not installed")
        except Exception:
            results.append(f"  ❌ {pkg:<18} not installed")
    return "Data packages:\n" + "\n".join(results)

# ── Agent Node ────────────────────────────────────────────────
def data_analyst_agent_node(state: AgentState):
    task = state.get("task", "")

    _mem_ctx = get_memory_context(task, "data_analyst")
    from core.user_profile import get_profile_context
    _effective_prompt = DATA_ANALYST_SYSTEM_PROMPT.format(user_profile=get_profile_context())
    if _mem_ctx:
        _effective_prompt += f"\n\n{_mem_ctx}"

    tool_context = ""

    if any(w in task.lower() for w in ["installed", "packages", "pandas", "numpy", "matplotlib"]):
        tool_context += f"\n[DATA PACKAGES]\n{check_data_packages()}"

    messages = [
        SystemMessage(content=_effective_prompt),
        *trim_messages(state["messages"], max_messages=10),
    ]

    if tool_context:
        messages.append(HumanMessage(
            content=f"System tool results:\n{tool_context}\n\nUse these in your response."
        ))

    response = llm.invoke(messages)

    save_to_memory("data_analyst", "chat", response.content,
                   {"task": task[:120] if task else ""})

    return {
        "messages":     [response],
        "active_agent": "data_analyst",
        "result":       response.content,
    }

# ── Build Subgraph ────────────────────────────────────────────
def build_data_analyst_agent():
    graph = StateGraph(AgentState)
    graph.add_node("data_analyst_agent", data_analyst_agent_node)
    graph.add_edge(START, "data_analyst_agent")
    graph.add_edge("data_analyst_agent", END)
    return graph.compile()

data_analyst_agent = build_data_analyst_agent()

if __name__ == "__main__":
    result = data_analyst_agent.invoke({
        "messages": [{"role": "user", "content": "Write a pandas snippet to find the top 5 customers by total spend from a CSV with columns: customer_id, order_date, amount."}],
        "active_agent": "", "task": "pandas top 5 customers by spend", "result": "", "next_agent": "", "memory": {},
    })
    print(result["messages"][-1].content)
