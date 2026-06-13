"""
world_model.py — Session-Scoped World Model (Phase 35)

Tracks what the system knows about the current project across
multiple requests within a session. This is what separates an
assistant from an operating system: continuity.

The WorldModel is a JSON document that accumulates facts about:
  - Project: language, framework, database, deployment, auth, frontend
  - Session: current goal, active agents, interaction history
  - Issues:  known bugs, failed steps, open questions
  - Progress: completed tasks, milestones

Entity extraction is rule-based (no LLM call) using keyword
sets matched against the query and response text.

Persistence: logs/world_model.db, one row per session.
             Updated after every emit(WORLD_MODEL_UPDATED).

Usage:
    from models.world_model import WorldModel, load_world, update_from_query

    world = load_world(session_id)
    world = update_from_query(world, query="Build FastAPI with JWT and Postgres")
    world.save()
    print(world.project_context)
"""

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

_DB_PATH   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "logs", "world_model.db")
_DB_INITED = False

# ── Entity vocabulary ─────────────────────────────────────────
# Maps keywords to (category, value) pairs.
# First match per category wins — entries ordered by specificity.

_ENTITY_MAP: list[tuple[str, str, str]] = [
    # (pattern, category, value)
    # Language
    (r"\bpython\b",      "language",   "python"),
    (r"\bc#\b|csharp\b", "language",   "csharp"),
    (r"\bjava(?:script)?\b", "language", "javascript"),
    (r"\btypescript\b",  "language",   "typescript"),
    (r"\brust\b",        "language",   "rust"),
    (r"\bgo\b|golang\b", "language",   "go"),
    # Framework
    (r"\bfastapi\b",     "framework",  "fastapi"),
    (r"\bflask\b",       "framework",  "flask"),
    (r"\bdjango\b",      "framework",  "django"),
    (r"\bexpress\b",     "framework",  "express"),
    (r"\bnext\.?js\b",   "framework",  "nextjs"),
    (r"\breact\b",       "framework",  "react"),
    (r"\bvue\b",         "framework",  "vue"),
    (r"\bangular\b",     "framework",  "angular"),
    (r"\bblazor\b",      "framework",  "blazor"),
    (r"\basp\.net\b",    "framework",  "aspnet"),
    # Database
    (r"\bpostgres(?:ql)?\b", "database", "postgresql"),
    (r"\bmysql\b",       "database",  "mysql"),
    (r"\bsqlite\b",      "database",  "sqlite"),
    (r"\bmongo(?:db)?\b","database",  "mongodb"),
    (r"\bredis\b",       "database",  "redis"),
    (r"\bsupabase\b",    "database",  "supabase"),
    # Deployment
    (r"\bdocker\b",      "deployment","docker"),
    (r"\bkubernetes\b|k8s\b", "deployment", "kubernetes"),
    (r"\bnginx\b",       "deployment","nginx"),
    (r"\bgunicorn\b",    "deployment","gunicorn"),
    (r"\buvicorn\b",     "deployment","uvicorn"),
    # Auth
    (r"\bjwt\b",         "auth",      "jwt"),
    (r"\boauth\b",       "auth",      "oauth"),
    (r"\bapi.?key\b",    "auth",      "api_key"),
    (r"\bbasic.?auth\b", "auth",      "basic_auth"),
    # Testing
    (r"\bpytest\b",      "test_framework", "pytest"),
    (r"\bxunit\b",       "test_framework", "xunit"),
    (r"\bnunit\b",       "test_framework", "nunit"),
    (r"\bjest\b",        "test_framework", "jest"),
]


# ── Data model ────────────────────────────────────────────────

@dataclass
class WorldModel:
    session_id:      str
    created_at:      float = field(default_factory=time.time)
    updated_at:      float = field(default_factory=time.time)

    # Project context — auto-extracted from queries
    project_context: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"language": "python", "framework": "fastapi", "database": "postgresql"}

    # Current goal (most recent high-level intent)
    current_goal:    str  = ""

    # Completed tasks (summaries, not full responses)
    completed_tasks: List[str] = field(default_factory=list)

    # Known issues (failure patterns, open bugs)
    known_issues:    List[Dict[str, str]] = field(default_factory=list)
    # e.g. [{"description": "nginx 502", "step_id": "step_2", "ts": "..."}]

    # Interaction log — lightweight summary per request
    interaction_log: List[Dict[str, str]] = field(default_factory=list)
    # e.g. [{"query": "...", "agent": "...", "outcome": "...", "ts": "..."}]

    # Entity graph — technical entities and connections
    entities:        Dict[str, List[str]] = field(default_factory=dict)
    # e.g. {"fastapi": ["jwt", "postgresql"], "jwt": ["fastapi"]}

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self) -> None:
        self.updated_at = time.time()
        _save_world(self)

    def context_summary(self) -> str:
        """
        One-paragraph summary of the world model for injection into prompts.
        Keeps it brief — we add this to agent system prompts.
        """
        ctx = self.project_context
        parts = []
        if ctx.get("language"):
            parts.append(f"Language: {ctx['language']}")
        if ctx.get("framework"):
            parts.append(f"Framework: {ctx['framework']}")
        if ctx.get("database"):
            parts.append(f"Database: {ctx['database']}")
        if ctx.get("deployment"):
            parts.append(f"Deployment: {ctx['deployment']}")
        if ctx.get("auth"):
            parts.append(f"Auth: {ctx['auth']}")
        if self.current_goal:
            parts.append(f"Current goal: {self.current_goal}")
        if self.completed_tasks:
            parts.append(f"Completed: {'; '.join(self.completed_tasks[-3:])}")
        if self.known_issues:
            issues = "; ".join(i["description"] for i in self.known_issues[-2:])
            parts.append(f"Known issues: {issues}")
        return " | ".join(parts) if parts else ""

    def add_issue(self, description: str, step_id: str = "") -> None:
        self.known_issues.append({
            "description": description,
            "step_id":     step_id,
            "ts":          str(time.time()),
        })
        # Keep only last 20 issues
        self.known_issues = self.known_issues[-20:]

    def add_completed(self, task: str) -> None:
        self.completed_tasks.append(task[:200])
        self.completed_tasks = self.completed_tasks[-50:]

    def log_interaction(self, query: str, agent: str, outcome: str) -> None:
        self.interaction_log.append({
            "query":   query[:150],
            "agent":   agent,
            "outcome": outcome,
            "ts":      str(time.time()),
        })
        self.interaction_log = self.interaction_log[-100:]


