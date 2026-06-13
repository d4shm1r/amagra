"""
planner.py — Task Planning Layer (Phase 33)

Converts complex queries into structured, ordered execution plans.
Replaces the placeholder decompose() in deep_pipeline.py with a
dependency-aware, uncertainty-tracked planning layer.

Two modes:
  rule_based — <1ms, no LLM, pattern templates per action type
  llm        — phi4-mini generates the plan, ~5-10s, richer decomposition

The LLM mode fires when:
  - complexity == "compound"
  - action == "build" or "research"
  - AND the query has >= 3 distinct domain signals

Otherwise rule_based runs. The LLM result is validated and falls back
to rule_based on any parse failure.

Integration:
  from orchestration.planner import plan_query, Plan, PlanStep
  plan = plan_query(query, brain_decision)
  for step in plan.ordered_steps():
      run(step.agent, step.description)

Output schema:
  Plan.steps            — PlanStep list (in dependency order)
  Plan.parallel_groups  — sets of step_ids safe to run concurrently
  Plan.uncertainty      — mean uncertainty across steps [0, 1]
  Plan.mode             — "rule_based" | "llm"
"""

import re
import json
import time
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import os  # path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestration.query_normalizer import normalize

# ── Agent metadata ────────────────────────────────────────────

AGENT_DESCRIPTIONS = {
    "python_dev":        "Python, FastAPI, async, algorithms, testing",
    "dotnet_dev":        "C#, .NET, Blazor, WebAssembly, SignalR",
    "it_networking":     "DNS, SSH, firewalls, nginx, VPN, networking",
    "ai_ml":             "ML models, PyTorch, LangChain, embeddings, RAG",
    "knowledge_learning":"Concepts, explanations, general CS knowledge",
    "terse":             "Quick lookups, commands, short factual answers",
}

VALID_AGENTS = set(AGENT_DESCRIPTIONS.keys())

# ── Step templates per action type ───────────────────────────
# (description_template, agent, base_uncertainty, success_criteria)

_T_BUILD = [
    ("Design architecture and data model for: {q}",      "knowledge_learning", 0.25, "Architecture defined"),
    ("Implement core logic and primary structures",        "python_dev",         0.40, "Core implementation working"),
    ("Add cross-component integration and error handling", "python_dev",         0.50, "Components integrated"),
    ("Write tests and verify end-to-end correctness",     "python_dev",         0.30, "Test suite passes"),
]
_T_DEBUG = [
    ("Characterize and reproduce the failure: {q}",       "knowledge_learning", 0.20, "Failure reproduced"),
    ("Identify root cause",                                "python_dev",         0.60, "Root cause found"),
    ("Implement targeted fix",                             "python_dev",         0.40, "Fix applied"),
    ("Verify fix and test for regressions",               "python_dev",         0.20, "Verified clean"),
]
_T_EXPLAIN = [
    ("Survey foundational concepts: {q}",                 "knowledge_learning", 0.20, "Concepts mapped"),
    ("Provide detailed technical explanation",             "knowledge_learning", 0.30, "Explanation drafted"),
    ("Illustrate with practical code examples",            "python_dev",         0.35, "Examples complete"),
]
_T_COMPARE = [
    ("Characterise first option in: {q}",                 "knowledge_learning", 0.20, "Option A characterised"),
    ("Characterise second option",                         "knowledge_learning", 0.20, "Option B characterised"),
    ("Synthesise trade-off analysis",                     "knowledge_learning", 0.30, "Comparison synthesised"),
]
_T_RESEARCH = [
    ("Survey existing knowledge: {q}",                    "knowledge_learning", 0.40, "Survey complete"),
    ("Analyse key patterns and findings",                  "knowledge_learning", 0.50, "Analysis done"),
    ("Synthesise conclusions and recommendations",         "knowledge_learning", 0.40, "Synthesis complete"),
]

_ACTION_TEMPLATES = {
    "build":    _T_BUILD,
    "debug":    _T_DEBUG,
    "explain":  _T_EXPLAIN,
    "compare":  _T_COMPARE,
    "research": _T_RESEARCH,
    "plan":     _T_BUILD,
    "unknown":  _T_EXPLAIN,
}


# ── Data model ────────────────────────────────────────────────

