"""
/ask/stream forwards real coordinator lifecycle events as `step` frames.

The point of these tests is that the frames are *earned*: the fake coordinator
emits on the event bus using the run_id it was handed, so a forwarded step
proves the subscription, the run_id filter and the queue drain all work. An
event emitted under a foreign run_id must not appear — the bus is global and
requests are concurrent.

Run: python3 -m pytest tests/test_routes_stream_steps.py -v
"""

import os
import sys
import json
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
from infrastructure.event_bus import emit, EventType

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="stream-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


class _FakeMsg:
    content = "streamed body"


def _fake_invoke_emitting(*, foreign: bool = False):
    """Coordinator stand-in that emits on the bus like the real one does."""
    def _invoke(state):
        run_id = state.get("run_id", "")
        emit(EventType.AGENT_SELECTED, {
            "run_id": run_id, "agent": "coding_agent",
            "confidence": 0.91, "action": "generate", "signal": "code/patch",
        }, persist=False)
        if foreign:
            emit(EventType.AGENT_SELECTED, {
                "run_id": "some-other-request", "agent": "leaked_agent",
            }, persist=False)
        emit(EventType.STEP_VERIFIED_PASS, {
            "run_id": run_id, "agent": "coding_agent",
            "score": 0.88, "step_id": run_id, "recommendation": "continue",
        }, persist=False)
        return {
            "messages": [_FakeMsg()],
            "active_agent": "coding_agent",
            "brain_decision": {"memories_used": []},
            "reflect_level": "none",
        }
    return _invoke


def _frames(body: str):
    out = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                out.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return out


def _stream(monkeypatch_env=True, **kw):
    """Drive /ask/stream down the coordinator (no-API-key) fallback path."""
    prev = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        with mock.patch("routes.core.coordinator") as _coord:
            _coord.invoke = _fake_invoke_emitting(**kw)
            r = client.post("/ask/stream", json={"message": "fix the parser"},
                            headers=HEADERS)
            return r, _frames(r.text)
    finally:
        if prev is not None:
            os.environ["ANTHROPIC_API_KEY"] = prev


def test_agent_selected_reaches_client_as_step_frame():
    r, frames = _stream()
    assert r.status_code == 200
    steps = [f for f in frames if f.get("type") == "step"]
    assert any(f["event"] == "agent.selected" for f in steps), frames


def test_step_frame_carries_real_payload():
    _, frames = _stream()
    sel = next(f for f in frames
               if f.get("type") == "step" and f["event"] == "agent.selected")
    assert sel["payload"]["agent"] == "coding_agent"
    assert sel["payload"]["confidence"] == 0.91


def test_verification_result_is_streamed():
    _, frames = _stream()
    ver = next(f for f in frames
               if f.get("type") == "step" and f["event"] == "step.verified.pass")
    assert ver["payload"]["score"] == 0.88


def test_foreign_run_id_is_not_forwarded():
    _, frames = _stream(foreign=True)
    agents = [f["payload"].get("agent") for f in frames if f.get("type") == "step"]
    assert "leaked_agent" not in agents, agents


def test_stream_still_delivers_answer_and_done():
    _, frames = _stream()
    assert any(f.get("type") == "token" and "streamed body" in f.get("text", "")
               for f in frames)
    assert frames[-1]["type"] == "done"


def test_handlers_unsubscribed_after_request():
    """A completed request must leave no handler behind on the global bus."""
    from infrastructure import event_bus
    before = sum(len(v) for v in event_bus._HANDLERS.values())
    _stream()
    after = sum(len(v) for v in event_bus._HANDLERS.values())
    assert after == before, f"handler leak: {before} → {after}"
