"""
Tests for orchestration/auto_retrain.py — the learned-router retrain hook (#15).

Exercises the deterministic counting path (should_retrain_after_session) and the
single-flight trigger, without actually retraining (the heavy worker is stubbed).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import orchestration.auto_retrain as ar


def _use_tmp_state(tmp_path, monkeypatch, every="5"):
    monkeypatch.setattr(ar, "_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("LEARNED_ROUTER_RETRAIN_EVERY", every)


def test_triggers_exactly_every_n(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="5")
    fires = [ar.should_retrain_after_session() for _ in range(12)]
    # Fire on the 5th and 10th sessions only.
    assert fires == [False, False, False, False, True,
                     False, False, False, False, True,
                     False, False]


def test_counter_resets_after_trigger(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="3")
    for _ in range(3):
        ar.should_retrain_after_session()
    state = ar._load_state()
    assert state["sessions_since_retrain"] == 0
    assert state["total_sessions"] == 3


def test_disabled_when_zero(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="0")
    assert not any(ar.should_retrain_after_session() for _ in range(20))


def test_state_persists_across_calls(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="50")
    ar.should_retrain_after_session()
    ar.should_retrain_after_session()
    assert ar._load_state()["total_sessions"] == 2


def test_note_session_kicks_retrain_single_flight(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="1")
    started = []
    # Stub the worker so no real training/threads run; simulate "in progress".
    monkeypatch.setattr(ar, "_retrain_worker", lambda: started.append(1))

    def _fake_kick():
        # Mirror real single-flight semantics without a thread.
        if ar._retrain_running.is_set():
            return False
        ar._retrain_running.set()
        try:
            ar._retrain_worker()
        finally:
            ar._retrain_running.clear()
        return True

    monkeypatch.setattr(ar, "_kick_retrain", _fake_kick)
    assert ar.note_session() is True          # every=1 → fires immediately
    assert started == [1]


def test_kick_retrain_is_single_flight(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch)
    ar._retrain_running.set()                 # pretend a retrain is running
    try:
        assert ar._kick_retrain() is False    # second trigger is a no-op
    finally:
        ar._retrain_running.clear()


def test_retrain_state_reports_config(tmp_path, monkeypatch):
    _use_tmp_state(tmp_path, monkeypatch, every="7")
    ar.should_retrain_after_session()
    st = ar.retrain_state()
    assert st["retrain_every"] == 7
    assert st["retrain_in_progress"] is False
    assert st["total_sessions"] == 1
