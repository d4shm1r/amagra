"""
Behavioral-contract parity: /ask and /ask/stream persist identical state.

The contract (docs/records/REFACTOR_ANALYSIS_2026-07.md §1.1): transport is
the ONLY intended difference between the two chat endpoints. Same message in,
same records out — thread turn, session row, routing telemetry, trace row,
run-log row. Before the unified pipeline, /ask/stream persisted *nothing*:
chats from the streaming UI were invisible to threads, telemetry, and the
learning loop. These tests keep that from regressing.

Both endpoints run against the same mocked coordinator result, then each
persistence table is diffed on its content columns (timestamps, ids and
durations excluded).

NOTE on the filename: test_auth.py must be the first module to import `api`
(it sets REQUIRE_AUTH=1 pre-import), so this file is named test_routes_* to
sort after it — as every other api-importing test module does.

Run: python3 -m pytest tests/test_routes_ask_parity.py -v
"""

import json
import os
import sqlite3
import sys
import uuid
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

import pytest

import core.api_keys as _ak
from fastapi.testclient import TestClient
from api import app
from infrastructure.db import path as _dbpath
import routes.core as _core

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="parity-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


class _FakeMsg:
    content = "Parity response body — identical on both transports."


def _fake_result():
    return {
        "messages":               [_FakeMsg()],
        "active_agent":           "knowledge_learning",
        "brain_decision": {
            "signal_domain":  "general",
            "signal_shape":   "explanation",
            "signal_conf":    0.9,
            "complexity":     "simple",
            "confidence":     0.85,
            "action":         "generate",
            "memories_used":  [],
        },
        "reflect_level":          "none",
        "contradiction_detected": False,
    }


@pytest.fixture(autouse=True)
def _local_only(monkeypatch):
    """Force the coordinator path on both endpoints (no Anthropic, no network)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PREFER_ANTHROPIC", "0")
    monkeypatch.setattr(_core.coordinator, "invoke",
                        mock.MagicMock(side_effect=lambda state: _fake_result()))


def _stream_events(resp_text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in resp_text.splitlines()
            if line.startswith("data: ")]


def _rows(db: str, sql: str, args=()) -> list[tuple]:
    conn = sqlite3.connect(_dbpath(db) if os.path.sep not in db else db)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _persisted_state(message: str, thread_id: str) -> dict:
    """Everything a chat request must leave behind, on content columns only."""
    from core.run_log import _default_path as _runlog_path
    return {
        "turns": _rows("sessions",
                       "SELECT user_msg, agent_msg, agent FROM turns WHERE thread_id=?",
                       (thread_id,)),
        "thread": _rows("sessions",
                        "SELECT title, turn_count FROM threads WHERE id=?",
                        (thread_id,)),
        "session": _rows("sessions",
                         "SELECT user_input, response, agent, confidence FROM sessions WHERE user_input=?",
                         (message[:500],)),
        "telemetry": _rows("telemetry",
                           "SELECT agent, signal_conf, complexity FROM routing_telemetry WHERE query_prefix=?",
                           (message[:120],)),
        "trace": _rows("traces",
                       "SELECT agent, routing_reason, signal_domain, signal_shape, signal_conf "
                       "FROM traces WHERE user_message=?",
                       (message[:200],)),
        "run_log": _rows(_runlog_path(),
                         "SELECT task, output FROM runs WHERE task=?",
                         (message,)),
    }


def test_ask_and_stream_persist_identical_state():
    """§1.1: same message through both endpoints → identical rows everywhere."""
    tag = uuid.uuid4().hex[:8]
    msg_ask,    thread_ask    = f"parity check {tag} via ask",    f"parity-ask-{tag}"
    msg_stream, thread_stream = f"parity check {tag} via stream", f"parity-stream-{tag}"

    r = client.post("/ask", headers=HEADERS,
                    json={"message": msg_ask, "thread_id": thread_ask})
    assert r.status_code == 200, r.text
    assert r.json()["thread_id"] == thread_ask

    r = client.post("/ask/stream", headers=HEADERS,
                    json={"message": msg_stream, "thread_id": thread_stream})
    assert r.status_code == 200, r.text
    events = _stream_events(r.text)
    types  = [e["type"] for e in events]
    assert "done" in types and "error" not in types, events

    state_ask    = _persisted_state(msg_ask,    thread_ask)
    state_stream = _persisted_state(msg_stream, thread_stream)

    for table in state_ask:
        got, want = state_stream[table], state_ask[table]
        # Same number of rows, and identical content except the message text
        # itself (which intentionally differs by transport tag).
        norm = lambda rows: [tuple(  # noqa: E731
            c.replace("via stream", "via X").replace("via ask", "via X")
            if isinstance(c, str) else c
            for c in row) for row in rows]
        assert norm(got) == norm(want), (
            f"{table}: stream persisted {got!r}, /ask persisted {want!r}"
        )

    # Each run left exactly one row per table — not zero (the old streaming
    # bug) and not duplicates.
    for table, rows in state_ask.items():
        assert len(rows) == 1, f"{table}: expected 1 row from /ask, got {rows!r}"


def test_stream_done_event_carries_thread_and_context_ids():
    """The client can only continue a thread if the server says which one."""
    tag = uuid.uuid4().hex[:8]
    r = client.post("/ask/stream", headers=HEADERS,
                    json={"message": f"thread adoption check {tag}"})
    assert r.status_code == 200
    events = _stream_events(r.text)
    done = next(e for e in events if e["type"] == "done")
    routing = next(e for e in events if e["type"] == "routing")
    assert done.get("thread_id"), done
    assert done.get("context_id"), done
    assert routing.get("thread_id") == done["thread_id"]

    # A server-generated thread id is real: the turn is stored under it.
    turns = _rows("sessions",
                  "SELECT user_msg FROM turns WHERE thread_id=?",
                  (done["thread_id"],))
    assert len(turns) == 1


def test_stream_appends_to_existing_thread():
    """Follow-up messages with the adopted thread id continue the thread."""
    tag = uuid.uuid4().hex[:8]
    tid = f"parity-continue-{tag}"
    for i in range(2):
        r = client.post("/ask/stream", headers=HEADERS,
                        json={"message": f"turn {i} {tag}", "thread_id": tid})
        assert r.status_code == 200
    turns = _rows("sessions",
                  "SELECT user_msg FROM turns WHERE thread_id=? ORDER BY id",
                  (tid,))
    assert [t[0] for t in turns] == [f"turn 0 {tag}", f"turn 1 {tag}"]
    count = _rows("sessions", "SELECT turn_count FROM threads WHERE id=?", (tid,))
    assert count == [(2,)]
