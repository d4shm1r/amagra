# ~/agentic-ai/decision_weights.py
# ─────────────────────────────────────────────────────────────
# Per-agent weight store with bounded EMA learning and calibration.
#
# Two tables in decisions.db:
#   agent_weights      — current weight per agent [0.1, 3.0]
#   agent_calibration  — rolling avg of (confidence, reflection_score)
#
# Weight semantics:
#   high weight → agent consistently chosen & performs well
#   low weight  → domain is ambiguous or agent underperforms
#
# Update rules:
#   adjust(agent, delta) — raw delta for conflict/decay signals
#   update_ema(agent, score) — bounded EMA for reflection signals
#     delta = clamp(0.05 * (score - current), -0.02, +0.02)
#
# Calibration:
#   update_calibration(agent, confidence, reflection_score)
#   to_confidence() applies calibration correction when sample_count >= 5:
#     calibrated = raw - 0.2 * (avg_confidence - avg_reflection)
# ─────────────────────────────────────────────────────────────

import os
import time
import sqlite3
import threading

from infrastructure.db import path as _dbpath
DB_PATH = _dbpath("decisions")
BOUNDS  = (0.1, 3.0)

KNOWN_AGENTS = [
    "it_networking", "python_dev", "dotnet_dev",
    "ai_ml", "knowledge_learning", "terse",
]

_lock     = threading.Lock()
_cache:    dict  = {}
_cache_ts: float = 0.0
CACHE_TTL = 5.0


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL;")
    return c


