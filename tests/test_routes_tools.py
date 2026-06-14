"""
Route tests for /tools/* — list (no LLM) and run (LLM monkeypatched).
"""

import os
import sys
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
import routes.tools as rtools
from fastapi.testclient import TestClient
from api import app

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="tools-test@test.com", tier="developer")}


def test_list_includes_read_tools():
    r = client.get("/tools/list", headers=HEADERS)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert {"read_file", "list_dir", "search_files"} <= names


def test_run_empty_prompt_400():
    r = client.post("/tools/run", json={"prompt": "  "}, headers=HEADERS)
    assert r.status_code == 400


def test_run_drives_loop_with_mocked_llm(monkeypatch):
    # Fake model: answers directly, no tool call.
    monkeypatch.setattr(rtools, "_llm_invoke", lambda transcript: "42 is the answer.")
    r = client.post("/tools/run", json={"prompt": "what is the answer?"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "42 is the answer."
    assert body["stopped"] == "answer"
    assert body["calls"] == []
