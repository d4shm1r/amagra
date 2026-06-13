"""
Canonical agent registry.  Import AGENT_IDS or AGENT_MAP from here —
never hardcode agent name strings in routing or inference code.

Adding a new agent: add it here first.  The boot assertion in coordinator.py
will catch any divergence at startup before any request is served.
"""

AGENT_MAP = {
    "python_dev":        {"label": "Python Dev",       "icon": "🐍", "color": "#4EC9B0", "domain": "python"},
    "dotnet_dev":        {"label": ".NET / Blazor Dev", "icon": "⚡", "color": "#7C3AED", "domain": "dotnet"},
    "it_networking":     {"label": "IT Networking",     "icon": "🌐", "color": "#007ACC", "domain": "networking"},
    "ai_ml":             {"label": "AI / ML",           "icon": "🧠", "color": "#C586C0", "domain": "ai_ml"},
    "web_dev":           {"label": "Web Dev",           "icon": "🕸",  "color": "#F97316", "domain": "web"},
    "devops":            {"label": "DevOps",            "icon": "🔧", "color": "#CCA700", "domain": "devops"},
    "data_analyst":      {"label": "Data Analyst",      "icon": "📊", "color": "#34D399", "domain": "data"},
    "writer":            {"label": "Writer",            "icon": "✍",  "color": "#F472B6", "domain": "writing"},
    "knowledge_learning":{"label": "Knowledge",         "icon": "📚", "color": "#9CDCFE", "domain": "knowledge"},
    "terse":             {"label": "Terse",             "icon": "⚡", "color": "#89D185", "domain": "terse"},
}

AGENT_IDS    = set(AGENT_MAP.keys())
CODE_AGENTS  = frozenset({"python_dev", "dotnet_dev"})
