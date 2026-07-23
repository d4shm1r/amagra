# ~/agentic-ai/coherence.py
# ─────────────────────────────────────────────────────────────
# Coherence functional C(t) for the adaptive agent system.
#
# Coherence measures whether the system's behaviour is
# consistent, well-calibrated, and self-improving.
#
# Formal definition:
#
#   C(t) = (1/3) [ C_routing(t) + C_calib(t) + C_quality(t) ]
#
# Components:
#
#   C_routing(t) = mean routing confidence(t)
#       → routing is coherent when queries map decisively to a domain.
#         (Was `1 - conflict_rate`, but issue #20 removed the keyword router,
#         so `conflict` is now structurally 0 and that axis was pinned at 1.0 —
#         a dead component silently inflating C. Rebased onto the brain's own
#         confidence, a live post-#20 signal. See OPEN_PROBLEMS O7 for the wider
#         set of consumers still reading the dead `conflict` column.)
#
#   C_calib(t) = 1 - mean|ε_cal(a, t)| over agents
#       → calibration coherence: confidence tracks actual quality
#
#   C_quality(t) = mean(quality) for recent responses
#       → response quality coherence: reflected + proxy scores
#
# Empirical claims:
#   (1) E[C(t+1) | reflect=True]  > E[C(t) | reflect=False]
#   (2) C(t) is non-decreasing as high-quality memory accumulates
#   (3) err(R∘N) < err(R') implies higher routing coherence
#
# Usage:
#   python3 coherence.py                 # live state + time series
#   python3 coherence.py --json          # JSON output
#   python3 coherence.py --dynamics      # full time-series table
#   python3 coherence.py --reflection    # reflection gain analysis
# ─────────────────────────────────────────────────────────────

import sys
import os
import json
import sqlite3
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.db import path as _dbpath
from infrastructure.math_metrics import (
    series_curvature, max_abs_curvature, curvature_leading_indicator,
)
_DECISIONS_DB = _dbpath("decisions")
_MEMORY_DB    = _dbpath("memory")

AGENTS = ["it_networking", "python_dev", "dotnet_dev",
          "ai_ml", "knowledge_learning", "terse"]

# Proxy performance signals for non-reflected decisions
_PROXY_NO_CONFLICT = 0.75
_PROXY_CONFLICT    = 0.55

WINDOW = 20   # rolling window size for time-series analysis


# ── Data structures ───────────────────────────────────────────

@dataclass
class CoherenceState:
    """
    C(t) decomposed into three components and a composite score.
    All values in [0, 1].
    """
    t:            int     = 0
    window:       int     = WINDOW

    c_routing:    float = 0.0   # mean routing confidence (O7: was 1 - conflict_rate)
    c_calib:      float = 0.0   # 1 - mean|calibration_error|
    c_quality:    float = 0.0   # mean response quality
    C:            float = 0.0   # composite (1/3 sum)

    conflict_rate:       float = 0.0   # actual brain-vs-router conflicts (≡0 post-#20, see O7)
    low_confidence_rate: float = 0.0   # fraction of routes below the decisiveness floor
    reflection_rate: float = 0.0
    mean_regret:     float = 0.0
    n_decisions:     int   = 0

    # Reflection gain data (when available)
    G_r_mean:     float = 0.0   # mean(s_final - s_initial)
    G_r_std:      float = 0.0
    G_r_n:        int   = 0
    G_r_positive: float = 0.0   # fraction where G_r > 0

    # Memory quality
    mem_avg_quality: float = 0.0
    mem_n:           int   = 0


# ── Data loading ──────────────────────────────────────────────

def _load_decisions(limit: int = 500) -> list[dict]:
    if not os.path.exists(_DECISIONS_DB):
        return []
    conn = sqlite3.connect(_DECISIONS_DB, timeout=10)
    try:
        rows = conn.execute(
            "SELECT id, timestamp, final_agent, conflict, reflect, regret, "
            "COALESCE(confidence, 0.67) "
            "FROM brain_decisions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "timestamp": r[1], "agent": r[2],
         "conflict": bool(r[3]), "reflect": bool(r[4]),
         "regret": float(r[5] or 0.0), "confidence": float(r[6] if r[6] is not None else 0.67)}
        for r in rows
    ]


