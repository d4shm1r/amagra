"""
Unit tests for memory_core/filter.py — no LLM, no DB required (duplicate check uses
a temp SQLite). Covers clean_content, should_save, is_duplicate, and all gate paths.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import memory_core.filter as mf


# ── clean_content ─────────────────────────────────────────────────────────────

def test_clean_content_strips_fluff_opener():
    dirty = "I'm excited to help you! To configure SSH, edit /etc/ssh/sshd_config and set PermitRootLogin no."
    cleaned = mf.clean_content(dirty)
    assert "excited" not in cleaned.lower()
    assert "sshd_config" in cleaned

def test_clean_content_strips_system_ok():
    # SYSTEM OK is only stripped when followed by an excited opener — test the opener stripping
    s = "**SYSTEM OK** I'm thrilled to assist! Let's explore LangGraph together and dive into technical details."
    cleaned = mf.clean_content(s)
    assert "thrilled" not in cleaned.lower()

def test_clean_content_preserves_pure_content():
    content = "def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n - 1)"
    assert mf.clean_content(content) == content

def test_clean_content_empty_returns_empty():
    assert mf.clean_content("") == ""
    assert mf.clean_content("   ") == "   "

def test_clean_content_strips_certainly_opener():
    s = "Certainly! Here is how DNS resolution works at a high level in modern Linux systems."
    cleaned = mf.clean_content(s)
    assert "certainly" not in cleaned.lower()
    assert "dns" in cleaned.lower()

def test_clean_content_preserves_content_after_multiple_openers():
    s = "Of course. Sure thing! FastAPI dependency injection uses Depends() to declare shared logic."
    cleaned = mf.clean_content(s)
    assert "fastapi" in cleaned.lower()


# ── should_save: fluff rejection ─────────────────────────────────────────────

def test_should_save_rejects_hard_fluff():
    ok, reason = mf.should_save("As an AI language model, I'm happy to assist you today.", "chat", "terse")
    assert not ok
    assert reason == "fluff"

def test_should_save_rejects_soft_fluff():
    content = "I hope this helps. Let me know if you need more. Feel free to ask anything else at all!"
    ok, reason = mf.should_save(content, "chat", "terse")
    assert not ok
    assert reason == "fluff"

def test_should_save_rejects_very_short():
    ok, reason = mf.should_save("ok great sure", "chat", "terse")
    assert not ok

def test_should_save_rejects_too_short_for_type():
    # "chat" requires 12 words — this is 4 words, hits fluff/short check first
    ok, reason = mf.should_save("DNS resolves domain names.", "chat", "it_networking")
    assert not ok
    # may be "fluff" (too short + no code + no numbers) or "too_short"
    assert reason in ("fluff", "too_short (4 words)")

def test_should_save_accepts_real_it_answer():
    content = (
        "To configure a static IP on Ubuntu, edit /etc/netplan/01-netcfg.yaml "
        "and set addresses, gateway4, and nameservers under your interface. "
        "Run sudo netplan apply to activate changes."
    )
    ok, reason = mf.should_save(content, "chat", "it_networking")
    assert ok, f"Expected True, got reason={reason}"

def test_should_save_accepts_real_code():
    content = "def factorial(n):\n    if n <= 1: return 1\n    return n * factorial(n-1)"
    ok, reason = mf.should_save(content, "code", "python_dev")
    assert ok, f"Expected True, got reason={reason}"

def test_should_save_accepts_lesson():
    content = (
        "LangGraph StateGraph requires you to define nodes as functions and edges as "
        "conditional transitions. Your coordinator routes to specialist agents based on "
        "the task type extracted from user input."
    )
    ok, reason = mf.should_save(content, "lesson", "knowledge_learning")
    assert ok, f"Expected True, got reason={reason}"

def test_should_save_rejects_empty():
    ok, reason = mf.should_save("", "chat", "terse")
    assert not ok
    assert reason == "empty"

def test_should_save_rejects_whitespace_only():
    ok, reason = mf.should_save("   ", "chat", "terse")
    assert not ok


# ── should_save: generic detection ───────────────────────────────────────────

def test_should_save_rejects_generic_definition():
    # lesson requires 20 words; this content also has a generic opener — whichever triggers first
    content = (
        "Python is a high-level interpreted programming language that is easy to learn "
        "for beginners and experts alike in the field of software engineering."
    )
    ok, reason = mf.should_save(content, "lesson", "python_dev")
    assert not ok
    # "Python is a" matches generic opener pattern
    assert reason in ("generic_definition", "too_short (24 words)")

def test_should_save_accepts_personalised_content():
    # "your" marker prevents generic rejection
    content = (
        "Your FastAPI project uses async routes correctly. "
        "To improve performance, use connection pooling in your database layer "
        "and avoid synchronous calls inside async handlers."
    )
    ok, reason = mf.should_save(content, "lesson", "python_dev")
    assert ok, f"Expected True, got reason={reason}"


# ── is_duplicate ──────────────────────────────────────────────────────────────

def test_is_duplicate_false_on_empty_db(tmp_path):
    db = str(tmp_path / "mem.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT, agent_name TEXT)")
    con.commit()
    con.close()

    original = mf.DB_PATH
    mf.DB_PATH = db
    try:
        result = mf.is_duplicate("some content here for testing", "python_dev")
        assert not result
    finally:
        mf.DB_PATH = original

def test_is_duplicate_true_on_near_identical(tmp_path):
    db = str(tmp_path / "mem.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT, agent_name TEXT)")
    existing = "To configure a static IP on Ubuntu, edit netplan and set addresses gateway nameservers apply"
    con.execute("INSERT INTO memories (content, agent_name) VALUES (?, ?)", (existing, "it_networking"))
    con.commit()
    con.close()

    original = mf.DB_PATH
    mf.DB_PATH = db
    try:
        # Same content → should be flagged as duplicate
        result = mf.is_duplicate(existing, "it_networking")
        assert result
    finally:
        mf.DB_PATH = original

def test_is_duplicate_false_on_different_content(tmp_path):
    db = str(tmp_path / "mem.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, content TEXT, agent_name TEXT)")
    con.execute("INSERT INTO memories (content, agent_name) VALUES (?, ?)",
                ("Python asyncio event loop processes coroutines concurrently without threads.", "python_dev"))
    con.commit()
    con.close()

    original = mf.DB_PATH
    mf.DB_PATH = db
    try:
        result = mf.is_duplicate(
            "DNS resolution converts domain names to IP addresses via recursive queries.", "python_dev"
        )
        assert not result
    finally:
        mf.DB_PATH = original

def test_is_duplicate_handles_db_error():
    original = mf.DB_PATH
    mf.DB_PATH = "/nonexistent/path/mem.db"
    try:
        result = mf.is_duplicate("any content", "any_agent")
        assert not result   # graceful fallback on error
    finally:
        mf.DB_PATH = original


# ── word_count internal ───────────────────────────────────────────────────────

def test_word_count():
    assert mf._word_count("hello world") == 2
    assert mf._word_count("") == 0
    assert mf._word_count("one two three four") == 4


# ── minimum words per type ────────────────────────────────────────────────────

def test_minimum_words_code_type():
    # code requires 8 words — 7 should fail
    short_code = "def f(x): return x"  # 4 tokens
    ok, reason = mf.should_save(short_code, "code", "python_dev")
    assert not ok

def test_minimum_words_research_type():
    # research requires 25 words
    content = " ".join(["word"] * 24)
    ok, _ = mf.should_save(content, "research", "knowledge_learning")
    assert not ok
    content = " ".join(["word"] * 26)
    ok, _ = mf.should_save(content, "research", "knowledge_learning")
    # may still fail on generic check, but not too_short
    if not ok:
        assert "too_short" not in _
