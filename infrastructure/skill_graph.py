"""
skill_graph.py — Skill Graph Architecture (Phase 36)

Replaces the coarse agent-identity model with composable skill nodes.

Current model:        ai_ml handles all of: "explain backprop" + "implement PyTorch trainer"
Skill model:          MachineLearningTheory vs MachineLearningEngineering — different nodes.

Each skill has:
  - A canonical name + domain category
  - A trigger vocabulary (keywords that activate it)
  - A target agent that executes it
  - A complexity profile (theory / engineering / ops)

The planner calls select_skills(query, n=3) to get the ranked list
instead of calling _detect_domains(). The coordinator still routes to
an agent, but the skill selection makes the intent far more specific.

Usage:
    from infrastructure.skill_graph import select_skills, skill_to_agent, SkillNode

    skills = select_skills("Explain gradient descent with backpropagation")
    # → [SkillNode("MachineLearningTheory", agent="ai_ml", ...)]

    skills = select_skills("Implement a PyTorch LSTM trainer")
    # → [SkillNode("MachineLearningEngineering", agent="ai_ml", ...)]

    # Get the execution agent for the top skill
    agent = skill_to_agent(skills[0]) if skills else "knowledge_learning"
"""

from dataclasses import dataclass, field
from typing import List, Optional
import re

# ── Skill node ────────────────────────────────────────────────

@dataclass
class SkillNode:
    name:         str              # e.g. "MachineLearningTheory"
    category:     str              # e.g. "ai_ml", "python", "infrastructure"
    agent:        str              # target agent for execution
    description:  str             # human-readable capability summary
    keywords:     List[str]       # trigger patterns (lowercased)
    complexity:   str   = "mixed" # "theory" | "engineering" | "ops" | "mixed"
    score:        float = 0.0     # filled in by select_skills()

    def matches(self, text: str) -> float:
        """
        Score keyword hits. Multi-word phrases count proportionally to their
        word count so "gradient descent" (weight 2) beats "backpropagation"
        (weight 1) — longer phrases are stronger, more specific signals.
        """
        t = text.lower()
        score = 0.0
        for kw in self.keywords:
            if kw in t:
                score += max(1, kw.count(" ") + 1)
        return score

    def max_score(self) -> float:
        """Maximum achievable score (all keywords matched)."""
        return sum(max(1, kw.count(" ") + 1) for kw in self.keywords)


# ── Skill registry ────────────────────────────────────────────
# Ordered roughly from most specific → least specific.

