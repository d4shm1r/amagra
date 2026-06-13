# ~/agentic-ai/memory_wipe.py
# One-time wipe. Drops all rows, resets autoincrement, keeps schema.

import sqlite3
import os

DB_PATH = os.path.join(os.path.expanduser('~/agentic-ai'), 'memory', 'agent_memory.db')

conn = sqlite3.connect(DB_PATH)
before = conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
conn.execute('DELETE FROM memories')
conn.execute('DELETE FROM sqlite_sequence WHERE name="memories"')
conn.commit()
after = conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
conn.close()

print(f"Wiped {before} entries. Remaining: {after}. Schema intact.")
