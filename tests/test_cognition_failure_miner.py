"""
Tests for cognition/failure_miner.py — print_report, save_report, mine (empty DB).
"""

import os, sys, json, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cognition.failure_miner as fm


# ── mine with empty DB ────────────────────────────────────────────────────────

def test_mine_returns_dict():
    result = fm.mine(limit=10)
    assert isinstance(result, dict)

def test_mine_structure():
    result = fm.mine(limit=10)
    assert "total_decisions" in result
    assert "summary" in result

def test_mine_summary_keys():
    result = fm.mine(limit=10)
    s = result["summary"]
    assert "conflict_rate" in s
    assert "reflection_rate" in s
    assert "avg_regret" in s

def test_mine_no_decisions():
    result = fm.mine(limit=0)
    assert isinstance(result, dict)
    assert result.get("total_decisions", 0) == 0


# ── print_report ──────────────────────────────────────────────────────────────

def test_print_report_error_dict(capsys):
    fm.print_report({"error": "database unavailable"})
    captured = capsys.readouterr()
    assert "database unavailable" in captured.out

def test_print_report_full(capsys):
    report = {
        "generated": "2025-01-01T00:00:00",
        "total_decisions": 50,
        "summary": {
            "conflict_rate": 0.10,
            "total_conflicts": 5,
            "reflection_rate": 0.20,
            "total_reflected": 10,
            "high_regret_count": 3,
            "avg_regret": 0.15,
            "avg_latency_ms": 250,
            "feedback_total": 8,
            "feedback_negative": 2,
        },
        "regret_by_agent": {
            "python_dev": {"count": 3, "avg_regret": 0.3, "pct_of_total": 6.0}
        },
        "conflict_by_agent": {
            "it_networking": {"conflict_rate": 0.15, "conflicts": 2, "total": 13}
        },
        "regret_by_action": {
            "build": {"count": 2, "avg_regret": 0.4}
        },
        "feedback_by_agent": {
            "python_dev": {"positive": 5, "negative": 1, "approval_rate": 0.83}
        },
        "top_failures": [
            {"id": 1, "agent": "python_dev", "regret": 0.5, "task": "deploy app"}
        ],
        "top_failure_tasks": [],
        "action_clusters": {},
    }
    fm.print_report(report)
    captured = capsys.readouterr()
    assert "50 decisions" in captured.out
    assert "python_dev" in captured.out

def test_print_report_empty_sections(capsys):
    report = {
        "generated": "2025-01-01T00:00:00",
        "total_decisions": 0,
        "summary": {
            "conflict_rate": 0.0,
            "total_conflicts": 0,
            "reflection_rate": 0.0,
            "total_reflected": 0,
            "high_regret_count": 0,
            "avg_regret": 0.0,
            "avg_latency_ms": 0,
            "feedback_total": 0,
            "feedback_negative": 0,
        },
        "regret_by_agent": {},
        "conflict_by_agent": {},
        "regret_by_action": {},
        "feedback_by_agent": {},
        "top_failures": [],
        "top_failure_tasks": [],
        "action_clusters": {},
    }
    fm.print_report(report)
    captured = capsys.readouterr()
    assert "0 decisions" in captured.out


# ── save_report ───────────────────────────────────────────────────────────────

def test_save_report(tmp_path, monkeypatch):
    monkeypatch.setattr(fm, "_REPORT_PATH", str(tmp_path / "report.json"))
    report = {"generated": "now", "total_decisions": 5, "summary": {}}
    path = fm.save_report(report)
    assert os.path.exists(path)
    with open(path) as f:
        loaded = json.load(f)
    assert loaded["total_decisions"] == 5
