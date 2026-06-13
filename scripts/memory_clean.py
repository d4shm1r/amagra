# ~/agentic-ai/memory_clean.py
# ─────────────────────────────────────────────────────────────
# One-time script to audit and clean existing memories.
# Run with:  python3 memory_clean.py --dry-run   (preview only)
#            python3 memory_clean.py --clean      (delete bad entries)
#            python3 memory_clean.py --clean-content (strip fluff, keep entry)
#
# Never deletes without explicit --clean flag.
# ─────────────────────────────────────────────────────────────

import sqlite3
import sys
import os
sys.path.insert(0, os.path.expanduser('~/agentic-ai'))

from memory_filter import should_save, clean_content

DB_PATH = os.path.join(os.path.expanduser('~/agentic-ai'), 'memory', 'agent_memory.db')


def audit():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT id, agent_name, mem_type, content FROM memories ORDER BY id ASC'
    ).fetchall()
    conn.close()

    keep   = []
    drop   = []
    clean  = []  # should save but content needs cleaning

    seen_ids = set()

    for row_id, agent, mem_type, content in rows:
        cleaned = clean_content(content or '')
        ok, reason = should_save(cleaned, mem_type, agent)

        was_cleaned = (cleaned.strip() != (content or '').strip())

        if not ok:
            drop.append((row_id, agent, mem_type, reason, content[:80]))
        elif was_cleaned:
            clean.append((row_id, agent, mem_type, cleaned, content[:80]))
            keep.append((row_id, agent, mem_type, content[:80]))
        else:
            keep.append((row_id, agent, mem_type, content[:80]))

    return keep, drop, clean


def print_report(keep, drop, clean):
    total = len(keep) + len(drop)
    print(f"\n{'='*55}")
    print("  MEMORY AUDIT REPORT")
    print(f"{'='*55}")
    print(f"  Total entries : {total}")
    print(f"  Keep          : {len(keep)}")
    print(f"  Drop (noise)  : {len(drop)}")
    print(f"  Clean content : {len(clean)}")
    print(f"{'='*55}")

    if drop:
        print(f"\n  ── ENTRIES TO DROP ({len(drop)}) ──")
        for row_id, agent, mem_type, reason, preview in drop:
            print(f"  [{row_id}] {agent}/{mem_type} — {reason}")
            print(f"       {preview!r}")

    if clean:
        print(f"\n  ── ENTRIES TO CLEAN ({len(clean)}) ──")
        for row_id, agent, mem_type, cleaned, original_preview in clean:
            print(f"  [{row_id}] {agent}/{mem_type}")
            print(f"       BEFORE: {original_preview!r}")
            print(f"       AFTER:  {cleaned[:80]!r}")


def do_clean(drop, clean):
    conn = sqlite3.connect(DB_PATH)
    dropped = 0
    cleaned = 0

    # Delete noise entries
    for row_id, agent, mem_type, reason, _ in drop:
        conn.execute('DELETE FROM memories WHERE id = ?', (row_id,))
        dropped += 1

    # Update content-cleaned entries (strip fluff openers, keep real content)
    for row_id, agent, mem_type, cleaned_content, _ in clean:
        conn.execute(
            'UPDATE memories SET content = ? WHERE id = ?',
            (cleaned_content, row_id)
        )
        cleaned += 1

    conn.commit()
    conn.close()

    print("\n  ✅ Done.")
    print(f"  Deleted  : {dropped} entries")
    print(f"  Cleaned  : {cleaned} entries")

    # Final count
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
    conn.close()
    print(f"  Remaining: {count} entries in DB")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else '--dry-run'

    print("Scanning memory DB...")
    keep, drop, clean = audit()
    print_report(keep, drop, clean)

    if mode == '--dry-run':
        print("\n  DRY RUN — no changes made.")
        print(f"  Run with --clean to delete {len(drop)} noise entries")
        print(f"  and clean {len(clean)} fluff-prefixed entries.")

    elif mode == '--clean':
        if not drop and not clean:
            print("\n  Nothing to clean.")
        else:
            confirm = input(f"\n  Delete {len(drop)} entries and clean {len(clean)}? [y/N] ")
            if confirm.lower() == 'y':
                do_clean(drop, clean)
            else:
                print("  Aborted.")
    else:
        print(f"\n  Unknown mode: {mode}")
        print("  Use --dry-run or --clean")
