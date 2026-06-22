"""
Tests for "Explain this project" (routes/project.py).

The behaviour that matters is the safety split:
  * structured decisions are ALWAYS returned (showing the user their own records);
  * the LLM narrative is produced ONLY behind a fresh PASS on the recall gate.

Isolation: AMAGRA_DB collapses SQLite (incl. model_decisions) into a temp file
and AMAGRA_DATA_DIR relocates the gate verdict — both captured and restored at
module teardown so later test modules are unaffected.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.NamedTemporaryFile(suffix="_explain.db", delete=False)
_tmp.close()
_tmpdir = tempfile.mkdtemp(suffix="_explain_data")
os.environ["AMAGRA_DB"] = _tmp.name
os.environ["AMAGRA_DATA_DIR"] = _tmpdir

from decision import model_choices
model_choices.init()

from evaluation import memory_gate
from fastapi.testclient import TestClient
from api import app
import core.api_keys as _ak

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="explain-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# Force this module's isolation on for every test (robust to another module's
# teardown clearing the env mid-session); pop back to the clean baseline at end.
@pytest.fixture(autouse=True)
def _force_isolated_env():
    os.environ["AMAGRA_DB"] = _tmp.name
    os.environ["AMAGRA_DATA_DIR"] = _tmpdir
    model_choices.init()
    yield


@pytest.fixture(scope="module", autouse=True)
def _clear_env():
    yield
    os.environ.pop("AMAGRA_DB", None)
    os.environ.pop("AMAGRA_DATA_DIR", None)


def _pass_gate():
    from datetime import datetime, timezone
    memory_gate.write_verdict({"passed": True,
                               "generated_at": datetime.now(timezone.utc).isoformat()})


def _fail_gate():
    from datetime import datetime, timezone
    memory_gate.write_verdict({"passed": False, "failures": ["recall_at_3=0.40 < 0.90"],
                               "generated_at": datetime.now(timezone.utc).isoformat()})


# ── empty project ─────────────────────────────────────────────────────────────

def test_empty_project_has_no_summary():
    r = client.get("/project/explain?project=empty-proj", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["decisions"] == []
    assert body["summary"] is None
    assert "no decisions recorded" in body["summary_note"]


# ── gated: decisions returned, narrative withheld ─────────────────────────────

def test_gated_returns_decisions_but_withholds_summary():
    model_choices.record("Pick a summarizer", "anthropic",
                         chosen_model="claude-sonnet-4-6",
                         rationale="best structure", project="gated-proj")
    _fail_gate()
    r = client.get("/project/explain?project=gated-proj", headers=HEADERS)
    body = r.json()
    assert body["synthesis_allowed"] is False
    assert len(body["decisions"]) == 1          # retrieval still works
    assert body["summary"] is None              # synthesis is held
    assert "withheld" in body["summary_note"]


# ── allowed: synthesis runs (provider mocked) ─────────────────────────────────

def test_synthesizes_when_gate_passes(monkeypatch):
    model_choices.record("Generate API docs", "anthropic",
                         chosen_model="claude-sonnet-4-6",
                         rationale="cleanest formatting", project="open-proj")
    _pass_gate()

    class _Fake:
        def generate(self, prompt, system_prompt=None, temperature=0.2):
            # The confirmed rationale must reach the model.
            assert "[confirmed]" in prompt
            return "This project standardized on Claude for documentation work."

    monkeypatch.setattr("routes.project._current_provider_body", lambda: {"provider": "anthropic"})
    monkeypatch.setattr("routes.project._build_provider", lambda body: _Fake())

    r = client.get("/project/explain?project=open-proj", headers=HEADERS)
    body = r.json()
    assert body["synthesis_allowed"] is True
    assert body["summary"] == "This project standardized on Claude for documentation work."
    assert body["summary_note"] is None


def test_provider_failure_degrades_gracefully(monkeypatch):
    model_choices.record("Choose embedder", "ollama", rationale="local", project="degrade-proj")
    _pass_gate()
    monkeypatch.setattr("routes.project._current_provider_body", lambda: None)  # no provider
    r = client.get("/project/explain?project=degrade-proj", headers=HEADERS)
    body = r.json()
    assert body["summary"] is None
    assert "no model provider" in body["summary_note"]
    assert len(body["decisions"]) == 1


# ── confidence hierarchy surfaces in counts + only active decisions ───────────

def test_counts_split_confirmed_tentative_and_exclude_superseded():
    p = "counts-proj"
    model_choices.record("q", "anthropic", rationale="why", project=p)   # confirmed
    model_choices.record("q", "openai", project=p)                       # tentative
    old = model_choices.record("q", "ollama", rationale="old", project=p)
    new = model_choices.record("q", "anthropic", rationale="newer", project=p)
    model_choices.supersede(old, new)

    _fail_gate()  # keep it deterministic — no LLM call
    r = client.get(f"/project/explain?project={p}", headers=HEADERS)
    body = r.json()
    # 4 recorded, 1 superseded → 3 active; of those 2 confirmed, 1 tentative.
    assert body["counts"]["active"] == 3
    assert body["counts"]["confirmed"] == 2
    assert body["counts"]["tentative"] == 1
    assert all(d["active"] for d in body["decisions"])