_SKILLS: List[SkillNode] = [

    # ── AI / ML ──────────────────────────────────────────────
    SkillNode(
        name="MachineLearningTheory",
        category="ai_ml", agent="ai_ml",
        description="Conceptual ML: loss functions, optimisers, theory, math",
        keywords=["gradient descent", "backpropagation", "loss function",
                  "overfitting", "regularisation", "regularization",
                  "bayesian", "hyperscaling", "convergence",
                  "attention mechanism", "transformer theory",
                  "markov", "probability", "entropy", "kl divergence",
                  "embedding space", "latent space", "explain ml",
                  "how does", "what is neural", "how neural"],
        complexity="theory",
    ),
    SkillNode(
        name="MachineLearningEngineering",
        category="ai_ml", agent="ai_ml",
        description="ML implementation: PyTorch, training loops, data pipelines",
        keywords=["pytorch", "tensorflow", "keras", "train model",
                  "training loop", "dataset", "dataloader",
                  "fine-tune", "finetune", "llm inference", "onnx",
                  "huggingface", "transformers", "implement ml",
                  "build model", "neural network code", "lstm", "rnn",
                  "cnn", "model.fit", "model.train"],
        complexity="engineering",
    ),

    # ── Python ────────────────────────────────────────────────
    SkillNode(
        name="FastAPI",
        category="python", agent="python_dev",
        description="FastAPI: routing, middleware, Pydantic, async endpoints",
        keywords=["fastapi", "endpoint", "route", "pydantic", "uvicorn",
                  "starlette", "dependency injection", "fastapi middleware",
                  "openapi", "swagger", "rest api python"],
        complexity="engineering",
    ),
    SkillNode(
        name="PythonBackend",
        category="python", agent="python_dev",
        description="Python server-side: Flask, Django, scripts, data processing",
        keywords=["python", "flask", "django", "script", "class", "function",
                  "module", "package", "pip", "venv", "pytest", "unittest",
                  "asyncio", "celery", "redis queue", "sqlalchemy"],
        complexity="engineering",
    ),
    SkillNode(
        name="Authentication",
        category="python", agent="python_dev",
        description="Auth systems: JWT, OAuth2, session management, API keys",
        keywords=["jwt", "json web token", "oauth", "oauth2",
                  "authentication", "authorisation", "authorization",
                  "api key", "session", "login", "logout",
                  "password hash", "bcrypt", "refresh token",
                  "bearer token", "cors"],
        complexity="engineering",
    ),

    # ── Database ──────────────────────────────────────────────
    SkillNode(
        name="DatabaseDesign",
        category="python", agent="python_dev",
        description="Schema design, migrations, ORM, query optimisation",
        keywords=["database schema", "migration", "orm",
                  "sqlalchemy", "alembic", "foreign key", "index",
                  "normalisation", "normalization", "query optimis",
                  "query optimiz", "postgres schema", "mysql schema",
                  "table design", "erd", "entity relationship"],
        complexity="engineering",
    ),
    SkillNode(
        name="CacheLayer",
        category="python", agent="python_dev",
        description="Redis, Memcached, in-process caching, cache invalidation",
        keywords=["redis", "cache", "memcached", "caching", "ttl",
                  "cache invalidation", "in-memory store",
                  "session store", "rate limiting"],
        complexity="engineering",
    ),

    # ── Blazor / .NET ─────────────────────────────────────────
    SkillNode(
        name="BlazorFrontend",
        category="blazor", agent="dotnet_dev",
        description="Blazor WASM/Server: components, data binding, HttpClient",
        keywords=["blazor", "razor", "wasm", "webassembly", "component",
                  "@code", "eventhander", "oninitialized", "httpclient blazor",
                  "blazor routing", "cascading", "parameter"],
        complexity="engineering",
    ),
    SkillNode(
        name="DotNetBackend",
        category="blazor", agent="dotnet_dev",
        description="ASP.NET Core: controllers, minimal API, EF Core",
        keywords=["asp.net", "aspnet", "csharp", "c#", ".net",
                  "ef core", "entity framework", "dotnet",
                  "controller", "ioc container", "dependency injection c#",
                  "xunit", "nunit"],
        complexity="engineering",
    ),

    # ── Infrastructure & Networking ───────────────────────────
    SkillNode(
        name="ContainerOrchestration",
        category="infrastructure", agent="it_networking",
        description="Docker, Kubernetes, container networking, Helm charts",
        keywords=["docker", "kubernetes", "k8s", "helm", "pod",
                  "deployment yaml", "service mesh", "ingress",
                  "dockerfile", "compose", "container", "registry",
                  "ci cd", "github actions", "gitlab ci"],
        complexity="ops",
    ),
    SkillNode(
        name="WebServerConfig",
        category="infrastructure", agent="it_networking",
        description="nginx, Apache, reverse proxy, TLS, load balancing",
        keywords=["nginx", "apache", "reverse proxy", "load balancer",
                  "upstream", "ssl", "tls", "https", "certificate",
                  "let's encrypt", "certbot", "vhost", "virtual host",
                  "proxy_pass", "server block"],
        complexity="ops",
    ),
    SkillNode(
        name="NetworkDebugging",
        category="infrastructure", agent="it_networking",
        description="TCP/IP, DNS, routing, firewalls, packet analysis",
        keywords=["502", "504", "network error", "timeout", "dns",
                  "firewall", "iptables", "port", "socket", "ping",
                  "traceroute", "curl", "http error", "connection refused",
                  "latency", "bandwidth", "packet loss"],
        complexity="ops",
    ),

    # ── Testing & Quality ─────────────────────────────────────
    SkillNode(
        name="TestingQA",
        category="python", agent="python_dev",
        description="Testing: pytest, unit tests, mocking, coverage, TDD, integration tests",
        keywords=["pytest", "unittest", "test", "mock", "patch", "fixture",
                  "coverage", "tdd", "test driven", "integration test",
                  "end to end", "e2e", "assertion", "test case",
                  "parameterize", "conftest", "monkeypatch",
                  "factory boy", "hypothesis", "property based"],
        complexity="engineering",
    ),

    # ── Cloud & Infrastructure ────────────────────────────────
    SkillNode(
        name="CloudInfrastructure",
        category="infrastructure", agent="it_networking",
        description="Cloud: AWS, GCP, Azure, Terraform, IaC, serverless, managed services",
        keywords=["aws", "gcp", "azure", "terraform", "infrastructure as code",
                  "iac", "s3", "ec2", "lambda", "cloud function",
                  "serverless", "rds", "cloudfront", "iam",
                  "pulumi", "ansible", "cloud run", "app engine",
                  "blob storage", "managed service", "vpc", "subnet"],
        complexity="ops",
    ),

    # ── Web Development ───────────────────────────────────────
    SkillNode(
        name="ReactFrontend",
        category="web", agent="web_dev",
        description="React, hooks, state management, TypeScript UI",
        keywords=["react", "usestate", "useeffect", "component", "jsx",
                  "typescript", "nextjs", "next.js", "tailwind",
                  "redux", "zustand", "vite", "webpack"],
        complexity="engineering",
    ),

    # ── DevOps ────────────────────────────────────────────────
    SkillNode(
        name="DeploymentPipeline",
        category="devops", agent="devops",
        description="CI/CD, GitHub Actions, deployment automation",
        keywords=["deploy", "pipeline", "github actions", "gitlab",
                  "jenkins", "argocd", "gitops", "release",
                  "rollout", "blue green", "canary"],
        complexity="ops",
    ),

    # ── Data Analysis ─────────────────────────────────────────
    SkillNode(
        name="DataAnalysis",
        category="data", agent="data_analyst",
        description="Data analysis: pandas, NumPy, visualization, EDA, statistics",
        keywords=["pandas", "dataframe", "data analysis", "data visualization",
                  "matplotlib", "seaborn", "plotly", "numpy array",
                  "data cleaning", "pivot table", "correlation matrix",
                  "exploratory data analysis", "eda", "statistical analysis",
                  "groupby", "jupyter notebook", "time series"],
        complexity="engineering",
    ),

    # ── Technical Writing ─────────────────────────────────────
    SkillNode(
        name="TechnicalWriting",
        category="writing", agent="writer",
        description="Documentation, README, changelogs, technical reports",
        keywords=["write documentation", "write readme", "api documentation",
                  "technical documentation", "release notes", "changelog",
                  "user guide", "technical writing", "docstring",
                  "markdown doc", "write a report", "architecture document"],
        complexity="theory",
    ),

    # ── Quick Lookup ──────────────────────────────────────────
    SkillNode(
        name="QuickLookup",
        category="general", agent="terse",
        description="Short factual lookups: command syntax, flags, one-liners",
        keywords=["what command", "quick command", "one liner",
                  "syntax for", "command to", "flag for",
                  "option for", "how do i run", "shortcut for"],
        complexity="theory",
    ),

    # ── General knowledge ─────────────────────────────────────
    SkillNode(
        name="ConceptualExplanation",
        category="general", agent="knowledge_learning",
        description="Explain concepts, compare approaches, high-level design",
        keywords=["explain", "what is", "how does", "compare",
                  "difference between", "when to use", "pros and cons",
                  "best practice", "overview", "introduction"],
        complexity="theory",
    ),
    SkillNode(
        name="Debugging",
        category="general", agent="knowledge_learning",
        description="General debugging: reading errors, root cause analysis",
        keywords=["debug", "error", "exception", "traceback", "bug",
                  "fix", "issue", "problem", "not working",
                  "crash", "fail", "why is"],
        complexity="mixed",
    ),
]

