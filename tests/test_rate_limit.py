"""
Unit tests for the in-memory per-minute rate limiter and its eviction (#194).

Exercises `api._check_minute_limit` directly with an injected `window` dict and a
controlled `now`, so no TestClient, Ollama, or clock is needed. The eviction
tests are the point of #194: the window dict must stay bounded to the active
working set instead of growing one entry per key for the life of the process.

Run: python3 -m pytest tests/test_rate_limit.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api  # noqa: E402
from api import _check_minute_limit  # noqa: E402


def _no_sweep(now: float) -> None:
    """Push the last-sweep clock to `now` so a call at `now` won't sweep."""
    api._last_rl_sweep = now


def _force_sweep_next() -> None:
    """Reset the last-sweep clock so the next call triggers a sweep."""
    api._last_rl_sweep = 0.0


def test_allows_up_to_limit_then_blocks():
    win: dict[int, tuple[int, float]] = {}
    now = 1000.0
    _no_sweep(now)
    # limit=3 → first three allowed, fourth blocked, all within one window.
    assert _check_minute_limit(1, 3, now, win) is True   # count 1
    assert _check_minute_limit(1, 3, now, win) is True   # count 2
    assert _check_minute_limit(1, 3, now, win) is True   # count 3
    assert _check_minute_limit(1, 3, now, win) is False  # count 4 > 3


def test_window_resets_after_60s():
    win: dict[int, tuple[int, float]] = {}
    now = 1000.0
    _no_sweep(now)
    assert _check_minute_limit(1, 1, now, win) is True    # count 1
    assert _check_minute_limit(1, 1, now, win) is False   # count 2 > 1
    # 60s later the fixed window rolls over and the counter restarts.
    later = now + 61
    _no_sweep(later)
    assert _check_minute_limit(1, 1, later, win) is True   # count 1 again


def test_distinct_keys_are_independent():
    win: dict[int, tuple[int, float]] = {}
    now = 1000.0
    _no_sweep(now)
    assert _check_minute_limit(1, 1, now, win) is True
    assert _check_minute_limit(2, 1, now, win) is True   # different key, own window
    assert _check_minute_limit(1, 1, now, win) is False  # key 1 already spent


def test_eviction_bounds_the_dict():
    # 500 keys touched at t=1000, none touched since → all stale by t=1100.
    win: dict[int, tuple[int, float]] = {k: (1, 1000.0) for k in range(500)}
    assert len(win) == 500

    later = 1100.0            # >60s after every existing window_start
    _force_sweep_next()
    # A single new request at `later` triggers the periodic sweep.
    assert _check_minute_limit(9999, 10, later, win) is True

    # Every stale key is gone; only the just-touched key survives.
    assert win == {9999: (1, later)}


def test_active_key_survives_its_own_sweep():
    # Mix of stale (old) and active (recent) keys; a sweep must keep the active
    # ones and the key being touched, drop only the fully-elapsed windows.
    now = 2000.0
    win: dict[int, tuple[int, float]] = {
        1: (1, 1000.0),   # stale (1000s old)
        2: (3, now - 10),  # active (10s into its window)
    }
    _force_sweep_next()
    assert _check_minute_limit(3, 10, now, win) is True

    assert 1 not in win          # stale evicted
    assert win[2] == (3, now - 10)  # active untouched
    assert win[3] == (1, now)       # touched key present