# ── Entity extraction ─────────────────────────────────────────

def _extract_entities(text: str) -> Dict[str, str]:
    """
    Rule-based entity extraction from query/response text.
    Returns {category: value} dict.  First match per category wins.
    """
    q        = text.lower()
    found: Dict[str, str] = {}
    for pattern, category, value in _ENTITY_MAP:
        if category not in found and re.search(pattern, q):
            found[category] = value
    return found


def update_from_query(world: WorldModel, query: str,
                      agent: str = "", response: str = "",
                      outcome: str = "unknown") -> WorldModel:
    """
    Update the world model from a new query + optional response.

    Extracts entities from both query and response.
    Updates current_goal if the query has clear intent.
    Logs the interaction.
    """
    combined = query + " " + response
    entities = _extract_entities(combined)

    # Merge into project_context (don't overwrite existing values
    # unless the new one is from the response — more specific)
    for category, value in entities.items():
        if category not in world.project_context:
            world.project_context[category] = value

    # Update entity graph (co-occurrence)
    entity_values = list(entities.values())
    for v in entity_values:
        others = [x for x in entity_values if x != v]
        if others:
            existing = world.entities.get(v, [])
            for o in others:
                if o not in existing:
                    existing.append(o)
            world.entities[v] = existing[-10:]   # cap at 10 connections

    # Update current goal from longer, intent-bearing queries
    if len(query.split()) >= 5:
        world.current_goal = query[:200]

    world.log_interaction(query, agent, outcome)

    return world


# ── DB persistence ────────────────────────────────────────────

def _ensure_db() -> None:
    global _DB_INITED
    if _DB_INITED:
        return
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS world_models (
            session_id  TEXT    PRIMARY KEY,
            created_at  REAL,
            updated_at  REAL,
            data        TEXT    NOT NULL
        )
    """)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    con.close()
    _DB_INITED = True


def _save_world(world: WorldModel) -> None:
    _ensure_db()
    try:
        con = sqlite3.connect(_DB_PATH, timeout=3)
        con.execute(
            """INSERT OR REPLACE INTO world_models
               (session_id, created_at, updated_at, data)
               VALUES (?, ?, ?, ?)""",
            (world.session_id, world.created_at,
             world.updated_at, json.dumps(world.to_dict())),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[world_model] save error: {e}")


def load_world(session_id: str) -> WorldModel:
    """Load an existing world model or create a fresh one."""
    _ensure_db()
    try:
        con = sqlite3.connect(_DB_PATH, timeout=3)
        row = con.execute(
            "SELECT data FROM world_models WHERE session_id=?",
            (session_id,)
        ).fetchone()
        con.close()
        if row:
            data = json.loads(row[0])
            w    = WorldModel(session_id=session_id)
            for k, v in data.items():
                if hasattr(w, k):
                    setattr(w, k, v)
            return w
    except Exception as e:
        print(f"[world_model] load error: {e}")
    return WorldModel(session_id=session_id)


# ── CLI test ─────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  world_model.py — entity extraction and persistence test")
    print("=" * 65)

    world = WorldModel(session_id="test-session-001")

    queries = [
        ("Build a FastAPI app with JWT auth and PostgreSQL",    "python_dev"),
        ("Set up Docker deployment for the FastAPI backend",   "it_networking"),
        ("Write pytest tests for the JWT authentication flow", "python_dev"),
        ("Why is my nginx returning 502 when I proxy to port 8000?", "it_networking"),
    ]

    for query, agent in queries:
        world = update_from_query(world, query, agent=agent, outcome="completed")
        print(f"\n  After: '{query[:55]}...'")
        print(f"    Context:   {world.project_context}")
        print(f"    Goal:      {world.current_goal[:60]}...")
        print(f"    Entities:  {dict(list(world.entities.items())[:3])}")

    world.add_issue("nginx 502 when proxying to uvicorn", step_id="step_2")
    world.add_completed("FastAPI JWT auth endpoint implemented")

    print(f"\n  Summary: {world.context_summary()}")
    print(f"  Issues:  {world.known_issues}")
    print(f"  Tasks:   {world.completed_tasks}")
