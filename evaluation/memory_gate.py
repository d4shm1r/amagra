"""
evaluation/memory_gate.py — the release gate for memory synthesis.

The strategy that justifies the whole product is "trustworthy memory." A false
memory about a project is worse than no memory: it makes the system confidently
wrong about the user's own work, which is the fastest way to destroy the trust
the moat depends on. So features that *synthesize* over accumulated memory —
above all "Explain this project" — must not ship behind a memory layer whose
recall hasn't been measured.

This module is the gate. evaluation/memory_recall_bench.py writes a verdict here
after measuring recall, provenance ordering, and currency safety; synthesis
features call synthesis_allowed() and stay dark until the verdict is PASS and
fresh. The benchmark is the lock; this is the key.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from infrastructure.paths import base_dir

# How long a passing verdict is trusted before it's considered stale. The memory
# corpus changes as decisions accumulate, so a months-old PASS no longer
# describes the live system; re-run the benchmark to refresh it.
VERDICT_TTL_DAYS = 14


def _gate_file() -> str:
    p = os.path.join(base_dir(), "logs", "memory_gate.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def write_verdict(report: dict) -> None:
    """Persist a benchmark report as the current gate verdict."""
    report = dict(report)
    report.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    with open(_gate_file(), "w") as f:
        json.dump(report, f, indent=2)


def read_verdict() -> dict | None:
    """The last written verdict, or None if the benchmark has never run."""
    try:
        with open(_gate_file()) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _age_days(iso: str) -> float:
    try:
        ts = datetime.fromisoformat(iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
    except Exception:
        return float("inf")


def synthesis_allowed() -> bool:
    """True only if the most recent benchmark PASSED and is not stale.

    Fails closed: no verdict, a failing verdict, or a stale verdict all return
    False, so a synthesis feature defaults to *not* trusting unmeasured memory.
    """
    v = read_verdict()
    if not v or not v.get("passed"):
        return False
    return _age_days(v.get("generated_at", "")) <= VERDICT_TTL_DAYS


def status() -> dict:
    """Human/API-readable gate status: why synthesis is or isn't allowed."""
    v = read_verdict()
    if not v:
        return {"allowed": False, "reason": "benchmark has never run",
                "verdict": None}
    age = _age_days(v.get("generated_at", ""))
    if not v.get("passed"):
        reason = "last benchmark FAILED — " + "; ".join(v.get("failures", []) or ["below threshold"])
    elif age > VERDICT_TTL_DAYS:
        reason = f"verdict is stale ({age:.0f}d old > {VERDICT_TTL_DAYS}d TTL) — re-run benchmark"
    else:
        reason = "recall benchmark passed and is current"
    return {
        "allowed":      synthesis_allowed(),
        "reason":       reason,
        "generated_at": v.get("generated_at"),
        "age_days":     round(age, 1) if age != float("inf") else None,
        "metrics":      v.get("metrics"),
        "thresholds":   v.get("thresholds"),
    }
