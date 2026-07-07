// AMAGRA desktop shell (Electron).
//
// Mirrors the AppImage contract (packaging/AppRun): the FastAPI server serves BOTH
// the API and the built UI on one port, so this shell only has to:
//   1. Start the backend (a frozen sidecar in production, the dev venv otherwise) —
//      unless a healthy server is already listening (e.g. `ai-start` is running).
//   2. Wait for /health, then open a native window pointed at it.
//   3. Tear down anything we started on quit.
//
// Env overrides: AMAGRA_PORT, AMAGRA_NO_OLLAMA=1.

const { app, BrowserWindow, Menu, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

const PORT = parseInt(process.env.AMAGRA_PORT || "8000", 10);
// Renderer origin: keep `localhost` (not 127.0.0.1) so the window matches the UI's
// default API base (ui/src/api.js → http://localhost:8000) and stays same-origin:
// no CORS. Chromium special-cases `localhost` to loopback and tries both families,
// so the window load is robust even when the server is IPv4-only.
const BASE = `http://localhost:${PORT}`;
// Health probe origin: the backend binds IPv4 `127.0.0.1` (see backendCommand),
// but on Windows `localhost` frequently resolves to IPv6 `::1` first — and Node's
// http.get, unlike Chromium, may not fall back to 127.0.0.1. Probing 127.0.0.1
// directly matches the actual listener on every platform. (This was the #1 cause
// of "Backend did not become healthy" on Windows.)
const PROBE = `http://127.0.0.1:${PORT}`;
// Dev loop: point the window at the Vite dev server (hot module reload) instead
// of the static ui/build the backend serves — UI edits then apply live, no
// `vite build` + reload. Run `cd ui && npm run dev` alongside, then
// `AMAGRA_DEV=1 npm start`. The API still lives at :8000; CORS already allows
// :3000 (api.py ALLOWED_ORIGINS), so cross-origin calls work.
const UI_URL = process.env.AMAGRA_UI_URL
  || (process.env.AMAGRA_DEV === "1" ? "http://localhost:3000" : BASE);
const REPO_ROOT = path.join(__dirname, "..");

let backend = null; // child we spawned (null if we reused an existing server)
let ollama = null;
let win = null;

// ── backend resolution ────────────────────────────────────────
// Production: a PyInstaller binary bundled next to the app (extraResources).
// Dev: the project venv running uvicorn against the repo checkout.
function backendCommand() {
  const exe = process.platform === "win32" ? "amagra-server.exe" : "amagra-server";
  const frozen = path.join(process.resourcesPath || "", "backend", exe);
  if (fs.existsSync(frozen)) {
    return { cmd: frozen, args: ["--host", "127.0.0.1", "--port", String(PORT)], cwd: path.dirname(frozen), frozen: true };
  }
  const venvPy = path.join(process.env.HOME || "", ".venvs", "langgraph-env", "bin", "python");
  const py = fs.existsSync(venvPy) ? venvPy : "python3";
  return {
    cmd: py,
    args: ["-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", String(PORT)],
    cwd: REPO_ROOT,
    frozen: false,
  };
}

function healthy() {
  return new Promise((resolve) => {
    const req = http.get(`${PROBE}/health`, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1000, () => { req.destroy(); resolve(false); });
  });
}

// A frozen onefile sidecar unpacks to %TEMP%/_MEIxxxx on every launch, and a
// fresh Windows Defender install scans every extracted file — cold first-launch
// can run well past a minute. Give it room before declaring failure.
async function waitForHealth(timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await healthy()) return true;
    if (backend && backend.exitCode !== null) return false; // died on boot
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function startOllama() {
  if (process.env.AMAGRA_NO_OLLAMA === "1") return;
  // Best-effort: if `ollama` is on PATH, make sure a server is up. Harmless if
  // one is already running (it will just exit).
  try {
    ollama = spawn("ollama", ["serve"], { stdio: "ignore", detached: false });
    ollama.on("error", () => { ollama = null; }); // not installed — fine
  } catch { ollama = null; }
}

async function startBackend() {
  if (await healthy()) return true; // reuse a server that's already up (e.g. ai-start)
  const { cmd, args, cwd, frozen } = backendCommand();
  // A packaged app installs read-only (a .app bundle, /opt, Program Files), so
  // the frozen backend's own dir (sys._MEIPASS) can't hold databases. Point
  // AMAGRA_DATA_DIR at the OS per-user data dir (~/Library/Application Support/
  // AMAGRA, %APPDATA%\AMAGRA, ~/.config/AMAGRA) so memory persists and writes
  // succeed. Dev (venv) keeps the project-dir default — matches `ai-start`.
  const env = { ...process.env };
  if (frozen) env.AMAGRA_DATA_DIR = app.getPath("userData");
  // Capture the sidecar's stdout+stderr to a logfile instead of discarding it
  // (stdio:"ignore"), so a boot failure leaves a diagnosable trail rather than a
  // silent "did not become healthy". The dialog below points the user here.
  backend = spawn(cmd, args, { cwd, stdio: ["ignore", logFd(), logFd()], env });
  backend.on("error", (e) => console.error("backend spawn failed:", e.message));
  return waitForHealth();
}

// Path to the backend logfile in the OS per-user data dir, and a lazily-opened
// append fd onto it. One shared fd for stdout+stderr keeps the stream ordered.
function logPath() {
  return path.join(app.getPath("userData"), "logs", "backend.log");
}
let _logFd = null;
function logFd() {
  if (_logFd !== null) return _logFd;
  try {
    const p = logPath();
    fs.mkdirSync(path.dirname(p), { recursive: true });
    _logFd = fs.openSync(p, "a");
  } catch {
    _logFd = "ignore"; // fall back to discarding rather than crashing the shell
  }
  return _logFd;
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: "AMAGRA",
    backgroundColor: "#F0E9DF", // cream — no white flash on load (see DESIGN_PRINCIPLES.md)
    icon: path.join(REPO_ROOT, "ui", "public", "logo512.png"),
    // Branded top bar: hide the OS title bar and paint the native window-controls
    // overlay in Gilded Calm (cream field, gold symbols). Win/Linux only — on
    // macOS the traffic-lights sit top-left, exactly where the ☰ launcher lives
    // (App.jsx: top 13 / left 15), so keep the native inset bar there.
    ...(process.platform === "darwin"
      ? {}
      : {
          titleBarStyle: "hidden",
          titleBarOverlay: { color: "#F0E9DF", symbolColor: "#8A5A00", height: 36 },
        }),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });
  // Keep the window titled AMAGRA — don't let the page's <title> override it.
  win.on("page-title-updated", (e) => e.preventDefault());
  // Open external links in the real browser, not inside the app shell.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  // Frameless top bar (Win/Linux): the hidden title bar turns the top strip into
  // client area, so declare a drag region — a transparent 36px strip that sits
  // UNDER the ☰ launcher (z 50) — and opt every interactive control out of it so
  // clicks/inputs still register. Injected from the shell to avoid touching the
  // React UI; delete this block to revert.
  if (process.platform !== "darwin") {
    win.webContents.on("did-finish-load", () => {
      win.webContents.insertCSS(
        "html::before{content:'';position:fixed;top:0;left:0;right:0;height:36px;" +
        "-webkit-app-region:drag;z-index:5}" +
        "button,a,input,textarea,select,label,summary,[role='button']," +
        "[role='tab'],[contenteditable],[tabindex]{-webkit-app-region:no-drag}"
      ).catch(() => {});
    });
  }
  win.loadURL(UI_URL);
  win.on("closed", () => { win = null; });
}

app.whenReady().then(async () => {
  // No File/Edit menu bar on Win/Linux (the ☰ launcher is the only chrome).
  // Keep the native app menu on macOS so Cmd+Q / copy-paste accelerators live.
  if (process.platform !== "darwin") Menu.setApplicationMenu(null);
  startOllama();
  const ok = await startBackend();
  if (!ok) {
    const { dialog } = require("electron");
    dialog.showErrorBox(
      "AMAGRA",
      `The backend did not start within the time limit.\n\n` +
        `A startup log was written to:\n${logPath()}\n\n` +
        `Please open that file (or share it) so the failure can be diagnosed.`
    );
    app.quit();
    return;
  }
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

function shutdown() {
  if (backend && backend.exitCode === null) backend.kill();
  if (ollama && ollama.exitCode === null) ollama.kill(); // leave pre-existing ollama alone (spawn no-ops if already up)
}
app.on("window-all-closed", () => { shutdown(); if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", shutdown);
process.on("exit", shutdown);