@dataclass
class PlanStep:
    step_id:          str
    description:      str
    agent:            str
    depends_on:       List[str] = field(default_factory=list)
    uncertainty:      float     = 0.4
    success_criteria: str       = ""
    action_type:      str       = "unknown"
    # Set by executor after the step runs
    status:           str       = "pending"  # pending|running|completed|failed
    result_snippet:   str       = ""
    elapsed_ms:       float     = 0.0

    def is_ready(self, completed: set) -> bool:
        """True when all dependencies have completed."""
        return all(dep in completed for dep in self.depends_on)


@dataclass
class Plan:
    query:           str
    steps:           List[PlanStep]
    parallel_groups: List[List[str]]   # each group = step_ids that can run together
    uncertainty:     float             # mean across steps
    mode:            str               # "rule_based" | "llm"
    elapsed_ms:      float = 0.0

    def ordered_steps(self) -> List[PlanStep]:
        """Steps in dependency-respecting execution order."""
        index = {s.step_id: s for s in self.steps}
        ordered, completed, remaining = [], set(), list(self.steps)
        while remaining:
            ready = [s for s in remaining if s.is_ready(completed)]
            if not ready:
                # Cycle or unresolvable — append remaining as-is
                ordered.extend(remaining)
                break
            for s in ready:
                ordered.append(s)
                completed.add(s.step_id)
                remaining.remove(s)
        return ordered

    def summary(self) -> str:
        lines = [f"Plan ({self.mode}, {len(self.steps)} steps, "
                 f"uncertainty={self.uncertainty:.2f}):"]
        for s in self.ordered_steps():
            deps = f"  [after {', '.join(s.depends_on)}]" if s.depends_on else ""
            lines.append(f"  {s.step_id}: [{s.agent}] {s.description}{deps}")
        return "\n".join(lines)


# ── Topology: parallel group computation ─────────────────────

def _compute_parallel_groups(steps: List[PlanStep]) -> List[List[str]]:
    """
    Topological level assignment.
    Steps with the same level can run concurrently.
    Returns list of levels, each level is a list of step_ids.
    """
    index   = {s.step_id: s for s in steps}
    level   = {}
    changed = True
    for s in steps:
        level[s.step_id] = 0

    while changed:
        changed = False
        for s in steps:
            max_dep_level = max(
                (level.get(dep, 0) for dep in s.depends_on), default=-1
            )
            new_level = max_dep_level + 1
            if new_level != level[s.step_id]:
                level[s.step_id] = new_level
                changed = True

    max_level = max(level.values(), default=0)
    groups = []
    for lv in range(max_level + 1):
        group = [sid for sid, l in level.items() if l == lv]
        if group:
            groups.append(group)
    return groups


# ── Domain-to-agent re-mapping for plan steps ─────────────────

_DOMAIN_AGENT = {
    "networking": "it_networking",
    "python":     "python_dev",
    "blazor":     "dotnet_dev",
    "ai_ml":      "ai_ml",
    "general":    "knowledge_learning",
}


def _best_agent(description: str, hint_agents: List[str]) -> str:
    """Pick the most relevant agent for a step description."""
    desc = description.lower()
    # Quick keyword match
    if any(k in desc for k in ("test", "pytest", "unit test")):
        return "python_dev"
    if any(k in desc for k in ("architecture", "design", "concept", "explain", "overview")):
        return "knowledge_learning"
    if any(k in desc for k in ("python", "fastapi", "flask", "async", "class", "function")):
        return "python_dev"
    if any(k in desc for k in ("blazor", "c#", ".net", "razor", "wasm")):
        return "dotnet_dev"
    if any(k in desc for k in ("network", "dns", "ssh", "nginx", "firewall")):
        return "it_networking"
    if any(k in desc for k in ("ml", "model", "embedding", "pytorch", "llm")):
        return "ai_ml"
    # Fall back to first hint agent
    return hint_agents[0] if hint_agents else "knowledge_learning"


# ── Uncertainty model ─────────────────────────────────────────

def _step_uncertainty(base: float, step_idx: int, n_steps: int,
                      n_domains: int, action: str) -> float:
    """
    Adjust base uncertainty for:
    - position in plan (middle steps more uncertain than first/last)
    - number of domains (cross-domain = harder)
    - action type modifier
    """
    position_factor = 1.0 + 0.1 * (step_idx - (n_steps - 1) / 2) / max(n_steps, 1)
    domain_factor   = 1.0 + 0.08 * max(0, n_domains - 1)
    action_mods     = {"debug": 1.2, "research": 1.1, "build": 1.0,
                       "explain": 0.9, "compare": 0.85, "lookup": 0.5}
    action_factor   = action_mods.get(action, 1.0)
    u = base * position_factor * domain_factor * action_factor
    return round(min(max(u, 0.05), 0.95), 3)


