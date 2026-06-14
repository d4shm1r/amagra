"""
Route tests for /workspace/* — the jailed file tool over HTTP.

Points AMAGRA_WORKSPACE at a temp dir (read live per request) and checks the
error-code mapping: 403 on escape, 404 on missing, 200 on happy path.
"""

import os
import sys
import tempfile
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _mod in (
    "langchain_ollama", "langchain_core", "langchain_core.messages",
    "langchain_core.documents", "langchain_core.documents.base",
    "langchain_core.runnables", "langchain_core.runnables.base",
    "langgraph", "langgraph.graph", "langgraph.graph.message",
    "langgraph.checkpoint", "langgraph.checkpoint.memory", "langgraph.prebuilt",
    "faiss", "sentence_transformers",
):
    sys.modules.setdefault(_mod, mock.MagicMock())

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="ws-test@test.com", tier="developer")}

_WS = tempfile.mkdtemp(prefix="amagra-ws-")


def setup_module(module):
    os.environ["AMAGRA_WORKSPACE"] = _WS
    with open(os.path.join(_WS, "readme.txt"), "w") as fh:
        fh.write("workspace file\nwith a marker token\n")
    os.mkdir(os.path.join(_WS, "pkg"))
    with open(os.path.join(_WS, "pkg", "mod.py"), "w") as fh:
        fh.write("print('hi')\n")


def teardown_module(module):
    os.environ.pop("AMAGRA_WORKSPACE", None)


def test_root_reports_workspace():
    r = client.get("/workspace/root", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["root"].endswith(os.path.basename(_WS))


def test_read_ok():
    r = client.get("/workspace/read", params={"path": "readme.txt"}, headers=HEADERS)
    assert r.status_code == 200
    assert "marker token" in r.json()["content"]


def test_list_ok():
    r = client.get("/workspace/list", headers=HEADERS)
    assert r.status_code == 200
    names = {e["name"] for e in r.json()["entries"]}
    assert {"readme.txt", "pkg"} <= names


def test_search_ok():
    r = client.get("/workspace/search", params={"q": "marker"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_traversal_returns_403():
    r = client.get("/workspace/read", params={"path": "../../etc/passwd"}, headers=HEADERS)
    assert r.status_code == 403


def test_missing_returns_404():
    r = client.get("/workspace/read", params={"path": "ghost.txt"}, headers=HEADERS)
    assert r.status_code == 404