def _init_table():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = _conn()

    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_weights (
            agent   TEXT PRIMARY KEY,
            weight  REAL NOT NULL DEFAULT 1.0,
            updated TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_calibration (
            agent          TEXT PRIMARY KEY,
            avg_confidence REAL NOT NULL DEFAULT 0.67,
            avg_reflection REAL NOT NULL DEFAULT 0.75,
            sample_count   INTEGER NOT NULL DEFAULT 0,
            updated        TEXT
        )
    """)

    # Raw (confidence, performance) pairs — one row per learning update.
    # The agent_calibration table above collapses these into a per-agent EMA;
    # this table keeps the raw points so the confidence→P(correct) reliability
    # curve can be measured (see evaluation/calibration_report.py). Append-only.
    c.execute("""
        CREATE TABLE IF NOT EXISTS calibration_samples (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,
            confidence  REAL NOT NULL,
            performance REAL NOT NULL,
            ts          TEXT NOT NULL
        )
    """)
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_calsamples_conf "
        "ON calibration_samples (confidence)"
    )

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    for a in KNOWN_AGENTS:
        c.execute(
            "INSERT OR IGNORE INTO agent_weights (agent, weight, updated) VALUES (?, 1.0, ?)",
            (a, ts)
        )
        c.execute(
            "INSERT OR IGNORE INTO agent_calibration "
            "(agent, avg_confidence, avg_reflection, sample_count) VALUES (?, 0.67, 0.75, 0)",
            (a,)
        )
    c.commit()
    c.close()


def _defaults() -> dict:
    return {a: 1.0 for a in KNOWN_AGENTS}


# ── Weight load/get ───────────────────────────────────────────

def load() -> dict:
    """Load all weights. Uses 5s in-process cache."""
    global _cache, _cache_ts
    now = time.time()
    with _lock:
        if _cache and (now - _cache_ts) < CACHE_TTL:
            return dict(_cache)
        try:
            c = _conn()
            rows = c.execute("SELECT agent, weight FROM agent_weights").fetchall()
            c.close()
            base = _defaults()
            base.update({a: w for a, w in rows if a in base})
            _cache, _cache_ts = base, now
            return dict(base)
        except Exception as e:
            print(f"[weights] load error: {e}")
            return _defaults()


def get(agent: str) -> float:
    """Return weight for a single agent. Default 1.0."""
    return load().get(agent, 1.0)


# ── Weight update ─────────────────────────────────────────────

def adjust(agent: str, delta: float) -> None:
    """Raw delta update — used for conflict signals and decay."""
    global _cache, _cache_ts
    from datetime import datetime, timezone
    with _lock:
        try:
            c = _conn()
            row = c.execute(
                "SELECT weight FROM agent_weights WHERE agent=?", (agent,)
            ).fetchone()
            current = row[0] if row else 1.0
            lo, hi  = BOUNDS
            new_w   = round(max(lo, min(hi, current + delta)), 4)
            ts      = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT OR REPLACE INTO agent_weights (agent, weight, updated) VALUES (?, ?, ?)",
                (agent, new_w, ts)
            )
            c.commit()
            c.close()
            if _cache:
                _cache[agent] = new_w
        except Exception as e:
            print(f"[weights] adjust error: {e}")


def update_ema(agent: str, reflection_score: float) -> None:
    """
    DEPRECATED — direct callers should use learning.apply_learning_update() instead.
    Kept for tests and diagnostic tooling that need a standalone weight update.
    The production path no longer calls this directly.
    """
    global _cache, _cache_ts
    from datetime import datetime, timezone

    # --- drift check before acquiring lock ---
    cal            = get_calibration(agent)
    cal_error      = abs(cal["error"]) if cal["count"] >= 5 else 0.0
    BASE_ALPHA     = 0.05
    alpha          = BASE_ALPHA * max(0.1, 1.0 - cal_error)

    try:
        from decision.log import regret_mean as _regret_mean
        r_mean = _regret_mean(50)
    except Exception:
        r_mean = 0.0

    if r_mean > 0.4 and cal_error > 0.3:
        print(
            f"[weights] {agent}: update frozen "
            f"(regret={r_mean:.2f} cal_err={cal_error:.2f})"
        )
        return

    with _lock:
        try:
            c = _conn()
            row = c.execute(
                "SELECT weight FROM agent_weights WHERE agent=?", (agent,)
            ).fetchone()
            current       = row[0] if row else 1.0
            lo, hi        = BOUNDS
            raw_delta     = alpha * (reflection_score - current)
            bounded_delta = max(-0.02, min(0.02, raw_delta))
            new_w         = round(max(lo, min(hi, current + bounded_delta)), 4)
            ts            = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT OR REPLACE INTO agent_weights (agent, weight, updated) VALUES (?, ?, ?)",
                (agent, new_w, ts)
            )
            c.commit()
            c.close()
            if _cache:
                _cache[agent] = new_w
        except Exception as e:
            print(f"[weights] update_ema error: {e}")


def reset() -> None:
    """Reset all weights to 1.0. Used for testing or drift recovery."""
    global _cache, _cache_ts
    from datetime import datetime, timezone
    with _lock:
        try:
            ts = datetime.now(timezone.utc).isoformat()
            c  = _conn()
            for a in KNOWN_AGENTS:
                c.execute(
                    "INSERT OR REPLACE INTO agent_weights (agent, weight, updated) VALUES (?, 1.0, ?)",
                    (a, ts)
                )
            c.commit()
            c.close()
            _cache, _cache_ts = _defaults(), time.time()
        except Exception as e:
            print(f"[weights] reset error: {e}")


# ── Calibration ───────────────────────────────────────────────

def update_calibration(agent: str, confidence: float, reflection_score: float) -> None:
    """
    Update rolling calibration stats using EMA (alpha=0.1).
    Called after reflection runs so confidence vs reality can be tracked.
    """
    from datetime import datetime, timezone
    ALPHA = 0.1
    with _lock:
        try:
            c = _conn()
            row = c.execute(
                "SELECT avg_confidence, avg_reflection, sample_count "
                "FROM agent_calibration WHERE agent=?",
                (agent,)
            ).fetchone()
            if row and row[2] > 0:
                avg_conf, avg_refl, count = row
                new_avg_conf = round((1 - ALPHA) * avg_conf + ALPHA * confidence, 4)
                new_avg_refl = round((1 - ALPHA) * avg_refl + ALPHA * reflection_score, 4)
                new_count    = count + 1
            else:
                new_avg_conf = round(float(confidence),        4)
                new_avg_refl = round(float(reflection_score),  4)
                new_count    = 1
            ts = datetime.now(timezone.utc).isoformat()
            c.execute(
                """INSERT OR REPLACE INTO agent_calibration
                   (agent, avg_confidence, avg_reflection, sample_count, updated)
                   VALUES (?, ?, ?, ?, ?)""",
                (agent, new_avg_conf, new_avg_refl, new_count, ts)
            )
            # Persist the raw pair (the EMA above throws it away). Same
            # transaction so the sample log can never diverge from the EMA.
            c.execute(
                "INSERT INTO calibration_samples "
                "(agent, confidence, performance, ts) VALUES (?, ?, ?, ?)",
                (agent, round(float(confidence), 4),
                 round(float(reflection_score), 4), ts)
            )
            c.commit()
            c.close()
        except Exception as e:
            print(f"[weights] calibration error: {e}")


def get_calibration(agent: str) -> dict:
    """Return calibration stats. {avg_confidence, avg_reflection, count, error}"""
    try:
        c = _conn()
        row = c.execute(
            "SELECT avg_confidence, avg_reflection, sample_count "
            "FROM agent_calibration WHERE agent=?",
            (agent,)
        ).fetchone()
        c.close()
        if row:
            return {
                "avg_confidence": row[0],
                "avg_reflection": row[1],
                "count":          row[2],
                "error":          round(row[0] - row[1], 4),
            }
    except Exception:
        pass
    return {"avg_confidence": 0.67, "avg_reflection": 0.75, "count": 0, "error": -0.08}


def get_calibration_samples(agent: str | None = None,
                            limit: int | None = None) -> list[dict]:
    """Return raw (confidence, performance) calibration pairs, newest first.

    These are the points the per-agent EMA is computed from — the dataset for
    the reliability diagram (evaluation/calibration_report.py). Optionally
    filter by agent and/or cap the number of rows.
    """
    rows: list[dict] = []
    try:
        c = _conn()
        sql = ("SELECT agent, confidence, performance, ts "
               "FROM calibration_samples")
        params: list = []
        if agent:
            sql += " WHERE agent=?"
            params.append(agent)
        sql += " ORDER BY id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        for a, conf, perf, ts in c.execute(sql, params).fetchall():
            rows.append({"agent": a, "confidence": conf,
                         "performance": perf, "ts": ts})
        c.close()
    except Exception as e:
        print(f"[weights] sample read error: {e}")
    return rows


def get_all_calibration() -> dict:
    """Return calibration stats for all agents. Used by /metrics."""
    result = {}
    try:
        c = _conn()
        rows = c.execute(
            "SELECT agent, avg_confidence, avg_reflection, sample_count "
            "FROM agent_calibration"
        ).fetchall()
        c.close()
        for agent, avg_conf, avg_refl, count in rows:
            result[agent] = {
                "avg_confidence": avg_conf,
                "avg_reflection": avg_refl,
                "count":          count,
                "error":          round(avg_conf - avg_refl, 4),
            }
    except Exception:
        pass
    return result


# ── Confidence (with calibration) ────────────────────────────

def to_confidence(agent: str) -> float:
    """
    Convert weight → calibrated confidence on [0.30, 1.00].

    Base: w / 1.35 (default w=1.0 → 0.74, up from 0.67 with divisor 1.5)

    Calibration (applied when sample_count >= 5):
      error      = avg_confidence - avg_reflection
      calibrated = raw - 0.15 * error  (factor reduced from 0.2 to soften
                   the correction for local models whose reflection scores
                   are systematically lower than routing confidence)

    If the brain has been systematically overconfident (error > 0),
    the calibrated score is lower. Underconfident → higher.
    """
    w   = get(agent)
    raw = round(min(1.0, max(0.30, w / 1.35)), 2)
    cal = get_calibration(agent)
    if cal["count"] >= 5:
        correction = round(0.15 * cal["error"], 3)
        calibrated = max(0.30, min(1.0, raw - correction))
        return round(calibrated, 2)
    return raw


# ── Drift detection ──────────────────────────────────────────

def drift_status() -> dict:
    """
    Evaluate current system health across three drift dimensions:

      calibration_drift   — |avg_confidence - avg_reflection| > 0.25
        brain's self-assessment diverging from actual output quality

      regret_explosion    — regret_mean(50) > 0.30
        brain is consistently routing to suboptimal agents

      weight_volatility   — variance(weights) > 0.05
        agent weights are spreading far from neutral

      drift_runaway       — signed lens of stability (math_metrics.drift_status_v2)
        a per-agent weight track that is BOTH diverging from its start AND
        accelerating away (no recovery guarantee). Variance is sign-blind — it
        cannot tell convergence-to-a-new-config from divergence — so this signed
        test is the verdict of record; the variance number is kept for back-compat.

    Returns {"healthy": bool, "flags": list, ...} for dashboard + freeze decisions.
    """
    try:
        from decision.log import regret_mean as _regret_mean
        r_mean = _regret_mean(50)
    except Exception:
        r_mean = 0.0

    cal_all  = get_all_calibration()
    weights  = load()

    # Per-agent calibration error (only for agents with ≥ 5 samples)
    cal_errors = {
        a: abs(c["error"])
        for a, c in cal_all.items()
        if c["count"] >= 5
    }

    # Weight variance across all agents
    vals     = list(weights.values())
    wt_mean  = sum(vals) / len(vals) if vals else 1.0
    variance = round(sum((v - wt_mean) ** 2 for v in vals) / len(vals), 5) if vals else 0.0

    flags = []
    for a, err in cal_errors.items():
        if err > 0.25:
            flags.append({
                "type":   "calibration_drift",
                "agent":  a,
                "error":  round(err, 3),
                "detail": f"{a} confidence deviates from reflection by {err:.2f}",
            })
    if r_mean > 0.30:
        flags.append({
            "type":   "regret_explosion",
            "value":  r_mean,
            "detail": f"mean routing regret {r_mean:.3f} — brain may be consistently wrong",
        })
    if variance > 0.05:
        flags.append({
            "type":     "weight_volatility",
            "value":    variance,
            "detail":   f"weight variance {variance:.5f} — agents diverging from neutral",
        })

    # Signed lens of stability: reconstruct per-agent weight tracks from the
    # event log and ask the theorem-backed question (diverging AND accelerating
    # away?) rather than a sign-blind variance cutoff.
    drift = _signed_drift_status()
    if drift["status"] == "runaway":
        flags.append({
            "type":   "drift_runaway",
            "agent":  drift["agent"],
            "value":  drift["signed_accel"],
            "detail": (f"{drift['agent']} weight diverging and accelerating away "
                       f"— {drift['regime']}"),
        })

    return {
        "healthy":            len(flags) == 0,
        "flags":              flags,
        "regret_mean_50":     r_mean,
        "weight_variance":    variance,
        "drift_status":       drift["status"],
        "drift_regime":       drift["regime"],
        "drift_agent":        drift["agent"],
        "calibration_errors": {a: round(e, 3) for a, e in cal_errors.items()},
        "weights":            weights,
    }


def _signed_drift_status(n: int = 200) -> dict:
    """Reconstruct per-agent weight tracks from the event log and run the signed
    lens-of-stability test (math_metrics.drift_status_v2).

    Best-effort: if the event log is unavailable or empty, returns the benign
    'self_correcting' verdict so callers always get a well-formed dict.
    """
    from infrastructure.math_metrics import drift_status_v2
    try:
        from infrastructure.event_bus import recent_events, EventType
        events = recent_events(n, EventType.ROUTING_WEIGHT_CHANGED.value)
    except Exception:
        events = []

    # recent_events is newest-first; rebuild each agent's track chronologically.
    history: dict[str, list[float]] = {}
    for ev in reversed(events):
        p = ev.get("payload", {})
        agent = p.get("agent")
        if agent is None or "weight_after" not in p:
            continue
        track = history.setdefault(agent, [])
        if not track and "weight_before" in p:
            track.append(p["weight_before"])   # seed the track's starting point
        track.append(p["weight_after"])

    return drift_status_v2(history)


def _neutral_mode(n: int = 200) -> dict:
    """Reconstruct per-agent (α, drift) from the event log and report the
    signed drift of the slowest-contracting mode (math_metrics.neutral_mode_drift).

    ``drift`` is each agent's weight track end-to-start delta (same reconstruction
    as ``_signed_drift_status``); ``α`` is the *latest* adaptive-α seen for that
    agent (the current contraction modulus, K = 1−α). Pooled variance is
    sign-blind and mode-blind — this names the one agent mode nearest the
    contraction boundary and reports its signed drift.

    Best-effort: an unavailable/empty log or a payload predating the α field
    yields the benign 'flat' verdict so callers always get a well-formed dict.
    """
    from infrastructure.math_metrics import neutral_mode_drift
    try:
        from infrastructure.event_bus import recent_events, EventType
        events = recent_events(n, EventType.ROUTING_WEIGHT_CHANGED.value)
    except Exception:
        events = []

    # recent_events is newest-first; rebuild each agent's track chronologically.
    history: dict[str, list[float]] = {}
    latest_alpha: dict[str, float] = {}
    for ev in reversed(events):
        p = ev.get("payload", {})
        agent = p.get("agent")
        if agent is None or "weight_after" not in p:
            continue
        track = history.setdefault(agent, [])
        if not track and "weight_before" in p:
            track.append(p["weight_before"])   # seed the track's starting point
        track.append(p["weight_after"])
        if "alpha" in p:
            latest_alpha[agent] = p["alpha"]   # newest wins (reversed → chrono)

    drifts = {a: t[-1] - t[0] for a, t in history.items() if len(t) >= 2}
    return neutral_mode_drift(latest_alpha, drifts)


# Auto-init on import
_init_table()
