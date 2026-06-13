"""
Agent manifest — the schema that makes routing dynamic.

Today: KEYWORD_MAP in orchestration/router.py is a hardcoded dict. That works
for 10 agents but breaks as soon as users can add their own.

The manifest is the contract between an agent and the runtime. When the router
loads manifests instead of a hardcoded dict, adding an agent requires no changes
to router.py or coordinator.py — only a manifest file and an entrypoint module.

Fields
------
id                  Unique snake_case identifier. Must match the node name in
                    coordinator.py and the key in agents/registry.py.
name                Human-readable label shown in the UI.
description         One-sentence summary used for LLM-fallback routing.
skills              High-level capability tags (used by skill_graph.py).
keywords            Regex-ready tokens used by the keyword router. Matched
                    with word-boundary guards, same as KEYWORD_MAP entries.
routing_examples    Representative queries — used for few-shot LLM routing
                    and future embedding-based similarity routing.
confidence_threshold Minimum keyword score to route directly without CoreBrain.
                    Default 0.75 (≈ 1 keyword match with no ambiguity).
capabilities        Runtime features the agent can use. The coordinator checks
                    this before dispatching when a capability is required.
                    Known values: memory, coding, execution, web_search,
                    file_access, planning.
provider            "local" = bundled with Amagra. "community" or "user" for
                    imported agents. Shown as a trust badge in the UI.
entrypoint          Python module path to the agent's build function, relative
                    to the project root.

Loading
-------
load_manifests() returns a dict keyed by agent id. It merges:
  1. Built-in manifests: agents/manifests/*.yaml
  2. User manifests:     ~/.amagra/agents/*.yaml  (Phase 4 — not yet active)

The router calls manifest_to_keyword_map() to produce a KEYWORD_MAP-compatible
dict from loaded manifests, so router.py can stay unchanged during the migration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentManifest:
    id:                   str
    name:                 str
    description:          str
    skills:               list[str]               = field(default_factory=list)
    keywords:             list[str]               = field(default_factory=list)
    routing_examples:     list[str]               = field(default_factory=list)
    confidence_threshold: float                   = 0.75
    capabilities:         list[str]               = field(default_factory=list)
    provider:             str                     = "local"
    entrypoint:           str                     = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentManifest":
        return cls(
            id                   = data["id"],
            name                 = data["name"],
            description          = data.get("description", ""),
            skills               = data.get("skills", []),
            keywords             = data.get("keywords", []),
            routing_examples     = data.get("routing_examples", []),
            confidence_threshold = float(data.get("confidence_threshold", 0.75)),
            capabilities         = data.get("capabilities", []),
            provider             = data.get("provider", "local"),
            entrypoint           = data.get("entrypoint", ""),
        )


def load_manifests(extra_dirs: list[str] | None = None) -> dict[str, AgentManifest]:
    """
    Load all agent manifests and return them keyed by agent id.

    Search order (later entries win on id collision):
      1. agents/manifests/*.yaml  — bundled manifests
      2. Paths in extra_dirs      — for testing or user-supplied manifests
    """
    try:
        import yaml
    except ImportError:
        return {}

    search_dirs: list[Path] = [
        Path(__file__).parent.parent / "agents" / "manifests",
    ]
    if extra_dirs:
        search_dirs.extend(Path(d) for d in extra_dirs)

    manifests: dict[str, AgentManifest] = {}
    for directory in search_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                if not data or "id" not in data:
                    continue
                m = AgentManifest.from_dict(data)
                manifests[m.id] = m
            except Exception as exc:
                print(f"[manifest] failed to load {path}: {exc}")

    return manifests


def manifest_to_keyword_map(
    manifests: dict[str, AgentManifest],
) -> dict[str, list[str]]:
    """
    Convert loaded manifests into a KEYWORD_MAP-compatible dict.

    Keywords from manifests are plain strings. The router wraps them with
    word-boundary guards ((?<!\\w)...(?!\\w)) at match time, matching the
    existing KEYWORD_MAP regex convention.

    This allows router.py to replace its hardcoded KEYWORD_MAP with:
        from providers.manifest import load_manifests, manifest_to_keyword_map
        KEYWORD_MAP = manifest_to_keyword_map(load_manifests())
    without any further changes.
    """
    return {
        agent_id: [
            rf"(?<!\w){re.escape(kw)}(?!\w)"
            for kw in manifest.keywords
        ]
        for agent_id, manifest in manifests.items()
        if manifest.keywords
    }


import re  # noqa: E402 — placed after the function that uses it for clarity
