"""
auto_retrain.py — retrain the learned router after every N real sessions (#15).

The learned router (orchestration/learned_router.py) is trained once on the seed
trace dataset. As real sessions accumulate its training data goes stale and the
DOMAIN→AGENT distribution it learned drifts from live behaviour. This module
keeps a small persisted counter and, every RETRAIN_EVERY real sessions, rebuilds
the trace dataset and retrains the model.

Design:
  • note_session() is called once per *real* (non-eval) session from the request
    path. It is cheap, never raises, and never blocks the response.
  • The actual retrain runs in a daemon thread, single-flight (a second trigger
    while one is running is a no-op), so request latency is unaffected.
  • Counting (should_retrain_after_session) is separated from execution so it can
    be unit-tested deterministically without spawning threads.

Config:
  LEARNED_ROUTER_RETRAIN_EVERY  — sessions between retrains (default 50; 0 = off)
"""

import os
import json
import threading

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE_PATH = os.path.join(_BASE, "logs", "auto_retrain_state.json")

_lock = threading.Lock()
_retrain_running = threading.Event()


def _retrain_every() -> int:
    try:
        return int(os.environ.get("LEARNED_ROUTER_RETRAIN_EVERY", "50"))
    except ValueError:
        return 50


def _load_state() -> dict:
    try:
        with open(_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
        tmp = _STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, _STATE_PATH)
    except Exception:
        pass


def should_retrain_after_session() -> bool:
    """
    Record one real session and report whether the retrain threshold was hit.

    Pure of side effects beyond the counter file: increments the running count,
    and on reaching the threshold resets it and returns True. Safe to call
    concurrently (guarded by _lock).
    """
    every = _retrain_every()
    if every <= 0:
        return False
    with _lock:
        state = _load_state()
        state["sessions_since_retrain"] = state.get("sessions_since_retrain", 0) + 1
        state["total_sessions"] = state.get("total_sessions", 0) + 1
        triggered = state["sessions_since_retrain"] >= every
        if triggered:
            state["sessions_since_retrain"] = 0
        _save_state(state)
    return triggered


def note_session() -> bool:
    """
    Call once per real session. Kicks a background retrain when due.

    Returns True if a retrain was started, False otherwise. Never raises.
    """
    try:
        if should_retrain_after_session():
            return _kick_retrain()
    except Exception as e:  # pragma: no cover - defensive
        print(f"[auto_retrain] note_session failed silently: {e}")
    return False


def _kick_retrain() -> bool:
    """Start the retrain thread unless one is already running (single-flight)."""
    if _retrain_running.is_set():
        return False
    _retrain_running.set()
    threading.Thread(
        target=_retrain_worker, name="learned-router-retrain", daemon=True
    ).start()
    return True


def _retrain_worker() -> None:
    try:
        from cognition.trace_builder import (
            build_traces, save_traces, dataset_stats, save_stats,
        )
        from orchestration import learned_router

        traces = build_traces()
        save_traces(traces)
        try:
            save_stats(dataset_stats(traces))
        except Exception:
            pass

        result = learned_router.train(traces, verbose=False)
        learned_router.invalidate_cache()

        with _lock:
            state = _load_state()
            state["total_retrains"] = state.get("total_retrains", 0) + 1
            state["last_retrain"] = {
                "n_samples":    result.get("n_samples"),
                "cv_accuracy":  result.get("cv_accuracy"),
                "train_accuracy": result.get("train_accuracy"),
                "error":        result.get("error"),
            }
            _save_state(state)
        print(f"[auto_retrain] learned router retrained: {result.get('n_samples')} "
              f"samples, cv={result.get('cv_accuracy')}")
    except Exception as e:
        print(f"[auto_retrain] retrain failed: {e}")
    finally:
        _retrain_running.clear()


def retrain_state() -> dict:
    """Current counter/retrain state (for the /stats API and diagnostics)."""
    state = _load_state()
    state["retrain_every"] = _retrain_every()
    state["retrain_in_progress"] = _retrain_running.is_set()
    return state
