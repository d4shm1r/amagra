# Troubleshooting — AMAGRA desktop on Windows

Practical guide for installing `AMAGRA-Setup-*.exe` on a fresh Windows machine and
recovering from the failures you're most likely to hit. The desktop app is an
Electron shell around the FastAPI backend, which is frozen into a PyInstaller
sidecar (`amagra-server.exe`) so there's no Python/venv to install — the shell
starts the sidecar, waits for it to answer on `127.0.0.1:8000`, then opens a
native window pointed at it (`desktop/main.js`).

## The happy path

1. **Run the installer.** It's a per-user NSIS one-click install →
   `%LOCALAPPDATA%\Programs\amagra`, with a Start-menu/desktop shortcut, then it
   launches automatically.
2. **SmartScreen will warn** — *"Windows protected your PC"*. This is expected:
   the build is **not code-signed** (see [RELEASING.md](RELEASING.md) → *Known
   caveat*). Click **More info → Run anyway**.
3. **First launch is slow (up to ~1–2 min) but silent.** The onefile sidecar
   unpacks to a temp dir and Windows Defender scans every extracted file. There
   should be **no stray console window** (fixed in v1.7.5). The app window opens
   once the backend is reachable.
4. **Onboarding appears** and offers Ollama — you can **Skip**. Ollama only powers
   the local model; the app runs fine without it.

## Where things live

| What | Path |
|---|---|
| Installed app | `%LOCALAPPDATA%\Programs\amagra` |
| Per-user data (memory, DBs) | `%APPDATA%\AMAGRA` |
| **Backend log (the key diagnostic)** | `%APPDATA%\AMAGRA\logs\backend.log` |

The backend log is append-only; each launch starts with a
`===== AMAGRA backend launch <timestamp> =====` marker. When reporting a problem,
copy the section from the **last** marker to the end.

## Failure modes

### A. "The backend did not start within the time limit"
The dialog names the log path. Open `%APPDATA%\AMAGRA\logs\backend.log` and read
the last launch section:

- Shows `Uvicorn running on http://127.0.0.1:8000` + a normal startup banner →
  the server booted fine but the shell's probe couldn't reach it. Usually the
  IPv6 issue in **D**, or a firewall/AV blocking loopback for the app.
- Shows a Python traceback or `[Errno …]` → the frozen backend **crashed on
  boot**. The traceback names the cause (a missing bundled file, an import error).
  Capture it and file an issue.
- Empty or missing → the sidecar exe never launched. See **C**.

### B. Port 8000 already in use
Something else owns `:8000`. v1.7.5 will *adopt* an already-running healthy server
on that port; otherwise it fails. Diagnose:

```
netstat -ano | findstr :8000
tasklist /fi "PID eq <pid-from-above>"
```

Close the offending app, or if it's a **stale AMAGRA backend** left by a previous
crash, `taskkill /PID <pid> /F`. (v1.7.5 reaps the backend on `SIGINT`/`SIGTERM`/
`SIGHUP` and tree-kills it on quit, so orphans holding the port should no longer
happen going forward.)

### C. Antivirus / Defender blocks or quarantines the sidecar
Symptom: `backend.log` is empty/missing, or launch hangs then fails. Because the
build is unsigned, Defender may quarantine `amagra-server.exe`. Check Defender →
*Protection history*; restore the file or add an exclusion for
`%LOCALAPPDATA%\Programs\amagra`. Then relaunch.

### D. Window opens but is blank / white / "can't reach this page"
The window loads `http://localhost:8000` while the backend binds IPv4
`127.0.0.1`, and Windows can resolve `localhost` to IPv6 `::1` first. Quick test
in a browser on that machine:

- `http://127.0.0.1:8000` **works** but `http://localhost:8000` **doesn't** →
  it's this. File an issue so the shell can load the window from `127.0.0.1` (and
  the UI switched to a relative API base to stay same-origin). Needs a new build.

### E. Nothing happens after "Run anyway"
Check Task Manager for an `AMAGRA`/`electron` process **and** an
`amagra-server.exe`. If neither is present, the Electron shell itself failed to
start — reinstall, or launch the installed
`%LOCALAPPDATA%\Programs\amagra\AMAGRA.exe` from a terminal to capture its output.

## The one thing to always collect

For **any** failure, grab `%APPDATA%\AMAGRA\logs\backend.log` (last launch section).
It's the single fastest way to tell a boot crash from a probe/network problem.

## Related

- [RELEASING.md](RELEASING.md) — how installers are built and the unsigned-build caveat.
- `desktop/main.js` — the startup/probe/shutdown logic referenced above.
