"""
strategy_memory.py — narrow "what worked before" memory for the router.

Semantic memory stores *what information the system saw*. Strategy memory stores
*which approach worked for this kind of task* — the organizational memory an
expert has and a wrapper doesn't. This is the aggregation/query layer the
STRATEGIC_SCORECARD names as the join key for the decision-intelligence layer:

    task_class → strategy → {attempts, success_rate, avg_cost, avg_latency}

It is deliberately narrow (not the full Personal Knowledge OS). Two producers:
  * record(StrategyRecord)  — live wiring writes one row per decision;
  * ingest_run_log()        — backfill from the run log we already keep, since
    its meta already carries every field a StrategyRecord needs.

Success is graded correctness when the caller has it; otherwise a response_quality
proxy (>= SUCCESS_QUALITY). Rows where neither is known store success=None and are
excluded from success_rate — honest under-counting, never a guessed pass.

CLI:
  python3 -m decision.strategy_memory --ingest              # backfill from run log
  python3 -m decision.strategy_memory --report              # ranked table, all classes
  python3 -m decision.strategy_memory --best python/debug   # best strategy for a class
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from dataclasses import dataclass

from infrastructure.db import path as _dbpath

# response_quality at/above which a run counts as a success when no graded
# correctness is supplied. Matches the ADB / calibration convention.
SUCCESS_QUALITY = 0.60


@dataclass
class StrategyRecord:
    task_class: str            # e.g. "python/debug"
    strategy: str              # canonical composed path, e.g. "python_dev+reflect:light"
    success: bool | None       # graded correctness, or quality proxy, or None
    latency_ms: int = 0
    cost: float = 0.0          # token/compute proxy (0 when unknown)
    regret: float | None = None
    run_id: str | None = None  # dedup key for run-log backfill (None for live rows)
    ts: float = 0.0


@dataclass
class StrategyStat:
    task_class: str
    strategy: str
    attempts: int
    successes: int
    graded: int
    success_rate: float        # successes / graded (0 when nothing graded)
    avg_cost: float
    avg_latency_ms: float


def task_class_of(signal_domain: str | None, signal_shape: str | None) -> str:
    """Coarse task class from the query signal — the unit strategies are learned
    per. Domain is *what* the task is about, shape is *how* it must be answered."""
    d = (signal_domain or "general").strip().lower() or "general"
    s = (signal_shape or "explanation").strip().lower() or "explanation"
    return f"{d}/{s}"


def canonical_strategy(agent: str | None, reflect_level: str = "none",
                       memory_used: bool = False, tool_used: bool = False) -> str:
    """Normalized composed path so the same strategy always aggregates together.
    Order is fixed (agent, reflect, memory, tool) so "+".join is canonical."""
    parts = [agent or "unknown"]
    if reflect_level and reflect_level != "none":
        parts.append(f"reflect:{reflect_level}")
    if memory_used:
        parts.append("memory")
    if tool_used:
        parts.append("tool")
    return "+".join(parts)


class StrategyMemory:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or _dbpath("strategy")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._init()

    def _init(self) -> None:
        con = sqlite3.connect(self.path)
        con.execute(
            """CREATE TABLE IF NOT EXISTS strategy_records (
                   id         INTEGER PRIMARY KEY AUTOINCREMENT,
                   ts         REAL,
                   task_class TEXT NOT NULL,
                   strategy   TEXT NOT NULL,
                   success    INTEGER,          -- 1/0/NULL(unknown)
                   latency_ms INTEGER,
                   cost       REAL,
                   regret     REAL,
                   run_id     TEXT              -- dedup key for run-log backfill
               )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_sr_class ON strategy_records(task_class)")
        # NULL run_ids are distinct in SQLite, so live rows never collide; only
        # backfilled rows (with a run_id) are deduplicated on re-ingest.
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sr_runid ON strategy_records(run_id)")
        con.commit()
        con.close()

    def record(self, sr: StrategyRecord) -> bool:
        """Append one decision outcome. Returns False if a row with the same
        run_id already exists (idempotent backfill)."""
        con = sqlite3.connect(self.path)
        try:
            con.execute(
                """INSERT OR IGNORE INTO strategy_records
                   (ts, task_class, strategy, success, latency_ms, cost, regret, run_id)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (sr.ts or time.time(), sr.task_class, sr.strategy,
                 None if sr.success is None else int(sr.success),
                 int(sr.latency_ms or 0), float(sr.cost or 0.0), sr.regret, sr.run_id),
            )
            changed = con.total_changes > 0
            con.commit()
            return changed
        finally:
            con.close()

    def stats_for(self, task_class: str, min_attempts: int = 1) -> list[StrategyStat]:
        """Strategies tried for a task class, ranked by success_rate desc then
        latency asc (cheapest-successful-first)."""
        con = sqlite3.connect(self.path)
        rows = con.execute(
            """SELECT strategy,
                      COUNT(*)                                          AS n,
                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END)        AS succ,
                      SUM(CASE WHEN success IS NOT NULL THEN 1 ELSE 0 END) AS graded,
                      AVG(cost)                                         AS ac,
                      AVG(latency_ms)                                   AS al
               FROM strategy_records
               WHERE task_class = ?
               GROUP BY strategy""",
            (task_class,),
        ).fetchall()
        con.close()
        stats: list[StrategyStat] = []
        for strat, n, succ, graded, ac, al in rows:
            if n < min_attempts:
                continue
            rate = (succ / graded) if graded else 0.0
            stats.append(StrategyStat(
                task_class=task_class, strategy=strat, attempts=n,
                successes=succ or 0, graded=graded or 0, success_rate=round(rate, 3),
                avg_cost=round(ac or 0.0, 1), avg_latency_ms=round(al or 0.0, 1),
            ))
        stats.sort(key=lambda s: (-s.success_rate, s.avg_latency_ms))
        return stats

    def best_for(self, task_class: str, min_attempts: int = 3) -> StrategyStat | None:
        """Best strategy for a task class, or None if no strategy has enough
        evidence yet (min_attempts guards against one-off luck)."""
        ranked = [s for s in self.stats_for(task_class) if s.attempts >= min_attempts]
        return ranked[0] if ranked else None

    def task_classes(self) -> list[str]:
        con = sqlite3.connect(self.path)
        rows = con.execute(
            "SELECT DISTINCT task_class FROM strategy_records ORDER BY task_class"
        ).fetchall()
        con.close()
        return [r[0] for r in rows]

    def ingest_run_log(self, runtime_db: str | None = None) -> int:
        """Backfill records from the run log. Idempotent: re-ingesting the same
        runs is a no-op (dedup on run_id). Returns rows newly inserted."""
        try:
            from core.run_log import _default_path
            p = runtime_db or _default_path()
        except Exception:
            p = runtime_db
        if not p or not os.path.exists(p):
            return 0
        con = sqlite3.connect(p)
        added = 0
        try:
            for ts, meta_json in con.execute("SELECT ts, meta FROM runs"):
                try:
                    m = json.loads(meta_json) if meta_json else {}
                except (ValueError, TypeError):
                    continue
                q = m.get("response_quality")
                sr = StrategyRecord(
                    task_class=task_class_of(m.get("signal_domain"), m.get("signal_shape")),
                    strategy=canonical_strategy(
                        m.get("agent"), m.get("reflect_level", "none"),
                        bool(m.get("memory_used")),
                    ),
                    success=(q >= SUCCESS_QUALITY) if isinstance(q, (int, float)) else None,
                    latency_ms=int(m.get("duration_ms") or 0),
                    run_id=m.get("run_id"),
                    ts=ts or 0.0,
                )
                if self.record(sr):
                    added += 1
        finally:
            con.close()
        return added


# ── CLI ────────────────────────────────────────────────────────────

def _print_report(mem: StrategyMemory) -> None:
    classes = mem.task_classes()
    if not classes:
        print("  Strategy memory is empty. Run --ingest first (needs run-log data).")
        return
    print(f"\n  Strategy memory — {len(classes)} task classes")
    print("  " + "─" * 74)
    print(f"  {'task_class':<22}{'strategy':<26}{'n':>4}{'succ%':>7}{'ms':>9}")
    print("  " + "─" * 74)
    for tc in classes:
        for i, s in enumerate(mem.stats_for(tc)):
            tcshow = tc if i == 0 else ""
            rate = f"{s.success_rate*100:.0f}%" if s.graded else "—"
            print(f"  {tcshow:<22}{s.strategy:<26}{s.attempts:>4}{rate:>7}{s.avg_latency_ms:>9.0f}")
    print("  " + "─" * 74)
    print("  success = graded correctness when known, else response_quality>=0.60 proxy")


def main() -> None:
    ap = argparse.ArgumentParser(description="Strategy memory — what worked before")
    ap.add_argument("--ingest", nargs="?", const=True, default=None,
                    help="backfill from run log; optional runtime.db path")
    ap.add_argument("--report", action="store_true", help="print ranked strategy table")
    ap.add_argument("--best", metavar="TASK_CLASS", default=None,
                    help="print the best strategy for a task class")
    args = ap.parse_args()

    mem = StrategyMemory()
    if args.ingest is not None:
        db = args.ingest if isinstance(args.ingest, str) else None
        added = mem.ingest_run_log(db)
        print(f"  Ingested {added} new records from run log.")
    if args.best:
        b = mem.best_for(args.best)
        print(f"  best_for({args.best!r}) = "
              + (f"{b.strategy}  ({b.success_rate*100:.0f}% over {b.attempts}, "
                 f"{b.avg_latency_ms:.0f}ms)" if b else "None (insufficient evidence)"))
    if args.report or (args.ingest is None and not args.best):
        _print_report(mem)


if __name__ == "__main__":
    main()