def _load_calibration() -> dict[str, float]:
    """Returns {agent: calibration_bias} from the decisions DB."""
    try:
        from decision.weights import get_calibration
        result = {}
        for a in AGENTS:
            cal = get_calibration(a)
            if cal and cal.get("sample_count", 0) >= 5:
                result[a] = abs(float(cal.get("bias", 0.0)))
            else:
                result[a] = 0.0
        return result
    except Exception:
        return {a: 0.0 for a in AGENTS}


def _load_reflection_gains() -> list[float]:
    """Returns list of G_r = score_final - score_initial from reflection memories."""
    if not os.path.exists(_MEMORY_DB):
        return []
    conn = sqlite3.connect(_MEMORY_DB, timeout=10)
    try:
        rows = conn.execute(
            "SELECT metadata FROM memories WHERE mem_type='reflection'"
        ).fetchall()
    finally:
        conn.close()
    gains = []
    for (meta_raw,) in rows:
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
            s_i = meta.get("score_initial")
            s_f = meta.get("score_final")
            if s_i is not None and s_f is not None:
                gains.append(float(s_f) - float(s_i))
        except Exception:
            pass
    return gains


def _load_memory_quality() -> tuple[float, int]:
    """Returns (avg_quality, n) over all memories."""
    if not os.path.exists(_MEMORY_DB):
        return 0.0, 0
    conn = sqlite3.connect(_MEMORY_DB, timeout=10)
    try:
        row = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM memories WHERE quality IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()
    if row and row[0] is not None:
        return float(row[0]), int(row[1])
    return 0.0, 0


# ── Component computation ─────────────────────────────────────

# Below this confidence a route is "indecisive" — the query didn't map cleanly
# to one domain (e.g. a single keyword scores ~0.33; the brain's default is 0.67).
_DECISIVE_CONF = 0.5


def _c_routing(decisions: list[dict]) -> tuple[float, float]:
    """
    C_routing = mean routing confidence over the window.
    Returns (c_routing, low_confidence_rate).

    Rebased in O7 (metric-owner decision). The old definition was
    `1 - conflict_rate`, where conflict = "brain overrode the keyword router" —
    but issue #20 removed that router, so `coordinator.py` writes `conflict = 0`
    unconditionally and the axis was pinned at 1.0, a dead component inflating the
    composite C. Confidence is the live post-#20 analogue: high confidence means
    the query mapped decisively to a domain (coherent routing); a run of low-
    confidence routes is the real incoherence signal. `low_confidence_rate` is the
    fraction below `_DECISIVE_CONF`, reported as a diagnostic (it is *not* the same
    as the — now always-zero — `conflict_rate`, which is reported separately).
    """
    if not decisions:
        return 0.5, 0.5
    confs = [float(d.get("confidence", 0.67)) for d in decisions]
    mean_conf = sum(confs) / len(confs)
    low_rate  = sum(1 for c in confs if c < _DECISIVE_CONF) / len(confs)
    return round(min(1.0, max(0.0, mean_conf)), 4), round(low_rate, 4)


def _c_calib(cal_errors: dict[str, float]) -> float:
    """
    C_calib = 1 - mean(|calibration_bias| per agent).
    Perfect calibration (bias=0 for all agents) → C_calib = 1.0.
    """
    if not cal_errors:
        return 1.0
    mean_err = sum(cal_errors.values()) / len(cal_errors)
    return round(1.0 - min(1.0, mean_err), 4)


