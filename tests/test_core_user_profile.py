"""
Unit tests for core/user_profile.py — no external dependencies.
Tests both "no profile" (returns "") and "with profile" (returns formatted block).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.user_profile as up


def test_no_profile_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(up, "_PROFILE_PATH", str(tmp_path / "nonexistent.json"))
    assert up.get_profile_context() == ""


def test_corrupt_profile_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "profile.json"
    p.write_text("NOT JSON {{{")
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))
    assert up.get_profile_context() == ""


def test_empty_profile_returns_empty(tmp_path, monkeypatch):
    p = tmp_path / "profile.json"
    p.write_text("{}")
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))
    result = up.get_profile_context()
    assert result == ""


def test_profile_with_standard_fields(tmp_path, monkeypatch):
    profile = {
        "name":               "Test User",
        "role":               "Software Engineer",
        "background":         "10 years Python",
        "communication_style": "Direct and concise",
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(profile))
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))

    result = up.get_profile_context()
    assert "<user_context>" in result
    assert "Name: Test User" in result
    assert "Role: Software Engineer" in result
    assert "Background: 10 years Python" in result
    assert "</user_context>" in result
    # The framing must tell the model not to echo the block (issue #4)
    assert "Never quote" in result


def test_profile_strips_comment_key(tmp_path, monkeypatch):
    profile = {
        "_comment": "This is an example file — replace with your own details",
        "name": "Real Name",
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(profile))
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))

    result = up.get_profile_context()
    assert "_comment" not in result
    assert "example" not in result
    assert "Real Name" in result


def test_profile_with_extra_keys(tmp_path, monkeypatch):
    profile = {
        "name": "Dev",
        "custom_field": "Some extra context",
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(profile))
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))

    result = up.get_profile_context()
    assert "Custom Field: Some extra context" in result


def test_profile_skips_empty_fields(tmp_path, monkeypatch):
    profile = {
        "name":       "Dev",
        "background": "",   # empty — should be skipped
        "role":       "  ", # whitespace — should be skipped
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(profile))
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))

    result = up.get_profile_context()
    assert "Background" not in result
    assert "Role" not in result
    assert "Name: Dev" in result


def test_profile_all_known_fields(tmp_path, monkeypatch):
    profile = {
        "name":               "Alice",
        "role":               "DevOps",
        "background":         "Linux admin",
        "communication_style": "Formal",
        "preferences":        "Code examples",
        "dont":               "Skip explanations",
    }
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(profile))
    monkeypatch.setattr(up, "_PROFILE_PATH", str(p))

    result = up.get_profile_context()
    for field in ["Name", "Role", "Background", "Communication style", "Preferences", "Never do"]:
        assert field in result
