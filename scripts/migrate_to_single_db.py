#!/usr/bin/env python3
"""
migrate_to_single_db.py — collapse Amagra's separate SQLite files into one.

Amagra ships in separate-file mode by default (one ``.db`` per logical store,
see ``infrastructure/db.py``). Setting ``AMAGRA_DB=/path/amagra.db`` flips the
*runtime* to single-file mode, but existing data still lives in the old files.
This one-shot script copies that data into the single file so the flip is
lossless.

What it does
------------
  * Reads the separate-file layout from ``infrastructure.db.REGISTRY`` (always
    the per-store paths, regardless of AMAGRA_DB), and copies every table from
    each existing source DB into the target file.
  * Preserves ``rowid`` for every table. This matters for ``memories`` because
    the FAISS index (``IndexIDMap``) is keyed on ``memories.id`` — losing those
    ids would silently invalidate vector search. (Even so, the FAISS backend
    self-heals: it rebuilds when the cached vector count != row count.)
  * Copies the FAISS sidecar (``faiss_index.bin``) next to the target if it
    exists, so search is warm immediately after the flip.

Safety
------
  * Default is ``--dry-run``: it prints the plan and copies nothing.
  * The target file must not already exist unless you pass ``--force``.
  * Source files are only read, never modified — the migration is reversible by
    simply not setting AMAGRA_DB.

Usage
-----
    # See what would happen (no writes):
    python scripts/migrate_to_single_db.py --target amagra.db --dry-run

    # Actually consolidate:
    python scripts/migrate_to_single_db.py --target amagra.db --apply

    # Then flip the runtime and restart:
    export AMAGRA_DB=$(pwd)/amagra.db
"""

import argparse
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.db import REGISTRY, _ROOT  # noqa: E402


def _source_path(relpath: str) -> str:
    """Absolute separate-file path for a registry entry (ignores AMAGRA_DB)."""
    return os.path.join(_ROOT, relpath)


def _tables(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """(name, create_sql) for every user table, skipping SQLite internals."""
    return conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
    ).fetchall()


def _has_rowid_alias(conn: sqlite3.Connection, table: str) -> bool:
    """True if the table has an INTEGER PRIMARY KEY (which aliases rowid)."""
    for cid, name, ctype, notnull, default, pk in conn.execute(
        f"PRAGMA table_info('{table}')"
    ):
        if pk and ctype.upper() == "INTEGER":
            return True
    return False


def _norm_sql(sql: str) -> str:
    """Whitespace-normalised CREATE statement for schema comparison."""
    return " ".join(sql.split()).replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")


def _existing_create_sql(dst: sqlite3.Connection, table: str) -> str | None:
    row = dst.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else None


def _copy_table(dst: sqlite3.Connection, table: str, create_sql: str) -> int:
    """Copy one attached-source table into the main DB, preserving rowid. Returns rows copied.

    Raises ValueError if a same-named table already exists with a *different*
    schema — refusing to clobber rather than silently corrupting.
    """
    existing = _existing_create_sql(dst, table)
    if existing is not None and _norm_sql(existing) != _norm_sql(create_sql):
        raise ValueError(
            f'table "{table}" already exists with a different schema '
            f'(two stores claim the same table name)'
        )
    dst.execute(create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))

    if _has_rowid_alias(dst, table):
        # The integer PK already carries the rowid value; SELECT * preserves it.
        sql = f'INSERT INTO main."{table}" SELECT * FROM src."{table}"'
    else:
        cols = [r[1] for r in dst.execute(f'PRAGMA table_info("{table}")')]
        collist = ", ".join(f'"{c}"' for c in cols)
        sql = (
            f'INSERT INTO main."{table}" (rowid, {collist}) '
            f'SELECT rowid, {collist} FROM src."{table}"'
        )

    before = dst.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
    dst.execute(sql)
    after = dst.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
    return after - before