def _c_quality(decisions: list[dict], mem_q: float = 0.0, mem_n: int = 0) -> float:
    """
    C_quality = independently-graded response/memory quality.

    Primary source: mean memory quality (graded by the Bayesian quality_update
    path), which is independent of routing conflict. The previous conflict-derived
    proxy (0.75 if no conflict else 0.55) made C_quality a deterministic affine
    function of conflict_rate — hence perfectly correlated with C_routing
    (= 1 − conflict_rate), so the composite C had only 2 effective degrees of
    freedom, not 3. Using graded memory quality restores a genuine third axis.

    Falls back to the conflict proxy only at cold start (no graded memory yet).
    """
    if mem_n > 0:
        return round(mem_q, 4)
    if not decisions:
        return 0.75
    scores = [
        _PROXY_NO_CONFLICT if not d["conflict"] else _PROXY_CONFLICT
        for d in decisions
    ]
    return round(sum(scores) / len(scores), 4)


# ── Reflection gain analysis ──────────────────────────────────

def reflection_gain_analysis() -> dict:
    """
    Empirical test: E[G_r | reflect=True] > 0.
    G_r = score_final - score_initial from reflection loop.
    """
    gains = _load_reflection_gains()
    if not gains:
        return {"n": 0, "mean": 0.0, "std": 0.0, "positive_frac": 0.0}
    n = len(gains)
    mean_g = sum(gains) / n
    std_g  = (sum((g - mean_g)**2 for g in gains) / n) ** 0.5
    pos    = sum(1 for g in gains if g > 0.0) / n
    return {
        "n":             n,
        "mean":          round(mean_g, 4),
        "std":           round(std_g, 4),
        "positive_frac": round(pos, 3),
        "max":           round(max(gains), 3),
        "min":           round(min(gains), 3),
    }


# ── Memory coherence over time ────────────────────────────────

def memory_coherence_history() -> list[dict]:
    """
    Memory coherence: average quality of memories by type over time.
    Shows C_memory is non-decreasing as quality gates prune bad memories.
    """
    if not os.path.exists(_MEMORY_DB):
        return []
    conn = sqlite3.connect(_MEMORY_DB, timeout=10)
    try:
        rows = conn.execute(
            "SELECT mem_type, COUNT(*), AVG(quality), "
            "SUM(CASE WHEN quality >= 0.70 THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN quality <  0.55 THEN 1 ELSE 0 END) "
            "FROM memories GROUP BY mem_type ORDER BY COUNT(*) DESC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "type":         r[0],
            "count":        r[1],
            "avg_quality":  round(float(r[2] or 0.0), 3),
            "high_quality": r[3],
            "low_quality":  r[4],
            "c_memory":     round(float(r[2] or 0.0), 3),
        }
        for r in rows
    ]


# ── Coherence time series ─────────────────────────────────────

