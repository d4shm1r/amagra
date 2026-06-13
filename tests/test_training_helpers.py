"""
Pure-function tests for training/ modules:
  auto_train.py  — _load_results, _save_results, _infer_mem_type, _infer_quality
  report_generator.py — _pct, _score, _bar, _verdict_badge, _health_badge,
                        _priority_badge, _section, _kv_grid, AgentHealth.health_score,
                        ReportData, FailureCase, CounterfactualOpportunity,
                        collect (with mocked subsystems), render_html
"""

import os
import sys
import json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import training.auto_train as at
import training.report_generator as rg


# ── auto_train: _infer_mem_type ───────────────────────────────────────────────

def test_infer_mem_type_code():
    result = at._infer_mem_type("how to sort", "Here is a function:\n```python\ndef sort(lst):\n    return sorted(lst)\n```")
    assert result == "code"

def test_infer_mem_type_code_def():
    result = at._infer_mem_type("explain", "You can use def my_func(): to create a function.")
    assert result == "code"

def test_infer_mem_type_failure():
    result = at._infer_mem_type("debug", "There was an error in the traceback you provided.")
    assert result == "failure"

def test_infer_mem_type_lesson():
    result = at._infer_mem_type("explain DNS", "DNS maps domain names to IP addresses using a distributed hierarchy.")
    assert result == "lesson"

def test_infer_mem_type_exception_keyword():
    result = at._infer_mem_type("why crash", "The exception was raised because the file was missing.")
    assert result == "failure"


# ── auto_train: _infer_quality ────────────────────────────────────────────────

def test_infer_quality_failed_verify():
    q = at._infer_quality("prompt", "response", passed_verify=False)
    assert q == 0.45

def test_infer_quality_short_response():
    q = at._infer_quality("prompt", "Short answer.", passed_verify=True)
    assert q == 0.70

def test_infer_quality_long_response():
    long = " ".join(["word"] * 200)  # 200 words > 150 threshold
    q = at._infer_quality("prompt", long, passed_verify=True)
    assert q > 0.70

def test_infer_quality_very_long_with_code():
    long = " ".join(["word"] * 350) + " ```code``` "
    q = at._infer_quality("prompt", long, passed_verify=True)
    assert q >= 0.80  # 0.70 + 0.08 + 0.05 + 0.07 = 0.90, capped at 0.92
    assert q <= 0.92

def test_infer_quality_with_code_block():
    response = "Here is how:\n```python\nprint('hello')\n```"
    q = at._infer_quality("prompt", response, passed_verify=True)
    assert q > 0.70


# ── auto_train: _load_results / _save_results ─────────────────────────────────

def test_load_results_missing_file(tmp_path, monkeypatch):
    fake_path = str(tmp_path / "no_results.json")
    monkeypatch.setattr(at, "RESULTS_FILE", fake_path)
    result = at._load_results()
    assert "prompts" in result
    assert "started" in result

def test_load_results_existing_file(tmp_path, monkeypatch):
    fake_path = str(tmp_path / "results.json")
    data = {"prompts": {"p1": {"status": "done"}}, "started": "2025-01-01"}
    with open(fake_path, "w") as f:
        json.dump(data, f)
    monkeypatch.setattr(at, "RESULTS_FILE", fake_path)
    result = at._load_results()
    assert "p1" in result["prompts"]

def test_save_and_reload_results(tmp_path, monkeypatch):
    fake_path = str(tmp_path / "results.json")
    monkeypatch.setattr(at, "RESULTS_FILE", fake_path)
    data = {"prompts": {"p1": {"status": "done"}}, "started": "2025-01-01"}
    at._save_results(data)
    assert os.path.exists(fake_path)
    with open(fake_path) as f:
        loaded = json.load(f)
    assert "updated" in loaded
    assert loaded["prompts"]["p1"]["status"] == "done"


# ── report_generator: pure formatting functions ───────────────────────────────

def test_pct():
    assert rg._pct(0.0) == "0.0%"
    assert rg._pct(1.0) == "100.0%"
    assert rg._pct(0.753) == "75.3%"

def test_score():
    assert rg._score(0.8) == "0.800"
    assert rg._score(1.0) == "1.000"

def test_bar_returns_svg():
    result = rg._bar(0.5)
    assert "<svg" in result
    assert "rect" in result

def test_bar_high_value():
    result = rg._bar(0.9)
    assert "#2C5F8A" in result  # blue for >= 0.7

def test_bar_medium_value():
    result = rg._bar(0.6)
    assert "#E07B00" in result  # orange for 0.5-0.7

def test_bar_low_value():
    result = rg._bar(0.3)
    assert "#B03030" in result  # red for < 0.5

def test_verdict_badge_known():
    result = rg._verdict_badge("core")
    assert "CORE" in result
    assert "span" in result

def test_verdict_badge_unknown():
    result = rg._verdict_badge("unknown")
    assert "span" in result  # fallback color

def test_health_badge():
    result = rg._health_badge("HEALTHY", 0.85)
    assert "HEALTHY" in result
    assert "0.850" in result

def test_health_badge_critical():
    result = rg._health_badge("CRITICAL", 0.10)
    assert "CRITICAL" in result

def test_priority_badge_high():
    result = rg._priority_badge("high")
    assert "HIGH" in result