# ── Rule-based planner ────────────────────────────────────────

def _rule_based_plan(query: str, action: str, agents: List[str],
                     n_domains: int, world_context: str = "") -> List[PlanStep]:
    templates = _ACTION_TEMPLATES.get(action, _T_EXPLAIN)
    q_short   = query[:60] + ("…" if len(query) > 60 else "")
    # Append a brief stack tag to the first step so it's project-specific.
    ctx_tag   = f" [{world_context}]" if world_context else ""
    steps     = []

    for i, (desc_tmpl, default_agent, base_u, criteria) in enumerate(templates):
        desc  = desc_tmpl.format(q=q_short)
        if i == 0 and ctx_tag:
            desc = desc + ctx_tag
        agent   = _best_agent(desc, agents) if agents else default_agent
        if agent not in VALID_AGENTS:
            agent = default_agent

        sid = f"step_{i+1}"
        deps = [f"step_{i}"] if i > 0 else []

        u = _step_uncertainty(base_u, i, len(templates), n_domains, action)

        steps.append(PlanStep(
            step_id          = sid,
            description      = desc,
            agent            = agent,
            depends_on       = deps,
            uncertainty      = u,
            success_criteria = criteria,
            action_type      = action,
        ))

    return steps


# ── LLM-based planner ─────────────────────────────────────────

_PLAN_SYSTEM = """You are a task decomposition assistant for a multi-agent system.
Break the user query into 3-5 ordered steps. Each step must have exactly one agent.
Available agents: python_dev, dotnet_dev, it_networking, ai_ml, knowledge_learning, terse.
Return ONLY valid JSON. No explanation. No markdown. Example format:
{"steps":[{"id":"step_1","description":"Design the API schema","agent":"knowledge_learning","depends_on":[],"uncertainty":0.2,"success_criteria":"Schema defined"},{"id":"step_2","description":"Implement FastAPI endpoints","agent":"python_dev","depends_on":["step_1"],"uncertainty":0.4,"success_criteria":"Endpoints working"}]}"""


def _llm_plan(query: str, agents: List[str], action: str,
              world_context: str = "") -> Optional[List[PlanStep]]:
    """
    Ask phi4-mini to decompose the query.
    Returns None on any failure so the caller can fall back to rule-based.
    Uses a dedicated llm instance with higher token budget.
    """
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage, SystemMessage

        planner_llm = ChatOllama(
            model       = "phi4-mini:latest",
            temperature = 0.3,   # low temp for structured output
            num_ctx     = 2048,
            num_predict = 512,   # larger budget for JSON plan
            num_thread  = 6,
        )

        ctx_line = f"Project context: {world_context}\n\n" if world_context else ""
        prompt = (
            f"Query: {query}\n\n"
            f"{ctx_line}"
            f"Preferred agents (use if appropriate): {', '.join(agents)}\n"
            f"Action type: {action}\n\n"
            "Output JSON plan:"
        )
        response = planner_llm.invoke([
            SystemMessage(content=_PLAN_SYSTEM),
            HumanMessage(content=prompt),
        ])
        raw = response.content.strip()

        # Extract JSON even if the model wraps it in markdown
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            return None
        data = json.loads(json_match.group())

        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list) or not raw_steps:
            return None

        steps = []
        for raw in raw_steps:
            agent = raw.get("agent", "knowledge_learning")
            if agent not in VALID_AGENTS:
                agent = "knowledge_learning"
            steps.append(PlanStep(
                step_id          = raw.get("id", f"step_{len(steps)+1}"),
                description      = raw.get("description", ""),
                agent            = agent,
                depends_on       = [d for d in raw.get("depends_on", []) if isinstance(d, str)],
                uncertainty      = float(raw.get("uncertainty", 0.4)),
                success_criteria = raw.get("success_criteria", ""),
                action_type      = action,
            ))

        return steps if steps else None

    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────

