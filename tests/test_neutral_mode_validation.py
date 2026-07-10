"""
Validation for the neutral-mode signed-drift metric (issue #74, task 5.4).

The metric (evaluation.math_metrics.neutral_mode_drift) scalarizes the per-agent
weight *vector* into a signed number by naming the slowest-contracting mode
(smallest adaptive-α ⇒ K = 1−α nearest 1) and reporting *its* signed drift.
Pooled variance is sign-blind and mode-blind; this is not.

Three layers, from always-runs to live:

  1. Contract      — synthetic α assigned independently of the drift: the call
                     must pick the min-α agent, preserve the drift sign, and set
                     regime ∈ {stabilizing, destabilizing}. Locks the behaviour
                     regardless of what the live log contains.

  2. Robustness    — the weights._neutral_mode() reconstructor must return a
                     well-formed dict on the real event log without raising,
                     even when the α field is absent (historical events predate
                     the field → benign 'flat' verdict).

  3. Live agreement — the exit criterion: the flagged neutral mode equals the
                     agent with the most volatile weight track over the last N
                     sessions. This needs the logged α (added to
                     ROUTING_WEIGHT_CHANGED as of #74) and so AUTO-ACTIVATES once
                     real α-bearing events accumulate; until then it skips with a
                     clear reason rather than passing on a fabricated proxy.

Honesty note: α in the live pipeline is a *composite* instability signal
(regret ∧ calibration ∧ weight-variance). Reconstructing a proxy α from any one
of those (e.g. calibration error alone) flags a different agent than track
volatility does, so a proxy-based "agreement" would be misleading. The live
check therefore waits for the genuine logged α.
"""

import os
import statistics as st
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.math_metrics import neutral_mode_drift
from decision.weights import _neutral_mode


# ── helpers ───────────────────────────────────────────────────────
def _real_tracks(n: int = 500):
    """Reconstruct per-agent weight tracks + latest α from the live event log.

    Returns (history, latest_alpha) where history[agent] is the chronological
    weight track. Mirrors weights._neutral_mode's reconstruction so the test
    reasons about exactly what the metric sees.
    """
    try:
        from infrastructure.event_bus import recent_events, EventType
        events = recent_events(n, EventType.ROUTING_WEIGHT_CHANGED.value)
    except Exception:
        events = []
    history: dict[str, list[float]] = {}
    latest_alpha: dict[str, float] = {}
    for ev in reversed(events):
        p = ev.get("payload", {})
        agent = p.get("agent")
        if agent is None or "weight_after" not in p:
            continue
        track = history.setdefault(agent, [])
        if not track and "weight_before" in p:
            track.append(p["weight_before"])
        track.append(p["weight_after"])
        if "alpha" in p:
            latest_alpha[agent] = p["alpha"]
    return history, latest_alpha


# ── 1. Contract (always runs) ─────────────────────────────────────
def test_picks_min_alpha_mode():
    # 'b' has the smallest α ⇒ K nearest 1 ⇒ the neutral mode
    out = neutral_mode_drift({"a": 0.14, "b": 0.03, "c": 0.10},
                             {"a": 0.20, "b": 0.08, "c": -0.30})
    assert out["agent"] == "b"
    assert abs(out["K"] - 0.97) < 1e-9          # K = 1 − 0.03


def test_sign_preserved_and_regime_matches_drift_sign():
    up = neutral_mode_drift({"b": 0.03}, {"b": 0.08})
    assert up["signed_drift"] == 0.08 and up["regime"] == "destabilizing"
    down = neutral_mode_drift({"b": 0.03}, {"b": -0.05})
    assert down["signed_drift"] == -0.05 and down["regime"] == "stabilizing"
    zero = neutral_mode_drift({"b": 0.03}, {"b": 0.0})
    assert zero["regime"] == "neutral"


def test_min_alpha_wins_even_when_another_agent_drifts_more():
    # 'a' drifts far but contracts strongly (large α); 'b' barely drifts but is
    # the slowest-contracting mode. The neutral mode is 'b' — the point of the
    # metric: it reports the mode about to lose contraction, not the loudest one.
    out = neutral_mode_drift({"a": 0.20, "b": 0.02},
                             {"a": 0.50, "b": 0.01})
    assert out["agent"] == "b" and out["signed_drift"] == 0.01


def test_disjoint_and_empty_inputs_are_flat():
    assert neutral_mode_drift({}, {})["regime"] == "flat"
    assert neutral_mode_drift({"a": 0.1}, {"b": 0.2})["agent"] is None


# ── 2. Robustness on the real log (always runs) ───────────────────
def test_reconstructor_wellformed_on_real_log():
    out = _neutral_mode()
    assert set(out) == {"agent", "K", "signed_drift", "regime"}
    assert out["regime"] in {"stabilizing", "destabilizing", "neutral", "flat"}
    # No α in historical events ⇒ benign flat; once α accumulates it lights up.
    if out["agent"] is None:
        assert out["regime"] == "flat"


# ── 3. Live agreement (auto-activating exit criterion) ────────────
def test_neutral_mode_agrees_with_most_volatile_track():
    history, latest_alpha = _real_tracks()
    tracks = {a: t for a, t in history.items() if len(t) >= 2}
    if len(tracks) < 2:
        pytest.skip("fewer than two multi-point weight tracks in the log")

    # Observed weakest mode = most volatile weight track over the window.
    volatility = {a: st.pvariance(t) for a, t in tracks.items()}
    observed = max(volatility, key=volatility.__getitem__)

    have_alpha = [a for a in tracks if a in latest_alpha]
    if len(have_alpha) < 2:
        pytest.skip(
            "logged α not yet accumulated on ≥2 tracks — live agreement check "
            f"activates once ROUTING_WEIGHT_CHANGED carries α (#74). "
            f"Observed weakest mode to match: {observed!r}"
        )

    drifts = {a: t[-1] - t[0] for a, t in tracks.items()}
    flagged = neutral_mode_drift(latest_alpha, drifts)["agent"]
    assert flagged == observed, (
        f"neutral mode {flagged!r} != most volatile track {observed!r}"
    )
