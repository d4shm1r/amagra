#!/usr/bin/env python3
"""
Retrieval Evaluation CLI

Reads the retrieval_audits table and produces a quality report.

Usage:
  python3 retrieval_eval.py               # full report (last 200 entries)
  python3 retrieval_eval.py --last 50     # last N audit entries
  python3 retrieval_eval.py --caller core_brain.fast_path
  python3 retrieval_eval.py --dump        # dump all raw audit rows

What it measures:
  - How many queries retrieved ≥1 failure/reflection memory (signal richness)
  - Type distribution of what gets surfaced
  - Quality distribution of retrieved memories
  - Freshness of retrieved memories (avg age in days)
  - Use-count distribution (which memories are over-used)
  - Caller breakdown

What it can't measure (requires ground truth labels):
  - Whether the retrieved memories were actually helpful
  - Precision or recall against known correct answers

To bootstrap ground truth, look at the raw audit rows and label a few:
  python3 retrieval_eval.py --dump | head -100
"""

import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_core.db as memory_db

# ── Helpers ───────────────────────────────────────────────────

def _age_days(timestamp: str) -> float:
    try:
        then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).total_seconds() / 86400
    except Exception:
        return 0.0


def _load_audits(conn, limit: int, caller_filter: str | None) -> list:
    if caller_filter:
        rows = conn.execute(
            "SELECT id, timestamp, query, caller, retrieved, count "
            "FROM retrieval_audits WHERE caller=? ORDER BY id DESC LIMIT ?",
            (caller_filter, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, timestamp, query, caller, retrieved, count "
            "FROM retrieval_audits ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    result = []
    for row in rows:
        r = {
            "id":        row[0],
            "timestamp": row[1],
            "query":     row[2],
            "caller":    row[3] or "",
            "count":     row[5],
        }
        try:
            r["retrieved"] = json.loads(row[4])
        except Exception:
            r["retrieved"] = []
        result.append(r)
    return result


def _load_memory_stats(conn) -> dict:
    """Load quality and type stats for all memories."""
    rows = conn.execute(
        "SELECT id, mem_type, COALESCE(quality,1.0), COALESCE(use_count,0), timestamp "
        "FROM memories"
    ).fetchall()
    by_id = {}
    for row_id, mtype, quality, use_count, ts in rows:
        by_id[row_id] = {
            "type":      mtype,
            "quality":   quality,
            "use_count": use_count,
            "age_days":  _age_days(ts),
        }
    return by_id


# ── Report sections ───────────────────────────────────────────

def _section_overview(audits: list):
    print("─── Overview ────────────────────────────────────────────")
    n      = len(audits)
    total  = sum(a["count"] for a in audits)
    callers = set(a["caller"] for a in audits)
    print(f"  Audit entries analyzed:  {n}")
    print(f"  Total memories retrieved: {total}")
    print(f"  Avg per query:            {total/n:.1f}" if n else "  No data")
    print(f"  Unique callers:           {len(callers)}")
    for c in sorted(callers):
        cc = sum(1 for a in audits if a["caller"] == c)
        print(f"    {c or '(unset)':35} {cc}")


def _section_type_distribution(audits: list, mem_stats: dict):
    print("\n─── Type distribution of retrieved memories ─────────────")
    type_counts  = defaultdict(int)
    total_items  = 0
    high_signal  = 0  # failure or reflection

    for a in audits:
        for r in a["retrieved"]:
            rid = r.get("id")
            if rid and rid in mem_stats:
                mtype = mem_stats[rid]["type"]
            else:
                mtype = r.get("type", "unknown")
            type_counts[mtype] += 1
            total_items += 1
            if mtype in ("failure", "reflection"):
                high_signal += 1

    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        pct  = 100 * c / total_items if total_items else 0
        flag = " ← high signal" if t in ("failure", "reflection") else ""
        print(f"  {t:18} {c:5}  ({pct:4.1f}%){flag}")

    if total_items:
        signal_pct = 100 * high_signal / total_items
        print(f"\n  Signal richness (failure+reflection): {high_signal}/{total_items} ({signal_pct:.1f}%)")
        if signal_pct < 5:
            print("  ⚠ Very low signal — failure/reflection memories rarely retrieved.")
            print("    Consider: saving more failure cases, or checking type_weight config.")
        elif signal_pct < 15:
            print("  ↗ Moderate signal — grows as more failure/reflection memories accumulate.")
        else:
            print("  ✓ Good signal richness.")


def _section_quality_distribution(audits: list, mem_stats: dict):
    print("\n─── Quality of retrieved memories ───────────────────────")
    qualities = []
    for a in audits:
        for r in a["retrieved"]:
            rid = r.get("id")
            if rid and rid in mem_stats:
                qualities.append(mem_stats[rid]["quality"])
            else:
                qualities.append(1.0)

    if not qualities:
        print("  No quality data.")
        return

    n      = len(qualities)
    avg_q  = sum(qualities) / n
    below  = sum(1 for q in qualities if q < 0.5)
    high   = sum(1 for q in qualities if q >= 0.8)

    # Histogram
    buckets = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    for lo, hi in buckets:
        c   = sum(1 for q in qualities if lo <= q < hi)
        pct = 100 * c / n
        bar = "█" * int(pct / 3)
        print(f"  {lo:.1f}–{hi:.1f}  {bar:<25} {c:4} ({pct:.1f}%)")

    print(f"\n  Avg quality of retrieved: {avg_q:.3f}")
    if avg_q < 0.6:
        print("  ⚠ Low average quality — most retrieved memories are unrated (quality=1.0 default)")
        print("    or were saved with low scores. Consider explicit quality on save().")
    else:
        print("  ✓ Quality distribution looks reasonable.")


def _section_freshness(audits: list, mem_stats: dict):
    print("\n─── Freshness of retrieved memories ─────────────────────")
    ages = []
    for a in audits:
        for r in a["retrieved"]:
            rid = r.get("id")
            if rid and rid in mem_stats:
                ages.append(mem_stats[rid]["age_days"])

    if not ages:
        print("  No age data available.")
        return

    avg_age = sum(ages) / len(ages)
    old30   = sum(1 for a in ages if a > 30)
    old90   = sum(1 for a in ages if a > 90)
    pct_old = 100 * old90 / len(ages) if ages else 0

    print(f"  Avg age of retrieved: {avg_age:.1f} days")
    print(f"  Older than 30 days:   {old30}/{len(ages)}")
    print(f"  Older than 90 days:   {old90}/{len(ages)} ({pct_old:.1f}%)")

    if pct_old > 30:
        print("  ⚠ Large fraction of old memories being retrieved.")
        print("    If they're consistently relevant, that's fine.")
        print("    If not, check for missing newer memories on the same topic.")
    else:
        print("  ✓ Retrieval skews toward recent memories as expected.")


def _section_use_concentration(mem_stats: dict):
    print("\n─── Memory use-count concentration ──────────────────────")
    counts = sorted(m["use_count"] for m in mem_stats.values())
    if not counts:
        print("  No use-count data.")
        return

    total_memories = len(counts)
    used           = sum(1 for c in counts if c > 0)
    never_used     = total_memories - used
    top10_pct_idx  = max(0, int(total_memories * 0.9))
    top10_count    = sum(counts[top10_pct_idx:])
    all_count      = sum(counts) or 1
    concentration  = 100 * top10_count / all_count

    print(f"  Total memories: {total_memories}")
    print(f"  Never retrieved: {never_used} ({100*never_used/total_memories:.1f}%)")
    print(f"  Top 10% of memories account for {concentration:.1f}% of retrievals")

    # Top 5 most-used
    sorted_mems = sorted(mem_stats.items(), key=lambda x: -x[1]["use_count"])[:5]
    if sorted_mems and sorted_mems[0][1]["use_count"] > 0:
        print("\n  Most-retrieved memories:")
        conn = sqlite3.connect(memory_db.DB_PATH)
        for mid, stats in sorted_mems:
            row = conn.execute("SELECT content FROM memories WHERE id=?", (mid,)).fetchone()
            content = row[0][:60] if row else "(not found)"
            print(f"    [{stats['type']:12}] q={stats['quality']:.1f}  used={stats['use_count']:3}  {content}")
        conn.close()

    if concentration > 80:
        print("\n  ⚠ High retrieval concentration — a few memories dominate.")
        print("    This can mean: (a) they're genuinely useful, or")
        print("    (b) the embedding space has blind spots for other topics.")


def _section_query_diversity(audits: list):
    print("\n─── Query sample (last 10) ──────────────────────────────")
    for a in audits[:10]:
        print(f"  [{a['caller'][:20]:20}] {a['query'][:60]}")


def _dump_raw(audits: list):
    for a in audits:
        print(json.dumps({
            "id":        a["id"],
            "timestamp": a["timestamp"],
            "query":     a["query"],
            "caller":    a["caller"],
            "count":     a["count"],
            "top_hit":   a["retrieved"][0] if a["retrieved"] else None,
        }, indent=2))


# ── Main ─────────────────────────────────────────────────────

def main():
    args    = sys.argv[1:]
    limit   = 200
    caller  = None
    dump    = "--dump" in args

    for i, a in enumerate(args):
        if a == "--last" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
        if a == "--caller" and i + 1 < len(args):
            caller = args[i + 1]

    if not os.path.exists(memory_db.DB_PATH):
        print(f"Memory DB not found at: {memory_db.DB_PATH}")
        print("Run the API server at least once to initialize the DB.")
        sys.exit(1)

    conn = sqlite3.connect(memory_db.DB_PATH)
    try:
        # Check retrieval_audits table exists
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "retrieval_audits" not in tables:
            print("retrieval_audits table not found — run the system once to initialize.")
            sys.exit(1)

        audits    = _load_audits(conn, limit, caller)
        mem_stats = _load_memory_stats(conn)
    finally:
        conn.close()

    if not audits:
        print(f"No audit entries found (limit={limit}, caller={caller or 'all'}).")
        print("Audit logging begins after the first search() call.")
        sys.exit(0)

    if dump:
        _dump_raw(audits)
        return

    print(f"\n{'═'*60}")
    print(f"  Memory Retrieval Evaluation Report")
    print(f"  DB: {memory_db.DB_PATH}")
    print(f"  Entries: {len(audits)} (of last {limit})")
    print(f"{'═'*60}\n")

    _section_overview(audits)
    _section_type_distribution(audits, mem_stats)
    _section_quality_distribution(audits, mem_stats)
    _section_freshness(audits, mem_stats)
    _section_use_concentration(mem_stats)
    _section_query_diversity(audits)

    print(f"\n{'═'*60}")
    print("  Run with --dump to see raw audit rows for manual labeling.")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    main()