def plan() -> list[tuple[str, str, list[tuple[str, str, int]]]]:
    """For each existing source DB: (logical_name, abspath, [(table, create_sql, rows)])."""
    out = []
    for name, relpath in REGISTRY.items():
        src = _source_path(relpath)
        if not os.path.exists(src):
            continue
        conn = sqlite3.connect(src)
        try:
            tables = []
            for tname, csql in _tables(conn):
                rows = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
                tables.append((tname, csql, rows))
        finally:
            conn.close()
        out.append((name, src, tables))
    return out


def _copy_faiss_sidecar(target: str, dry_run: bool) -> str | None:
    """Copy memory/faiss_index.bin next to the target, if present. Returns dest path or None."""
    mem_rel = REGISTRY.get("memory")
    if not mem_rel:
        return None
    mem_dir = os.path.dirname(_source_path(mem_rel))
    sidecar = os.path.join(mem_dir, "faiss_index.bin")
    if not os.path.exists(sidecar):
        return None
    dest = os.path.join(os.path.dirname(target), "faiss_index.bin")
    if os.path.abspath(sidecar) == os.path.abspath(dest):
        return None
    if not dry_run:
        shutil.copy2(sidecar, dest)
    return dest


def main_args(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Consolidate Amagra's SQLite files into one.")
    ap.add_argument("--target", default=os.environ.get("AMAGRA_DB", ""),
                    help="Path to the single DB file (defaults to $AMAGRA_DB).")
    ap.add_argument("--apply", action="store_true",
                    help="Actually perform the migration (default is a dry run).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the plan and exit without writing (the default).")
    ap.add_argument("--force", action="store_true",
                    help="Allow merging into a target file that already exists.")
    args = ap.parse_args(argv)

    if not args.target:
        print("error: no target — pass --target PATH or set AMAGRA_DB", file=sys.stderr)
        return 2
    target = args.target if os.path.isabs(args.target) else os.path.join(_ROOT, args.target)
    dry_run = not args.apply  # apply is the only thing that writes

    sources = plan()
    sources = [s for s in sources if os.path.abspath(s[1]) != os.path.abspath(target)]

    total_tables = sum(len(t) for _, _, t in sources)
    total_rows = sum(r for _, _, t in sources for *_, r in t)
    print(f"Target : {target}")
    print(f"Sources: {len(sources)} DB file(s), {total_tables} table(s), {total_rows} row(s)\n")
    for name, src, tables in sources:
        print(f"  {name:14s} {src}")
        for tname, _csql, rows in tables:
            print(f"      - {tname:24s} {rows:>8d} rows")
    if not sources:
        print("Nothing to migrate (no separate source files found).")
        return 0

    if dry_run:
        print("\n[dry-run] no changes written. Re-run with --apply to migrate.")
        _copy_faiss_sidecar(target, dry_run=True)
        return 0

    if os.path.exists(target) and not args.force:
        print(f"\nerror: target exists: {target}\n"
              f"       refusing to merge into it. Move it aside or pass --force.",
              file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    dst = sqlite3.connect(target)
    copied = 0
    try:
        for name, src, tables in sources:
            dst.execute("ATTACH DATABASE ? AS src", (src,))
            try:
                for tname, csql, _rows in tables:
                    n = _copy_table(dst, tname, csql)
                    copied += n
                    print(f"  copied {n:>8d} rows  {name}.{tname}")
                dst.commit()
            finally:
                dst.execute("DETACH DATABASE src")
    except Exception as e:
        dst.rollback()
        print(f"\nerror during migration: {e}\n(target left partially written; "
              f"delete {target} and retry)", file=sys.stderr)
        return 1
    finally:
        dst.close()

    sidecar = _copy_faiss_sidecar(target, dry_run=False)
    print(f"\nDone. {copied} row(s) consolidated into {target}.")
    if sidecar:
        print(f"FAISS sidecar copied to {sidecar}.")
    print("\nNext steps:")
    print(f"  export AMAGRA_DB={target}")
    print("  # restart the API; verify /health and a memory search, then archive the old *.db files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_args())