def plan_query(
    query:       str,
    action:      str       = "unknown",
    agents:      List[str] = None,
    complexity:  str       = "simple",
    force_llm:   bool      = False,
) -> Plan:
    """
    Produce an execution plan for the given query.

    Parameters
    ----------
    query       : raw user query
    action      : detected action type from core_brain (build|debug|explain|...)
    agents      : suggested agents from core_brain.agent_strategy
    complexity  : "simple" | "compound" | "ambiguous"
    force_llm   : bypass mode heuristic and always call the LLM

    Returns
    -------
    Plan with ordered, dependency-annotated PlanStep list.
    """
    t0     = time.monotonic()
    agents = agents or ["knowledge_learning"]
    sig    = normalize(query)

    # Refine agent list via skill graph when no domain agents were provided
    try:
        from infrastructure.skill_graph import select_skills, skill_summary
        skills = select_skills(query, n=3)
        if skills:
            skill_agents = list(dict.fromkeys(s.agent for s in skills))
            if agents == ["knowledge_learning"] and skill_agents:
                agents = skill_agents
            print(f"[planner] skills={skill_summary(skills)}")
    except Exception:
        pass

    # Count distinct domains as a complexity proxy
    n_domains = max(1, len([a for a in agents if a != "knowledge_learning"]))

    # Pull world model context for project-aware step descriptions
    world_context = ""
    try:
        from models.world_model import load_world
        wm = load_world("cos-session-main")
        world_context = wm.context_summary()
    except Exception:
        pass

    # Mode selection: LLM fires for compound build/research with 2+ domains
    use_llm = (
        force_llm
        or (
            complexity == "compound"
            and action in ("build", "research", "plan")
            and n_domains >= 2
        )
    )

    mode  = "rule_based"
    steps = None

    if use_llm:
        steps = _llm_plan(query, agents, action, world_context=world_context)
        if steps:
            mode = "llm"

    if steps is None:
        steps = _rule_based_plan(query, action, agents, n_domains,
                                  world_context=world_context)

    groups = _compute_parallel_groups(steps)
    mean_u = sum(s.uncertainty for s in steps) / len(steps) if steps else 0.5

    elapsed = (time.monotonic() - t0) * 1000

    return Plan(
        query           = query,
        steps           = steps,
        parallel_groups = groups,
        uncertainty     = round(mean_u, 3),
        mode            = mode,
        elapsed_ms      = round(elapsed, 1),
    )


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    TESTS = [
        # (query, action, agents, complexity)
        (
            "Build a FastAPI app with JWT authentication and PostgreSQL database",
            "build", ["python_dev", "it_networking"], "compound",
        ),
        (
            "My nginx is returning 502 when proxying to my FastAPI backend. Debug and fix.",
            "debug", ["it_networking", "python_dev"], "compound",
        ),
        (
            "Explain the difference between supervised and unsupervised learning",
            "explain", ["ai_ml", "knowledge_learning"], "simple",
        ),
        (
            "Compare Blazor Server vs Blazor WebAssembly for a dashboard app",
            "compare", ["dotnet_dev", "knowledge_learning"], "simple",
        ),
        (
            "Research and design a multi-agent system with memory, planning, and reflection",
            "research", ["ai_ml", "python_dev", "knowledge_learning"], "compound",
        ),
    ]

    print("=" * 65)
    print("  planner.py — rule-based plan tests")
    print("=" * 65)

    for query, action, agents, complexity in TESTS:
        plan = plan_query(query, action=action, agents=agents, complexity=complexity)
        print(f"\n{'─'*65}")
        print(f"  Query:  {query[:60]}…" if len(query) > 60 else f"  Query:  {query}")
        print(f"  Mode:   {plan.mode}  |  Steps: {len(plan.steps)}"
              f"  |  Uncertainty: {plan.uncertainty:.2f}  |  {plan.elapsed_ms:.1f}ms")
        print(f"  Parallel groups: {plan.parallel_groups}")
        print()
        for s in plan.ordered_steps():
            dep_str = f"  [after {', '.join(s.depends_on)}]" if s.depends_on else ""
            print(f"    {s.step_id}  [{s.agent:20s}]  u={s.uncertainty:.2f}  {s.description}{dep_str}")

    print(f"\n{'=' * 65}")
    llm_flag = "--llm" in sys.argv
    if llm_flag:
        print("\n  LLM plan test (--llm flag):")
        q = "Build a FastAPI app with JWT authentication and PostgreSQL database"
        plan = plan_query(q, action="build", agents=["python_dev"], complexity="compound", force_llm=True)
        print(plan.summary())