# ── Public API ────────────────────────────────────────────────

def select_skills(query: str, n: int = 3) -> List[SkillNode]:
    """
    Score all skills against the query and return the top-n matches.

    Scoring: keyword hit count normalised by skill keyword count,
    so skills with fewer but more specific keywords can still win.
    """
    q = query.lower()
    scored = []
    for skill in _SKILLS:
        hits = skill.matches(q)
        if hits > 0:
            normalised = hits / skill.max_score()
            node = SkillNode(**{
                **skill.__dict__,
                "score": round(normalised, 4),
            })
            scored.append(node)

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:n]


def skill_to_agent(skill: SkillNode) -> str:
    """Return the execution agent for a skill node."""
    return skill.agent


def top_agent(query: str, fallback: str = "knowledge_learning") -> str:
    """
    Quick helper: return the agent for the highest-scoring skill.
    """
    skills = select_skills(query, n=1)
    return skills[0].agent if skills else fallback


def skill_summary(skills: List[SkillNode]) -> str:
    """One-line summary of selected skills for logging."""
    if not skills:
        return "(no skills matched)"
    return " + ".join(f"{s.name}({s.score:.2f})" for s in skills)


# ── Agent → skill index ───────────────────────────────────────

def skills_for_agent(agent: str) -> List[SkillNode]:
    """All skills that map to a given agent."""
    return [s for s in _SKILLS if s.agent == agent]


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  skill_graph — skill disambiguation test")
    print("=" * 65)

    queries = [
        ("Explain gradient descent and why it converges", "should → MachineLearningTheory"),
        ("Implement a PyTorch LSTM trainer with dropout", "should → MachineLearningEngineering"),
        ("Build FastAPI endpoint with JWT auth",          "should → FastAPI + Authentication"),
        ("Set up nginx reverse proxy for port 8000",     "should → WebServerConfig"),
        ("Why is my nginx returning 502 bad gateway",    "should → NetworkDebugging"),
        ("Set up Docker with Kubernetes deployment",     "should → ContainerOrchestration"),
        ("Build a Blazor WASM component with HttpClient","should → BlazorFrontend"),
        ("What is the difference between JWT and OAuth", "should → Authentication or ConceptualExplanation"),
    ]

    all_pass = True
    for query, note in queries:
        skills = select_skills(query, n=3)
        top    = skills[0] if skills else None
        agent  = top.agent if top else "knowledge_learning"
        match  = "✅" if skills else "⚠"
        print(f"\n  {match} [{agent}]  \"{query[:52]}\"")
        print(f"      Skills:  {skill_summary(skills)}")
        print(f"      Note:    {note}")
        if not skills:
            all_pass = False

    print(f"\n  {'All skill matches found' if all_pass else 'Some queries had no skill match'}")
