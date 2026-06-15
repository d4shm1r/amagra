"""
Tests for core/language.py and the non-English profile gate (GitHub issue #6).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.language import is_probably_non_english
import core.user_profile as up


# ── detector: non-English true positives ──────────────────────────────────────

def test_albanian_flagged():
    # The reported regression case.
    assert is_probably_non_english("Si je sot, çfarë po bën me projektin tim?")

def test_cyrillic_flagged():
    assert is_probably_non_english("Привет, как у тебя дела сегодня?")

def test_cjk_flagged():
    assert is_probably_non_english("你好，今天过得怎么样？")

def test_spanish_with_diacritics_flagged():
    assert is_probably_non_english("¿Cómo está tu configuración de red?")

def test_long_latin_no_stopwords_flagged():
    # Five+ word non-English phrase with no English function words.
    assert is_probably_non_english("Bonjour comment configurer mon serveur web")


# ── detector: English true negatives (no false positives) ─────────────────────

def test_english_sentence_not_flagged():
    assert not is_probably_non_english("How do I configure my home network?")

def test_short_english_command_not_flagged():
    # Terse English commands have no stopwords but must not trip the detector.
    assert not is_probably_non_english("configure vlan trunking")
    assert not is_probably_non_english("restart nginx service")

def test_empty_not_flagged():
    assert not is_probably_non_english("")
    assert not is_probably_non_english("   ")

def test_english_with_loanword_not_flagged():
    # A stray accented word should not override clear English stopwords.
    assert not is_probably_non_english("I love this café near my house")


# ── profile gate: non-English strips profile, adds language directive ─────────

def test_profile_context_non_english_strips_profile(monkeypatch):
    monkeypatch.setattr(up, "_load_profile", lambda: {"name": "Dash", "role": "SRE"})
    ctx = up.get_profile_context("Si je sot, çfarë po bën me projektin tim?")
    assert "response_language" in ctx
    assert "Dash" not in ctx          # profile must not leak
    assert "SRE" not in ctx

def test_profile_context_english_keeps_profile(monkeypatch):
    monkeypatch.setattr(up, "_load_profile", lambda: {"name": "Dash", "role": "SRE"})
    ctx = up.get_profile_context("How do I configure my home network?")
    assert "Dash" in ctx
    assert "response_language" not in ctx

def test_profile_context_no_query_keeps_profile(monkeypatch):
    # Back-compat: callers that pass nothing behave exactly as before.
    monkeypatch.setattr(up, "_load_profile", lambda: {"name": "Dash"})
    ctx = up.get_profile_context()
    assert "Dash" in ctx

def test_profile_context_no_profile_non_english_still_directs(monkeypatch):
    monkeypatch.setattr(up, "_load_profile", lambda: None)
    ctx = up.get_profile_context("Përshëndetje, si mund të rregulloj rrjetin tim")
    assert "response_language" in ctx