def coherence_time_series(window: int = WINDOW) -> list[dict]:
    """
    Compute C(t) over rolling windows of decisions.
    Returns list of {window_end_id, C, c_routing, c_calib, c_quality, ...}
    """
    decisions = _load_decisions(500)
    if not decisions:
        return []

    decisions = list(reversed(decisions))  # chronological order
    cal_errors = _load_calibration()
    mem_q, mem_n = _load_memory_quality()  # system-level, independent of routing

    series = []
    step = max(1, window // 2)  # 50% overlap between windows

    for start in range(0, len(decisions) - window + 1, step):
        window_slice = decisions[start : start + window]
        cr, low_conf_rate = _c_routing(window_slice)
        cc = _c_calib(cal_errors)  # calibration is system-level, not window-specific
        cq = _c_quality(window_slice, mem_q, mem_n)
        composite = round((cr + cc + cq) / 3, 4)

        series.append({
            "window_idx":     start // step,
            "decision_range": f"{window_slice[0]['id']}–{window_slice[-1]['id']}",
            "n":              len(window_slice),
            "c_routing":      cr,
            "c_calib":        cc,
            "c_quality":      cq,
            "C":              composite,
            "conflict_rate":  round(sum(1 for d in window_slice if d["conflict"]) / len(window_slice), 4),
            "low_confidence_rate": low_conf_rate,
            "reflect_rate":   round(sum(1 for d in window_slice if d["reflect"]) / len(window_slice), 3),
        })

    # Second-order signal (OCAC Delta_secondDiff): curvature of C(t).
    # Δ²Cₙ = Cₙ₊₁ − 2Cₙ + Cₙ₋₁ — the acceleration of coherence change, a
    # leading indicator the level/rate metrics miss. Aligned to interior
    # windows; endpoints have no curvature (None).
    curv = series_curvature([row["C"] for row in series])
    for row in series:
        row["C_curvature"] = None
    for i, cv in enumerate(curv):
        series[i + 1]["C_curvature"] = cv

    return series


# ── Main entry point ──────────────────────────────────────────

def current_coherence(window: int = WINDOW) -> CoherenceState:
    """
    Compute C(t) from the most recent `window` decisions.
    Returns a CoherenceState dataclass.
    """
    decisions  = _load_decisions(window)
    cal_errors = _load_calibration()
    mem_q, mem_n = _load_memory_quality()
    gains_data   = reflection_gain_analysis()

    cr, low_conf_rate  = _c_routing(decisions)
    cc                 = _c_calib(cal_errors)
    cq                 = _c_quality(decisions, mem_q, mem_n)
    composite          = round((cr + cc + cq) / 3, 4)

    n = len(decisions)
    reflect_rate  = round(sum(1 for d in decisions if d["reflect"]) / max(n, 1), 3)
    mean_regret   = round(sum(d["regret"] for d in decisions) / max(n, 1), 4)
    conflict_rate = round(sum(1 for d in decisions if d["conflict"]) / max(n, 1), 4)

    return CoherenceState(
        t=n,
        window=window,
        c_routing=cr,
        c_calib=cc,
        c_quality=cq,
        C=composite,
        conflict_rate=conflict_rate,
        low_confidence_rate=low_conf_rate,
        reflection_rate=reflect_rate,
        mean_regret=mean_regret,
        n_decisions=n,
        G_r_mean=gains_data["mean"],
        G_r_std=gains_data["std"],
        G_r_n=gains_data["n"],
        G_r_positive=gains_data["positive_frac"],
        mem_avg_quality=round(mem_q, 3),
        mem_n=mem_n,
    )


def print_coherence(state: CoherenceState) -> None:
    bar = lambda v: "█" * int(v * 20) + "░" * (20 - int(v * 20))
    print(f"\n{'='*60}")
    print(f"  Coherence State  C(t)  —  last {state.n_decisions} decisions")
    print(f"{'='*60}")
    print(f"\n  C(t)  = {state.C:.4f}  {bar(state.C)} {'COHERENT' if state.C > 0.75 else 'DEGRADED'}")
    print("\n  Components:")
    print(f"    C_routing  {state.c_routing:.4f}  {bar(state.c_routing)}  (mean confidence · low-conf {state.low_confidence_rate:.3f})")
    print(f"    C_calib    {state.c_calib:.4f}  {bar(state.c_calib)}  (1 - mean|cal_error|)")
    print(f"    C_quality  {state.c_quality:.4f}  {bar(state.c_quality)}  (mean proxy performance)")
    print("\n  Supporting metrics:")
    print(f"    Reflect rate   {state.reflection_rate:.3f}")
    print(f"    Mean regret    {state.mean_regret:.4f}")
    print(f"    Mem avg q      {state.mem_avg_quality:.3f}  ({state.mem_n} records)")
    if state.G_r_n > 0:
        print("\n  Reflection gain G_r = s_final − s_initial:")
        print(f"    n={state.G_r_n}  mean={state.G_r_mean:+.4f}  std={state.G_r_std:.4f}  "
              f"positive={state.G_r_positive:.1%}")
    print()


def print_dynamics(series: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"  Coherence Dynamics  C(t)  — rolling windows of {WINDOW}")
    print(f"{'='*60}")
    print(f"  {'Win':>4}  {'C(t)':>6}  {'C_rt':>6}  {'C_ca':>6}  {'C_ql':>6}  {'Δ²C':>8}  {'loco%':>6}  {'refl%':>6}  Trend")
    print(f"  {'─'*66}")
    prev = None
    for row in series:
        delta = ""
        if prev is not None:
            delta = "▲" if row["C"] > prev + 0.005 else ("▼" if row["C"] < prev - 0.005 else "→")
        cv = row.get("C_curvature")
        cv_str = f"{cv:>+8.4f}" if cv is not None else f"{'·':>8}"
        loco = row.get('low_confidence_rate', row.get('conflict_rate', 0.0))
        print(f"  {row['window_idx']:>4}  {row['C']:>6.4f}  {row['c_routing']:>6.4f}  "
              f"{row['c_calib']:>6.4f}  {row['c_quality']:>6.4f}  {cv_str}  "
              f"{loco*100:>5.1f}%  {row['reflect_rate']*100:>5.1f}%  {delta}")
        prev = row["C"]

    c_series = [row["C"] for row in series]
    peak = max_abs_curvature(c_series)
    # Signed alarm of record: keep the sign max_abs_curvature folds away, so a
    # downturn (concave, bending down from a high level) reads differently from a
    # self-correcting rebound (convex). Traces to OCAC Delta_secondDiff.
    signed = curvature_leading_indicator(c_series)
    if signed["warn"]:
        verdict = "⚠ downturn — bending down from a high level (instability leading indicator)"
    elif signed["regime"] == "rebound":
        verdict = "↻ rebound — self-correcting (safe)"
    elif peak > 0.05:
        verdict = "bending sharply"
    else:
        verdict = "trajectory smooth"
    print(f"\n  Peak |Δ²C| = {peak:.4f}  (signed {signed['signed_peak']:+.4f}, "
          f"{signed['regime']})\n  {verdict}")
    print()


def print_reflection_test(gains: dict) -> None:
    print(f"\n{'='*60}")
    print("  Empirical Test: Reflection Increases Coherence")
    print("  Claim: E[G_r | reflect=True] > 0")
    print(f"{'='*60}")
    if gains["n"] == 0:
        print("  No reflection data available.\n")
        return
    print(f"\n  n={gains['n']}  G_r = score_final − score_initial")
    print(f"  Mean G_r  = {gains['mean']:+.4f}")
    print(f"  Std  G_r  = {gains['std']:.4f}")
    print(f"  G_r > 0   = {gains['positive_frac']:.1%}  ({int(gains['positive_frac']*gains['n'])}/{gains['n']} improved)")
    print(f"  Range     = [{gains['min']:+.3f}, {gains['max']:+.3f}]")
    if gains["mean"] >= 0:
        print("\n  ✓ Claim SUPPORTED: mean G_r ≥ 0, reflection is non-destructive")
    else:
        print("\n  ✗ Claim NOT SUPPORTED: mean G_r < 0")
    print()


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Coherence functional for the agentic AI system")
    parser.add_argument("--json",       action="store_true", help="Output current state as JSON")
    parser.add_argument("--dynamics",   action="store_true", help="Show full time-series table")
    parser.add_argument("--reflection", action="store_true", help="Show reflection gain analysis only")
    parser.add_argument("--window",     type=int, default=WINDOW, help=f"Rolling window size (default={WINDOW})")
    args = parser.parse_args()

    state = current_coherence(args.window)

    if args.json:
        print(json.dumps(asdict(state), indent=2))
    elif args.reflection:
        print_reflection_test(reflection_gain_analysis())
    else:
        print_coherence(state)
        if args.dynamics:
            print_dynamics(coherence_time_series(args.window))
            # Memory coherence
            mc = memory_coherence_history()
            print(f"{'='*60}")
            print("  Memory Coherence  C_memory  by type")
            print(f"{'='*60}")
            print(f"  {'Type':<15}  {'n':>5}  {'avg_q':>7}  {'high≥0.70':>10}  {'low<0.55':>9}  C_memory")
            for r in mc:
                bar = "█" * int(r["c_memory"] * 20)
                print(f"  {r['type']:<15}  {r['count']:>5}  {r['avg_quality']:>7.3f}  "
                      f"{r['high_quality']:>10}  {r['low_quality']:>9}  {bar}")
            print()
        else:
            print_reflection_test(reflection_gain_analysis())
