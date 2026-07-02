"""
Unit tests for decision/weights.py — weight management and calibration.
Tests use production DB (or fallback to defaults when DB unavailable).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import decision.weights as dw


@pytest.fixture(autouse=True)
def _reset_weights_cache():
    """Tests here monkeypatch DB_PATH to a tmp DB, which warms the in-process
    cache from that tmp DB. Teardown restores DB_PATH but not the cache, so
    without this reset every weights reader in the next CACHE_TTL seconds
    (e.g. identity fingerprints) sees tmp-DB values against the real DB."""
    yield
    with dw._lock:
        dw._cache, dw._cache_ts = {}, 0.0


# ── _defaults ─────────────────────────────────────────────────────────────────

def test_defaults_returns_dict():
    d = dw._defaults()
    assert isinstance(d, dict)

def test_defaults_has_known_agents():
    d = dw._defaults()
    assert "python_dev" in d
    assert "it_networking" in d
    assert "ai_ml" in d

def test_defaults_all_one():
    d = dw._defaults()
    for v in d.values():
        assert v == 1.0


# ── load / get ────────────────────────────────────────────────────────────────

def test_load_returns_dict():
    result = dw.load()
    assert isinstance(result, dict)

def test_load_has_all_agents():
    result = dw.load()
    defaults = dw._defaults()
    for agent in defaults:
        assert agent in result

def test_get_unknown_agent():
    result = dw.get("completely_unknown_agent_xyz")
    assert result == 1.0  # fallback default

def test_get_known_agent():
    result = dw.get("python_dev")
    lo, hi = dw.BOUNDS
    assert lo <= result <= hi


# ── adjust ────────────────────────────────────────────────────────────────────

def test_adjust_positive(tmp_path, monkeypatch):
    monkeypatch.setattr(dw, "DB_PATH", str(tmp_path / "weights.db"))
    dw._cache.clear() if hasattr(dw._cache, 'clear') else None
    dw.adjust("python_dev", +0.05)
    w = dw.get("python_dev")
    lo, hi = dw.BOUNDS
    assert lo <= w <= hi

def test_adjust_negative(tmp_path, monkeypatch):
    monkeypatch.setattr(dw, "DB_PATH", str(tmp_path / "weights.db"))
    dw.adjust("python_dev", -0.05)
    w = dw.get("python_dev")
    lo, hi = dw.BOUNDS
    assert lo <= w <= hi

def test_adjust_respects_lower_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(dw, "DB_PATH", str(tmp_path / "weights.db"))
    dw.adjust("python_dev", -999.0)
    w = dw.get("python_dev")
    assert w >= dw.BOUNDS[0]

def test_adjust_respects_upper_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(dw, "DB_PATH", str(tmp_path / "weights.db"))
    dw.adjust("python_dev", +999.0)
    w = dw.get("python_dev")
    assert w <= dw.BOUNDS[1]


# ── to_confidence ─────────────────────────────────────────────────────────────

def test_to_confidence_returns_float():
    c = dw.to_confidence("python_dev")
    assert isinstance(c, float)

def test_to_confidence_range():
    c = dw.to_confidence("python_dev")
    assert 0.30 <= c <= 1.0

def test_to_confidence_unknown_agent():
    c = dw.to_confidence("unknown_xyz")
    assert 0.30 <= c <= 1.0


# ── get_calibration / get_all_calibration ────────────────────────────────────

def test_get_calibration_returns_dict():
    cal = dw.get_calibration("python_dev")
    assert isinstance(cal, dict)
    assert "count" in cal
    assert "error" in cal

def test_get_all_calibration_returns_dict():
    all_cal = dw.get_all_calibration()
    assert isinstance(all_cal, dict)


# ── reset ─────────────────────────────────────────────────────────────────────

def test_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(dw, "DB_PATH", str(tmp_path / "weights.db"))
    # Clear the in-process cache so load() reads from our tmp DB
    dw._cache.clear()
    dw._cache_ts = 0.0
    dw._init_table()
    dw.reset()
    dw._cache.clear()
    dw._cache_ts = 0.0
    result = dw.load()
    for v in result.values():
        assert abs(v - 1.0) < 0.001


# ── drift_status ──────────────────────────────────────────────────────────────

def test_drift_status_returns_dict():
    result = dw.drift_status()
    assert isinstance(result, dict)

def test_drift_status_has_healthy_key():
    result = dw.drift_status()
    assert "healthy" in result

def test_drift_status_has_flags():
    result = dw.drift_status()
    assert "flags" in result
    assert isinstance(result["flags"], list)
