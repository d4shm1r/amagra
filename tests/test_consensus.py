"""
Tests for the Consensus Engine.

  - core.consensus.analyze: pure agreement math with an injected embedder.
  - POST /consensus: fan-out + analysis + optional synthesis, all mocked offline.
"""
import math
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

from core import consensus as cc  # noqa: E402


# ── pure analysis ────────────────────────────────────────────────────────────

def test_single_text_is_not_comparable():
    out = cc.analyze(["only one"], embed_fn=lambda t: [1.0, 0.0])
    assert out["verdict"] == "single"
    assert out["agreement_score"] is None
    assert out["representative_index"] == 0


def test_identical_answers_reach_consensus():
    embed = lambda t: [1.0, 0.0, 0.0]  # noqa: E731 - every answer maps the same
    out = cc.analyze(["blue", "blue", "blue"], embed_fn=embed)
    assert out["verdict"] == "consensus"
    assert out["agreement_score"] == 1.0
    assert out["dissenters"] == []
    assert out["n"] == 3


def test_outlier_is_flagged_as_dissenter():
    # two aligned answers + one orthogonal → divergent, the odd one out named.
    def embed(t):
        return [0.0, 1.0] if "yellow" in t else [1.0, 0.0]
    out = cc.analyze(["blue", "blue", "yellow"], embed_fn=embed)
    assert out["verdict"] == "divergent"
    assert out["dissenters"] == [2]
    assert out["representative_index"] in (0, 1)  # one of the aligned pair


def test_partial_agreement_band():
    # two answers at cosine ~0.75 → falls in the partial band, no dissenters (n<3).
    def embed(t):
        return [1.0, 0.0] if t == "a" else [0.75, math.sqrt(1 - 0.75**2)]
    out = cc.analyze(["a", "b"], embed_fn=embed)
    assert out["verdict"] == "partial"
    assert 0.68 <= out["agreement_score"] < 0.82
    assert out["dissenters"] == []


def test_empty_slots_preserve_original_indexing():
    def embed(t):
        return [1.0, 0.0]
    out = cc.analyze(["x", "", "x"], embed_fn=embed)  # middle answer failed
    assert out["n"] == 2
    assert out["per_candidate"][1] is None        # failed slot stays None
    assert out["matrix"][1] == [None, None, None]


def test_summarize_is_human_readable():
    assert "consensus" in cc.summarize(
        {"verdict": "consensus", "agreement_score": 0.9}).lower()
    assert "diverge" in cc.summarize(
        {"verdict": "divergent", "agreement_score": 0.3, "dissenters": [2]}).lower()


# ── route ────────────────────────────────────────────────────────────────────

import core.api_keys as _ak  # noqa: E402
import routes.consensus as rc  # noqa: E402
from routes.debug_prompt import DebugResult  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from api import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
HEADERS = {"X-API-Key": _ak.create_key(owner="consensus-test@test.com", tier="developer")}

_TWO_MODELS = [
    {"provider": "ollama", "model": "m1"},
    {"provider": "ollama", "model": "m2"},
]


def _fake_run_one(body, prompt, system, temperature):
    # Each model returns the same answer → should reach consensus.
    return DebugResult(provider=body["provider"], model=body["model"],
                       output="The sky is blue.", latency_ms=5, chars=16, words=4)


def _fake_embed(text):
    return [1.0, 0.0, 0.0]  # identical vectors → perfect agreement


def test_consensus_route_reaches_verdict():
    with mock.patch.object(rc, "_resolve_models", return_value=_TWO_MODELS), \
         mock.patch.object(rc, "_run_one", side_effect=_fake_run_one), \
         mock.patch("memory_core.db.get_embedding", side_effect=_fake_embed):
        r = client.post("/consensus",
                        json={"prompt": "What colour is the sky?", "synthesize": False},
                        headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "consensus"
    assert body["n_ok"] == 2
    assert body["agreement_score"] == 1.0
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["agreement"] == 1.0
    assert body["consensus_answer"] is None  # synthesis disabled


def test_consensus_route_degrades_when_embedder_down():
    def boom(text):
        raise RuntimeError("ollama unreachable")
    with mock.patch.object(rc, "_resolve_models", return_value=_TWO_MODELS), \
         mock.patch.object(rc, "_run_one", side_effect=_fake_run_one), \
         mock.patch("memory_core.db.get_embedding", side_effect=boom):
        r = client.post("/consensus",
                        json={"prompt": "x", "synthesize": False}, headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "error"
    assert len(body["candidates"]) == 2          # answers still returned
    assert "unavailable" in (body["note"] or "")


def test_consensus_route_synthesizes_via_judge():
    fake_judge = mock.MagicMock()
    fake_judge.generate.return_value = "CONSENSUS:\nThe sky is blue.\n\nDISAGREEMENT:\nNone."
    with mock.patch.object(rc, "_resolve_models", return_value=_TWO_MODELS), \
         mock.patch.object(rc, "_run_one", side_effect=_fake_run_one), \
         mock.patch.object(rc, "_build_for", return_value=fake_judge), \
         mock.patch("memory_core.db.get_embedding", side_effect=_fake_embed):
        r = client.post("/consensus",
                        json={"prompt": "What colour is the sky?", "synthesize": True},
                        headers=HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consensus_answer"] == "The sky is blue."
    assert body["contradiction_note"] is None     # "None." → no disagreement
    assert body["synthesized_by"] == "ollama/m1"
    fake_judge.generate.assert_called_once()