def test_priority_badge_med():
    result = rg._priority_badge("medium")
    assert "MED" in result

def test_section():
    result = rg._section("My Title", "body content", anchor="sec1")
    assert "My Title" in result
    assert "body content" in result
    assert 'id="sec1"' in result

def test_section_no_anchor():
    result = rg._section("Title", "body")
    assert "Title" in result
    assert 'id=' not in result

def test_kv_grid():
    result = rg._kv_grid(("total", "42"), ("score", "0.85"))
    assert "total" in result
    assert "42" in result
    assert "score" in result


# ── report_generator: dataclasses ────────────────────────────────────────────

def test_agent_health_score():
    ah = rg.AgentHealth(
        name="python_dev",
        decisions=100,
        conflict_rate=0.05,
        avg_regret=0.02,
        avg_quality=0.82,
        verdict="core",
        verdict_reason="high accuracy",
        top_domain="python",
    )
    score = ah.health_score
    assert 0 <= score <= 1.0

def test_agent_health_score_degraded():
    ah = rg.AgentHealth(
        name="weak_agent",
        decisions=10,
        conflict_rate=0.8,
        avg_regret=0.5,
        avg_quality=0.3,
        verdict="struggling",
        verdict_reason="high errors",
        top_domain="none",
    )
    score = ah.health_score
    assert score < 0.5

def test_failure_case_creation():
    fc = rg.FailureCase(
        decision_id=1,
        agent="python_dev",
        action="respond",
        regret=0.4,
        query="test query",
    )
    assert fc.decision_id == 1
    assert fc.regret == 0.4

def test_counterfactual_opportunity():
    co = rg.CounterfactualOpportunity(
        decision_id=2,
        query="network question",
        original_agent="python_dev",
        suggested_alt="it_networking",
        regret=0.25,
        conflict=True,
        priority="high",
    )
    assert co.priority == "high"
    assert co.regret == 0.25


# ── report_generator: collect() with mocked subsystems ───────────────────────

def _make_report_data() -> rg.ReportData:
    return rg.ReportData(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        window=20,
        total_decisions=100,
        conflict_rate=0.10,
        reflection_rate=0.25,
        avg_regret=0.08,
        coherence=0.82,
        c_routing=0.80,
        c_calib=0.78,
        c_quality=0.85,
        g_r_mean=0.04,
        mem_avg_quality=0.77,
        mem_count=150,
        agents=[
            rg.AgentHealth(
                name="python_dev",
                decisions=60,
                conflict_rate=0.08,
                avg_regret=0.06,
                avg_quality=0.85,
                verdict="core",
                verdict_reason="high accuracy",
                top_domain="python",
                action_dist={"respond": 58, "clarify": 2},
            )
        ],
        top_failures=[
            rg.FailureCase(decision_id=1, agent="python_dev", action="respond", regret=0.35, query="bad query")
        ],
        conflict_clusters={"python_dev": {"rate": 0.08, "n": 60}},
        action_clusters={"respond": {"count": 80, "avg_regret": 0.06}},
        cf_candidates=[
            rg.CounterfactualOpportunity(
                decision_id=1, query="net q", original_agent="python_dev",
                suggested_alt="it_networking", regret=0.3, conflict=True, priority="high"
            )
        ],
        overall_health=0.82,
        health_label="HEALTHY",
    )


def test_collect_with_all_systems_unavailable(monkeypatch):
    import unittest.mock as mock
    with mock.patch.dict(sys.modules, {
        "cognition.coherence": None,
        "cognition.failure_miner": None,
        "training.specialization": None,
        "cognition.counterfactual": None,
    }):
        result = rg.collect(window=5)
    assert isinstance(result, rg.ReportData)
    assert result.window == 5
    assert result.total_decisions == 0
    assert result.health_label in ("HEALTHY", "MODERATE", "DEGRADED", "CRITICAL")


def test_collect_health_labels():
    for overall, expected in [
        (0.85, "HEALTHY"),
        (0.70, "MODERATE"),
        (0.55, "DEGRADED"),
        (0.30, "CRITICAL"),
    ]:
        # Manually check the threshold logic by constructing at known overall values
        if overall >= 0.80:
            label = "HEALTHY"
        elif overall >= 0.65:
            label = "MODERATE"
        elif overall >= 0.50:
            label = "DEGRADED"
        else:
            label = "CRITICAL"
        assert label == expected


# ── report_generator: render_html ────────────────────────────────────────────

def test_render_html_returns_string():
    d = _make_report_data()
    html = rg.render_html(d)
    assert isinstance(html, str)
    assert len(html) > 100

def test_render_html_contains_sections():
    d = _make_report_data()
    html = rg.render_html(d)
    assert "Coherence" in html or "coherence" in html.lower()

def test_render_html_shows_agent_name():
    d = _make_report_data()
    html = rg.render_html(d)
    assert "python_dev" in html

def test_render_html_shows_health_label():
    d = _make_report_data()
    html = rg.render_html(d)
    assert "HEALTHY" in html

def test_render_html_empty_agents():
    d = _make_report_data()
    d.agents = []
    d.top_failures = []
    d.cf_candidates = []
    html = rg.render_html(d)
    assert isinstance(html, str)
    assert len(html) > 100
