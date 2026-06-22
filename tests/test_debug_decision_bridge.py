"""
Tests for the debugger→memory bridge (Tier 0).

Covers the store (decision/model_choices.py) along its two trust axes —
provenance (explicit vs derived) and currency (supersede) — plus the
POST /debug/decision and GET /debug/decisions endpoints.

DB isolation: AMAGRA_DB is pointed at a temp file *before* api/model_choices
are imported, so every logical database (including model_decisions) collapses
into a throwaway file and the real logs/ are never touched.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate all SQLite into one temp file before anything opens a connection.
# AMAGRA_DB is process-global. The test baseline (per conftest) leaves it unset,
# so we force it on for *every* test in this module — robust to another module's
# teardown popping it mid-session — and pop it back to the clean baseline when
# this module finishes, rather than restoring a value another module may have
# leaked at import time.
_tmp = tempfile.NamedTemporaryFile(suffix="_bridge.db", delete=False)
_tmp.close()
os.environ["AMAGRA_DB"] = _tmp.name


@pytest.fixture(autouse=True)
def _force_isolated_db():
    os.environ["AMAGRA_DB"] = _tmp.name
    model_choices.init()
    yield


@pytest.fixture(scope="module", autouse=True)
def _clear_amagra_db():
    yield
    os.environ.pop("AMAGRA_DB", None)

from decision import model_choices
model_choices.init()  # create the table inside the isolated single-file DB

from fastapi.testclient import TestClient
from api import app

import core.api_keys as _ak

client  = TestClient(app, raise_server_exceptions=False)
_key    = _ak.create_key(owner="bridge-test@test.com", tier="developer")
HEADERS = {"X-API-Key": _key}


# ── store: provenance axis ────────────────────────────────────────────────────

def test_rationale_makes_record_explicit():
    did = model_choices.record(
        "Summarize an API doc", "anthropic", chosen_model="claude-sonnet-4-6",
        rationale="cleanest formatting",
    )
    rec = model_choices.get_by_id(did)
    assert rec["provenance"] == "explicit"
    assert model_choices.quality_for("explicit") == 1.0


def test_bare_selection_is_derived():
    did = model_choices.record("Draft a regex", "openai", chosen_model="gpt-4o-mini")
    rec = model_choices.get_by_id(did)
    assert rec["provenance"] == "derived"
    assert model_choices.quality_for("derived") < model_choices.quality_for("explicit")


def test_tags_alone_count_as_explicit():
    did = model_choices.record("Write tests", "ollama", rationale_tags=["Reasoning"])
    assert model_choices.get_by_id(did)["provenance"] == "explicit"


# ── store: currency axis ──────────────────────────────────────────────────────

def test_supersede_marks_old_record_stale():
    old = model_choices.record("Pick a model for X", "openai", chosen_model="gpt-4o-mini")
    new = model_choices.record("Pick a model for X", "anthropic",
                               chosen_model="claude-sonnet-4-6", rationale="better reasoning")
    assert model_choices.supersede(old, new) is True
    assert model_choices.get_by_id(old)["active"] is False
    assert model_choices.get_by_id(old)["superseded_by"] == new
    assert model_choices.get_by_id(new)["active"] is True


def test_active_only_filter_hides_superseded():
    project = "currency-proj"
    a = model_choices.record("q", "openai", chosen_model="gpt-4o-mini", project=project)
    b = model_choices.record("q", "anthropic", chosen_model="claude-sonnet-4-6", project=project)
    model_choices.supersede(a, b)
    active = model_choices.recent(project=project, active_only=True)
    ids = {r["id"] for r in active}
    assert b in ids and a not in ids


# ── coverage (SKC-style leading indicator) ────────────────────────────────────

def test_coverage_counts_provenance_and_currency():
    project = "coverage-proj"
    e = model_choices.record("p", "anthropic", rationale="why", project=project)
    model_choices.record("p", "openai", project=project)          # derived
    s = model_choices.record("p", "ollama", project=project)      # will be superseded
    t = model_choices.record("p", "anthropic", rationale="newer", project=project)
    model_choices.supersede(s, t)

    cov = model_choices.coverage(project=project)
    assert cov["total"] == 4
    assert cov["explicit"] == 2 and cov["derived"] == 2
    assert cov["superseded"] == 1 and cov["active"] == 3
    assert 0.0 <= cov["explicit_ratio"] <= 1.0


# ── API endpoints ─────────────────────────────────────────────────────────────

def test_post_decision_persists_and_reports_provenance():
    r = client.post("/debug/decision", headers=HEADERS, json={
        "prompt": "Generate a changelog",
        "chosen_provider": "anthropic",
        "chosen_model": "claude-sonnet-4-6",
        "candidates": [
            {"provider": "anthropic", "model": "claude-sonnet-4-6", "words": 80},
            {"provider": "openai", "model": "gpt-4o-mini", "words": 60},
        ],
        "rationale": "more accurate structure",
        "rationale_tags": ["Accuracy"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["provenance"] == "explicit"
    assert isinstance(body["decision_id"], int) and body["decision_id"] > 0


def test_get_decisions_returns_records_and_coverage():
    client.post("/debug/decision", headers=HEADERS, json={
        "prompt": "List endpoints", "chosen_provider": "openai", "chosen_model": "gpt-4o-mini",
    })
    r = client.get("/debug/decisions?limit=10", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "decisions" in body and "coverage" in body
    assert isinstance(body["decisions"], list)
    assert "explicit_ratio" in body["coverage"]


def test_post_decision_supersedes_prior_via_api():
    first = client.post("/debug/decision", headers=HEADERS, json={
        "prompt": "Choose a summarizer", "chosen_provider": "openai", "chosen_model": "gpt-4o-mini",
    }).json()["decision_id"]
    second = client.post("/debug/decision", headers=HEADERS, json={
        "prompt": "Choose a summarizer", "chosen_provider": "anthropic",
        "chosen_model": "claude-sonnet-4-6", "rationale": "switched — better quality",
        "supersedes": first,
    })
    assert second.status_code == 200
    assert model_choices.get_by_id(first)["active"] is False


def test_post_decision_tags_project_and_filters():
    """The UI posts a sticky `project`; it must persist and be filterable."""
    client.post("/debug/decision", headers=HEADERS, json={
        "prompt": "Pick a model", "chosen_provider": "anthropic",
        "chosen_model": "claude-sonnet-4-6", "rationale": "x", "project": "billing-svc",
    })
    r = client.get("/debug/decisions?project=billing-svc", headers=HEADERS)
    assert r.status_code == 200
    decisions = r.json()["decisions"]
    assert decisions and all(d["project"] == "billing-svc" for d in decisions)
