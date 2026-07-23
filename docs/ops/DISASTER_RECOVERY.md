# Disaster Recovery — backup & restore (self-hosted)

Amagra is a **local-first, single-machine** app: users self-host it (`docker compose
up` or a desktop build) on their own hardware. There is no server we run, so DR is
not a multi-region failover story — it is one thing: **back up the data directory,
know how to put it back.** This runbook is that.

Related: [DEPLOY.md](DEPLOY.md), [TROUBLESHOOTING_WINDOWS.md](TROUBLESHOOTING_WINDOWS.md).

---

## What is durable (and what is not)

Everything Amagra persists lives under **one root** — `base_dir()` in
[`infrastructure/paths.py`](../../infrastructure/paths.py):

- **`AMAGRA_DATA_DIR`** if set (packaged desktop builds point it at the OS user-data
  dir — e.g. `~/.local/share/amagra`, `~/Library/Application Support/Amagra`,
  `%APPDATA%\Amagra`), **else the project directory** (dev/checkout default).

Under that root, by tier of importance:

| Path | Contents | Losing it means |
|---|---|---|
| `memory/` | **Durable user data** — `agent_memory.db` (learned memory + FAISS vector index), `api_keys.db`, `registrations.db`, `stripe_events.db` | Irrecoverable. Learned memory, keys, registrations gone. **Always back up.** |
| `tasks.db` | The background task queue | In-flight/queued tasks lost. Low value once drained. |
| `logs/` | Telemetry / decision cluster (`decisions.db`, `runs.db`, `events.db`, `sessions.db`, `feedback.db`, `world_model.db`, …) | Analytics/learning **history** lost, not user data. Regenerates from new traffic. **Safe to delete** to reclaim space. |
| `data/amagra.db` | Single-file mode only (`AMAGRA_DB` set) — all of the above collapsed into one file (+ FAISS sidecar) | Same as `memory/` — back this up. |

**Rule of thumb:** `memory/` (or the single `amagra.db`) is the crown jewels; `logs/`
is disposable; `tasks.db` is transient.

---

## Backup

SQLite runs in **WAL mode**, so each `*.db` may have `*.db-wal` / `*.db-shm` sidecars
holding not-yet-checkpointed writes. A copy that grabs the `.db` but not its `-wal` can
be inconsistent. Two safe options:

**Option A — cold copy (simplest, recommended).** Stop the app first so WAL is
checkpointed and nothing is mid-write, then copy the whole root:

```bash
# docker: stop the api container (ollama/ui can stay up)
docker compose stop api

# copy the data root (adjust if AMAGRA_DATA_DIR is set elsewhere)
tar czf amagra-backup-$(date +%F).tar.gz memory/ tasks.db data/ 2>/dev/null

docker compose start api
```

**Option B — hot copy (no downtime).** Use SQLite's online backup, which is
WAL-consistent without stopping writers, per database file:

```bash
for db in memory/agent_memory.db memory/api_keys.db memory/registrations.db; do
  sqlite3 "$db" ".backup 'backup/$(basename "$db")'"
done
# then copy the FAISS index files under memory/ (plain file copy is fine — they are
# rewritten atomically, not appended)
```

> Do **not** simply `cp` a live `.db` without its `-wal`/`-shm` sidecars — that is the
> one way to capture a torn write. Cold copy or `.backup` avoids it.

**Cadence.** Back up `memory/` on whatever interval matches how much learned state you
can afford to lose (daily is plenty for a personal instance). `logs/` need not be backed
up. Keep at least one off-machine copy.

---

## Restore

```bash
docker compose stop api          # or quit the desktop app

# replace the data root from a backup (this OVERWRITES current state)
rm -rf memory/ tasks.db data/    # only what you are restoring
tar xzf amagra-backup-YYYY-MM-DD.tar.gz

docker compose start api
```

On next boot the app enables WAL on every database and reconnects; no migration step is
needed (schema is created idempotently). Verify with `GET /health` and, if you use
tasks, `GET /tasks/status` (shows `queue_depth`).

---

## Corruption / partial loss

- **`logs/` corrupted or huge:** stop the app, delete the offending `logs/*.db`, restart
  — it is recreated empty. You lose telemetry history only.
- **`memory/agent_memory.db` corrupted, no backup:** last resort — `sqlite3 db "PRAGMA
  integrity_check"`; if unrecoverable, delete it to start memory fresh (learned content
  lost, app functional).
- **Queue wedged (all tasks stuck `running` after a crash):** `reset_orphaned_tasks()`
  runs at startup and flips orphaned `running` → `pending`; a restart clears it.

---

## Backpressure (why the queue can't grow without bound)

The task worker drains `pending` tasks **serially**, so queue *depth* was the only
unbounded dimension. `POST /tasks/create` now rejects with **429** once
`AMAGRA_MAX_PENDING_TASKS` (default **100**, `0` disables) pending tasks exist, and
`GET /tasks/status` reports live `queue_depth` / `queue_limit`. This bounds `tasks.db`
growth and makes shed-load observable (#198).
