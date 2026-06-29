"""
Tests for #70 — decisions key on prompt_version_id, not just the raw prompt string.

Pure store-level coverage (no FastAPI): record() persists the link, get_by_id /
recent surface it, omitting it stays back-compatible, and init() migrates a table
created before the column existed. All SQLite is isolated into a temp single-file
DB via AMAGRA_DB so the real logs/ are never touched.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.NamedTemporaryFile(suffix="_pvid.db", delete=False)
_tmp.close()
os.environ["AMAGRA_DB"] = _tmp.name

from decision import model_choices  # noqa: E402  (after AMAGRA_DB is set)


@pytest.fixture(autouse=True)
def _isolated_db():
    os.environ["AMAGRA_DB"] = _tmp.name
    model_choices.init()
    yield


def test_record_persists_prompt_version_id():
    did = model_choices.record(
        "Summarize the contract", "anthropic",
        chosen_model="claude", prompt_version_id="contract@v3",
    )
    assert did > 0
    rec = model_choices.get_by_id(did)
    assert rec["prompt_version_id"] == "contract@v3"


def test_record_without_version_id_is_back_compatible():
    did = model_choices.record("legacy prompt", "openai", chosen_model="gpt")
    assert did > 0
    rec = model_choices.get_by_id(did)
    assert rec["prompt_version_id"] is None        # absent, not crashing
    assert rec["prompt"] == "legacy prompt"         # still keyed by text as before


def test_recent_surfaces_prompt_version_id():
    model_choices.record("p", "anthropic", prompt_version_id="p@v1")
    rows = model_choices.recent(limit=5)
    assert any(r["prompt_version_id"] == "p@v1" for r in rows)


def test_init_migrates_table_missing_the_column():
    """A model_decisions table created before #70 must gain the column on init()."""
    c = model_choices._conn()
    c.execute("DROP TABLE IF EXISTS model_decisions")
    # Recreate the pre-#70 schema (no prompt_version_id), with one legacy row.
    c.execute("""
        CREATE TABLE model_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            project TEXT DEFAULT '', prompt TEXT NOT NULL, system TEXT DEFAULT '',
            temperature REAL DEFAULT 0.2, candidates TEXT DEFAULT '[]',
            chosen_provider TEXT NOT NULL, chosen_model TEXT DEFAULT '',
            rationale TEXT DEFAULT '', rationale_tags TEXT DEFAULT '[]',
            provenance TEXT DEFAULT 'derived', superseded_by INTEGER DEFAULT NULL,
            memory_mirrored INTEGER DEFAULT 0
        )
    """)
    c.execute("INSERT INTO model_decisions (timestamp, prompt, chosen_provider) "
              "VALUES ('2026-01-01T00:00:00+00:00', 'old prompt', 'ollama')")
    c.commit()
    cols = {row[1] for row in c.execute("PRAGMA table_info(model_decisions)").fetchall()}
    assert "prompt_version_id" not in cols          # precondition: legacy schema
    c.close()

    model_choices.init()                            # the migration under test

    # Legacy row survives with a NULL version id, and new rows can set it.
    legacy = model_choices.recent(limit=10)
    assert any(r["prompt"] == "old prompt" and r["prompt_version_id"] is None for r in legacy)
    did = model_choices.record("new", "anthropic", prompt_version_id="new@v1")
    assert model_choices.get_by_id(did)["prompt_version_id"] == "new@v1"
