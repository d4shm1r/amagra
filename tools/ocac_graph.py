"""
tools/ocac_graph.py — thin read-only adapter onto the OCAC research graph.

OCAC (~/ocac, ~/ocac_2, ~/Desktop/OCAC-Vault) is a separate Lean 4 formalization
project with its own authoritative, typed, human-curated knowledge graph:
90-Meta/graph.yaml. Its nodes carry id/type/status/confidence/a Lean symbol;
its edges carry a relation vocabulary (depends_on, blocks, disproves, resolves,
supersedes, ...). That graph is generated and drift-checked by OCAC's own
tooling (build_vault.py, check_drift.py) — it is the single source of truth.

This module does not copy, mirror, or re-index it. It reads graph.yaml
directly at query time and caches the parse keyed on the file's mtime, so an
OCAC-side rebuild is picked up automatically with no coordination required.
Amagra never writes to this file.

Configuration (env):
    AMAGRA_OCAC_GRAPH   path to graph.yaml
                        (default: ~/Desktop/OCAC-Vault/90-Meta/graph.yaml)

`available()` is False whenever the file isn't on disk, which is the normal
state for anyone running Amagra without this specific research vault present —
the dependent tools (tools/catalog.py) are gated on it and simply don't appear.
"""

import os

import yaml

_DEFAULT_PATH = os.path.expanduser("~/Desktop/OCAC-Vault/90-Meta/graph.yaml")

# Keyed on path so switching AMAGRA_OCAC_GRAPH mid-process (tests) can't serve
# a stale parse from a different file.
_cache: dict = {"path": None, "mtime": None, "nodes": None, "edges": None}


class GraphNotAvailable(Exception):
    """graph.yaml isn't at the configured path."""


def _graph_path() -> str:
    return os.environ.get("AMAGRA_OCAC_GRAPH", _DEFAULT_PATH)


def available(graph_path: str | None = None) -> bool:
    return os.path.isfile(graph_path or _graph_path())


def _load(graph_path: str | None = None):
    path = graph_path or _graph_path()
    mtime = os.path.getmtime(path)
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return _cache["nodes"], _cache["edges"]
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    nodes = {n["id"]: n for n in doc.get("nodes", [])}
    all_edges = doc.get("edges", [])
    _cache.update(path=path, mtime=mtime, nodes=nodes, edges=all_edges)
    return nodes, all_edges


def _require(graph_path: str | None):
    if not available(graph_path):
        raise GraphNotAvailable(graph_path or _graph_path())


def get_node(node_id: str, graph_path: str | None = None) -> dict:
    """The node's own fields (type, status, confidence, lean symbol, tags, provenance, ...)."""
    _require(graph_path)
    nodes, _ = _load(graph_path)
    node = nodes.get(node_id)
    if node is None:
        raise KeyError(f"no such node: {node_id!r}")
    return node


def edges(node_id: str, direction: str = "out", relation: str | None = None,
          graph_path: str | None = None) -> list[dict]:
    """Edges touching node_id. direction: 'out' (node_id is source), 'in'
    (node_id is target), or 'both'. Optionally filtered to one relation type
    (e.g. 'depends_on', 'blocks', 'disproves') — see graph.yaml for the vocabulary."""
    _require(graph_path)
    _, all_edges = _load(graph_path)

    def touches(e: dict) -> bool:
        if direction == "out":
            hit = e["source"] == node_id
        elif direction == "in":
            hit = e["target"] == node_id
        else:
            hit = e["source"] == node_id or e["target"] == node_id
        return hit and (relation is None or e["relation"] == relation)

    return [e for e in all_edges if touches(e)]


def search(query: str, graph_path: str | None = None, limit: int = 20) -> list[dict]:
    """Case-insensitive substring match over node id and title."""
    _require(graph_path)
    nodes, _ = _load(graph_path)
    q = query.lower()
    hits = [n for n in nodes.values()
            if q in n["id"].lower() or q in n.get("title", "").lower()]
    return hits[:limit]
