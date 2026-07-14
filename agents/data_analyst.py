import subprocess
import sys

from agents.runner import Agent
from agents.spec import AgentSpec, Probe

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

# ── Spec ──────────────────────────────────────────────────────
SPEC = AgentSpec(
    name="data_analyst",
    prompt=DATA_ANALYST_SYSTEM_PROMPT,
    probe_intro="System tool results:",
    probes=(
        Probe(
            triggers=("installed", "packages", "pandas", "numpy", "matplotlib"),
            label="DATA PACKAGES",
            run=lambda _task: check_data_packages(),
        ),
    ),
)

data_analyst_agent = Agent(SPEC)
