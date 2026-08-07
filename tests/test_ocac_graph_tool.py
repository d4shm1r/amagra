"""
Tests for tools/ocac_graph.py — the read-only adapter onto OCAC's graph.yaml.

Uses a small synthetic graph.yaml (never the real vault) so these pass whether
or not this machine has ~/Desktop/OCAC-Vault. That absence case — available()
False, tools gated off — is itself the default-everywhere-else state and is
asserted explicitly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.catalog as catalog
import tools.ocac_graph as ocac

_FIXTURE = """\
nodes:
  - id: PROB-x
    type: OpenProblem
    title: "Problem X"
    status: open
    confidence: 0.5
    lean: prob_x_statement
  - id: GAP-y
    type: Gap
    title: "Gap Y blocking X"
    status: open
    confidence: 1.0
edges:
  - {source: PROB-x, relation: depends_on, target: GAP-y}
  - {source: GAP-y, relation: blocks, target: PROB-x}
"""


def _write_fixture(tmp_path):
    p = tmp_path / "graph.yaml"
    p.write_text(_FIXTURE)
    return str(p)


# ── available() ──────────────────────────────────────────────────────────

def test_available_false_for_missing_file(tmp_path):
    missing = str(tmp_path / "nope.yaml")
    assert ocac.available(missing) is False


def test_available_true_for_fixture(tmp_path):
    path = _write_fixture(tmp_path)
    assert ocac.available(path) is True


# ── get_node ─────────────────────────────────────────────────────────────

def test_get_node(tmp_path):
    path = _write_fixture(tmp_path)
    node = ocac.get_node("PROB-x", graph_path=path)
    assert node["type"] == "OpenProblem"
    assert node["lean"] == "prob_x_statement"


def test_get_node_unknown_raises(tmp_path):
    path = _write_fixture(tmp_path)
    try:
        ocac.get_node("NOPE", graph_path=path)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_get_node_no_graph_raises(tmp_path):
    missing = str(tmp_path / "nope.yaml")
    try:
        ocac.get_node("PROB-x", graph_path=missing)
        assert False, "expected GraphNotAvailable"
    except ocac.GraphNotAvailable:
        pass


# ── edges ────────────────────────────────────────────────────────────────

def test_edges_out(tmp_path):
    path = _write_fixture(tmp_path)
    out = ocac.edges("PROB-x", direction="out", graph_path=path)
    assert out == [{"source": "PROB-x", "relation": "depends_on", "target": "GAP-y"}]


def test_edges_in(tmp_path):
    path = _write_fixture(tmp_path)
    out = ocac.edges("PROB-x", direction="in", graph_path=path)
    assert out == [{"source": "GAP-y", "relation": "blocks", "target": "PROB-x"}]


def test_edges_both(tmp_path):
    path = _write_fixture(tmp_path)
    out = ocac.edges("PROB-x", direction="both", graph_path=path)
    assert len(out) == 2


def test_edges_relation_filter(tmp_path):
    path = _write_fixture(tmp_path)
    out = ocac.edges("PROB-x", direction="both", relation="blocks", graph_path=path)
    assert len(out) == 1
    assert out[0]["relation"] == "blocks"


# ── search ───────────────────────────────────────────────────────────────

def test_search_by_id_substring(tmp_path):
    path = _write_fixture(tmp_path)
    hits = ocac.search("prob-x", graph_path=path)
    assert [n["id"] for n in hits] == ["PROB-x"]


def test_search_by_title_substring(tmp_path):
    path = _write_fixture(tmp_path)
    hits = ocac.search("blocking", graph_path=path)
    assert [n["id"] for n in hits] == ["GAP-y"]


# ── mtime-keyed cache picks up edits ────────────────────────────────────

def test_cache_invalidates_on_mtime_change(tmp_path):
    path = _write_fixture(tmp_path)
    ocac.get_node("PROB-x", graph_path=path)  # warm the cache
    updated = _FIXTURE.replace(
        "nodes:\n",
        "nodes:\n  - id: PROB-z\n    type: OpenProblem\n    title: Z\n",
        1,
    )
    with open(path, "w") as fh:
        fh.write(updated)
    os.utime(path, (os.path.getmtime(path) + 5,) * 2)  # force a distinct mtime
    node = ocac.get_node("PROB-z", graph_path=path)
    assert node["title"] == "Z"


# ── catalog wiring ───────────────────────────────────────────────────────

def test_catalog_hides_ocac_tools_when_graph_absent(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", str(tmp_path / "nope.yaml"))
    tools = catalog.available_tools()
    assert "ocac_node" not in tools
    assert "ocac_edges" not in tools
    assert "ocac_search" not in tools


def test_catalog_exposes_ocac_tools_when_graph_present(monkeypatch, tmp_path):
    path = _write_fixture(tmp_path)
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", path)
    tools = catalog.available_tools()
    assert "ocac_node" in tools
    assert "ocac_edges" in tools
    assert "ocac_search" in tools


def test_catalog_execute_ocac_node(monkeypatch, tmp_path):
    path = _write_fixture(tmp_path)
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", path)
    out = catalog.execute("ocac_node", {"id": "PROB-x"})
    assert out["type"] == "OpenProblem"


def test_catalog_execute_ocac_edges(monkeypatch, tmp_path):
    path = _write_fixture(tmp_path)
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", path)
    out = catalog.execute("ocac_edges", {"id": "PROB-x", "direction": "in"})
    assert out["edges"][0]["relation"] == "blocks"


def test_catalog_execute_ocac_search(monkeypatch, tmp_path):
    path = _write_fixture(tmp_path)
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", path)
    out = catalog.execute("ocac_search", {"query": "Gap Y"})
    assert out["nodes"][0]["id"] == "GAP-y"


def test_catalog_execute_gated_off_raises_permission_error(monkeypatch, tmp_path):
    monkeypatch.setenv("AMAGRA_OCAC_GRAPH", str(tmp_path / "nope.yaml"))
    try:
        catalog.execute("ocac_node", {"id": "PROB-x"})
        assert False, "expected PermissionError"
    except PermissionError:
        pass
