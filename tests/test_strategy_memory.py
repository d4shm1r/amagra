"""Tests for decision/strategy_memory.py — aggregation + ranking + idempotent backfill."""
import json
import os
import sqlite3
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decision.strategy_memory import (
    StrategyMemory, StrategyRecord, task_class_of, canonical_strategy,
)


def _mem():
    d = tempfile.mkdtemp()
    return StrategyMemory(path=os.path.join(d, "strategy.db"))


def test_task_class_and_canonical_strategy():
    assert task_class_of("python", "debug") == "python/debug"
    assert task_class_of(None, None) == "general/explanation"
    assert canonical_strategy("python_dev") == "python_dev"
    assert canonical_strategy("python_dev", "light", memory_used=True) == "python_dev+reflect:light+memory"
    assert canonical_strategy("ai_ml", "full", tool_used=True) == "ai_ml+reflect:full+tool"


def test_stats_ranking_success_then_latency():
    m = _mem()
    tc = "python/debug"
    # strategy A: 100% but slow; B: 50% fast; C: 100% fast
    for _ in range(4): m.record(StrategyRecord(tc, "A", True, latency_ms=9000))
    for i in range(4): m.record(StrategyRecord(tc, "B", i < 2, latency_ms=100))
    for _ in range(4): m.record(StrategyRecord(tc, "C", True, latency_ms=100))
    stats = m.stats_for(tc)
    # C (100%, fast) first, A (100%, slow) second, B (50%) last
    assert [s.strategy for s in stats] == ["C", "A", "B"]
    assert stats[0].success_rate == 1.0 and stats[-1].success_rate == 0.5


def test_none_success_excluded_from_rate():
    m = _mem()
    tc = "ai_ml/comparison"
    m.record(StrategyRecord(tc, "S", True))
    m.record(StrategyRecord(tc, "S", None))   # ungradeable — not counted
    m.record(StrategyRecord(tc, "S", None))
    s = m.stats_for(tc)[0]
    assert s.attempts == 3 and s.graded == 1 and s.success_rate == 1.0


def test_best_for_requires_min_attempts():
    m = _mem()
    tc = "net/procedural"
    m.record(StrategyRecord(tc, "lucky", True))          # 1 attempt
    assert m.best_for(tc, min_attempts=3) is None
    for _ in range(3): m.record(StrategyRecord(tc, "solid", True))
    assert m.best_for(tc, min_attempts=3).strategy == "solid"


def test_ingest_run_log_is_idempotent_and_derives_fields():
    m = _mem()
    d = tempfile.mkdtemp()
    rl = os.path.join(d, "runtime.db")
    con = sqlite3.connect(rl)
    con.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, ts REAL, task TEXT, ext_id TEXT, output TEXT, meta TEXT)")
    rows = [
        {"run_id": "r1", "signal_domain": "python", "signal_shape": "debug",
         "agent": "python_dev", "reflect_level": "light", "memory_used": True,
         "response_quality": 0.82, "duration_ms": 8000},
        {"run_id": "r2", "signal_domain": "python", "signal_shape": "debug",
         "agent": "python_dev", "reflect_level": "none", "memory_used": False,
         "response_quality": 0.40, "duration_ms": 1200},
        {"run_id": "r3", "signal_domain": "ai_ml", "signal_shape": "comparison",
         "agent": "ai_ml", "reflect_level": "none",
         "duration_ms": 900},  # no quality → success None
    ]
    for r in rows:
        con.execute("INSERT INTO runs (ts, task, ext_id, output, meta) VALUES (?,?,?,?,?)",
                    (1.0, "t", r["run_id"], "o", json.dumps(r)))
    con.commit(); con.close()

    assert m.ingest_run_log(rl) == 3
    assert m.ingest_run_log(rl) == 0        # idempotent — dedup on run_id

    s = m.stats_for("python/debug")
    strategies = {x.strategy for x in s}
    assert "python_dev+reflect:light+memory" in strategies
    assert "python_dev" in strategies
    # r3 had no quality → success None → graded 0
    aiml = m.stats_for("ai_ml/comparison")[0]
    assert aiml.graded == 0 and aiml.attempts == 1


def test_shipped_module_imports_and_db_path():
    # Real StrategyMemory() must resolve a db path without error.
    m = StrategyMemory(path=os.path.join(tempfile.mkdtemp(), "s.db"))
    assert m.task_classes() == []
