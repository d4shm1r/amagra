"""
Migrate agent_memory.db (SQLite + FAISS) → PostgreSQL + pgvector.

Usage:
    # Dry run — shows what would be migrated
    python scripts/migrate_to_pgvector.py --dry-run

    # Full migration
    MEMORY_PG_DSN="postgresql://user:pass@localhost:5432/agentmemory" \
    python scripts/migrate_to_pgvector.py

    # With explicit DSN
    python scripts/migrate_to_pgvector.py --dsn "postgresql://localhost/agentmemory"

Requires:
    pip install psycopg2-binary pgvector
"""

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "agent_memory.db")


def count_sqlite(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL").fetchone()[0]


def migrate(dsn: str, dry_run: bool, batch_size: int = 100) -> None:
    import numpy as np
    import psycopg2
    from pgvector.psycopg2 import register_vector

    sq = sqlite3.connect(SQLITE_PATH, timeout=30)
    total = count_sqlite(sq)
    print(f"SQLite source   : {SQLITE_PATH}")
    print(f"Rows to migrate : {total}")

    if dry_run:
        print("[dry-run] No changes made.")
        sq.close()
        return

    pg = psycopg2.connect(dsn)
    register_vector(pg)

    # Schema is created by PgvectorBackend.__init__, but we do it here too for safety
    with pg:
        cur = pg.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id         SERIAL PRIMARY KEY,
                timestamp  TIMESTAMPTZ DEFAULT NOW(),
                agent_name TEXT,
                mem_type   TEXT,
                content    TEXT,
                metadata   JSONB,
                embedding  vector(768),
                quality    REAL    DEFAULT 1.0,
                use_count  INTEGER DEFAULT 0,
                last_used  TIMESTAMPTZ
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS retrieval_audits (
                id        SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                query     TEXT,
                caller    TEXT,
                retrieved JSONB,
                count     INTEGER
            );
        """)

    # Check if destination already has rows
    cur_check = pg.cursor()
    cur_check.execute("SELECT COUNT(*) FROM memories")
    existing = cur_check.fetchone()
    if existing and existing[0] > 0:
        ans = input(f"Destination already has {existing[0]} rows. Append? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            pg.close()
            sq.close()
            return

    rows = sq.execute(
        "SELECT id, timestamp, agent_name, mem_type, content, metadata, "
        "embedding, COALESCE(quality,1.0), COALESCE(use_count,0), last_used "
        "FROM memories WHERE embedding IS NOT NULL ORDER BY id"
    ).fetchall()

    migrated = skipped = 0
    t0 = time.time()

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        with pg:
            cur = pg.cursor()
            for row in batch:
                _, ts, agent, mtype, content, meta_raw, emb_blob, quality, use_count, last_used = row
                try:
                    emb = np.frombuffer(emb_blob, dtype=np.float32)
                    if emb.shape[0] != 768:
                        skipped += 1
                        continue
                    # Re-normalize just in case
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb = emb / norm

                    try:
                        meta = json.loads(meta_raw) if meta_raw else None
                    except Exception:
                        meta = None

                    cur.execute(
                        """INSERT INTO memories
                           (timestamp, agent_name, mem_type, content, metadata,
                            embedding, quality, use_count, last_used)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (ts, agent, mtype, content,
                         json.dumps(meta) if meta else None,
                         emb.tolist(),
                         float(quality), int(use_count), last_used),
                    )
                    migrated += 1
                except Exception as e:
                    print(f"  row {row[0]} error: {e}")
                    skipped += 1

        elapsed = round(time.time() - t0, 1)
        pct = round((i + len(batch)) / len(rows) * 100)
        print(f"  {i + len(batch)}/{len(rows)} ({pct}%)  migrated={migrated}  skipped={skipped}  {elapsed}s")

    # Build HNSW index after bulk load (much faster than incremental)
    print("Building HNSW index …")
    with pg:
        pg.cursor().execute("""
            CREATE INDEX IF NOT EXISTS memories_hnsw_idx
            ON memories USING hnsw (embedding vector_cosine_ops)
            WITH (m=16, ef_construction=64);
        """)
        pg.cursor().execute("CREATE INDEX IF NOT EXISTS memories_agent_idx ON memories(agent_name);")

    elapsed_total = round(time.time() - t0, 1)
    print(f"\nDone in {elapsed_total}s")
    print(f"  Migrated : {migrated}")
    print(f"  Skipped  : {skipped}")
    cur_final = pg.cursor()
    cur_final.execute("SELECT COUNT(*) FROM memories")
    print(f"  Total in PG: {cur_final.fetchone()[0]}")

    pg.close()
    sq.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate SQLite memories to pgvector")
    parser.add_argument("--dsn", default=os.environ.get("MEMORY_PG_DSN", "postgresql://localhost/agentmemory"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    print(f"DSN: {args.dsn}")
    migrate(args.dsn, dry_run=args.dry_run, batch_size=args.batch_size)
