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

const { app, BrowserWindow, Menu, shell, ipcMain } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const fs = require("fs");

const PORT = parseInt(process.env.AMAGRA_PORT || "8000", 10);
// Renderer origin: keep `localhost` (not 127.0.0.1) so the window matches the UI's
// default API base (ui/src/lib/api.js → http://localhost:8000) and stays same-origin:
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

// Liveness probe. We intentionally hit "/" (the served UI root), NOT "/health":
//   • "/" is a cheap static index.html read (JSON when no UI is bundled) — always
//     200 the instant the server can accept connections, and it's exactly what
//     win.loadURL() needs to succeed, so it tests the thing that actually matters.
//   • "/health" does blocking work on EVERY call — a urllib probe of Ollama
//     (http://localhost:11434, timeout=2s) plus cold lazy-imports of the memory/
//     UCI modules. On Windows, unpacking a PyInstaller onefile into a Defender-
//     scanned %TEMP% pushed /health past the old 1s probe timeout on every call,
//     so a perfectly healthy server never passed the loop → the 120s "did not
//     start" dialog fired while the app worked fine in a browser.
// The 5s timeout is generous headroom over "/"'s sub-ms response, not a crutch.
function healthy() {
  return new Promise((resolve) => {
    const req = http.get(`${PROBE}/`, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(5000, () => { req.destroy(); resolve(false); });
  });
}

// A frozen onefile sidecar unpacks to %TEMP%/_MEIxxxx on every launch, and a
// fresh Windows Defender install scans every extracted file — cold first-launch
// can run well past a minute. Give it room before declaring failure.
async function waitForHealth(timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await healthy()) return true;
    // The backend we spawned has exited — normally a boot failure, so stop
    // looping for the full 120s. But the most common early-exit cause is
    // EADDRINUSE: the port was already held by a healthy server (a prior AMAGRA
    // instance, or `ai-start`) that our single reuse probe happened to miss.
    // Re-probe once before giving up so we ADOPT that server instead of raising
    // a spurious "did not start" dialog over an app that's actually working.
    if (backend && backend.exitCode !== null) return healthy();
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
  // Force UTF-8 for the backend process. Windows defaults to a legacy code page
  // (cp1252) for both console output AND file I/O, so the app's emoji/unicode
  // logging and any implicitly-encoded file read would crash on a box that was
  // developed on Linux. PYTHONUTF8=1 flips the whole interpreter to UTF-8 mode.
  env.PYTHONUTF8 = "1";
  env.PYTHONIOENCODING = "utf-8";
  // Mark each launch in the logfile so stale entries from a previous crashed run
  // aren't mistaken for the current one (the log is append-mode for crash history).
  try {
    fs.writeSync(logFd(), `\n===== AMAGRA backend launch ${new Date().toISOString()} =====\n`);
  } catch {}
  // Capture the sidecar's stdout+stderr to a logfile instead of discarding it
  // (stdio:"ignore"), so a boot failure leaves a diagnosable trail rather than a
  // silent "did not become healthy". The dialog below points the user here.
  // windowsHide: the frozen sidecar is a PyInstaller console app, so on Windows
  // spawning it pops a stray `cmd`/console window next to (or instead of) the
  // Electron shell. We already capture its stdout+stderr to the logfile, so the
  // console is pure noise — suppress it. No effect on macOS/Linux.
  backend = spawn(cmd, args, { cwd, stdio: ["ignore", logFd(), logFd()], env, windowsHide: true });
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

// ── rounded window corners ────────────────────────────────────
// Only Linux. The other two platforms already do this, and forcing it there
// would cost more than it buys:
//   · macOS rounds every frameless window itself, and a transparent window
//     loses the native shadow and the traffic-light hit regions.
//   · Windows 11's DWM rounds all top-level windows; going transparent opts the
//     window out of the native shadow and Snap Layouts.
// Linux compositors don't round anything, which is where the sharp corners come
// from. Rounding needs `transparent: true` — the corner has to be genuinely
// see-through, and CSS alone cannot do it because the page is clipped to the
// window rect the compositor draws.
const ROUND_CORNERS = process.platform === "linux";
const CORNER_RADIUS = 12;

// Applied by toggling a class, not by inserting and removing stylesheets — the
// class survives navigations and costs one executeJavaScript per window-state
// change instead of a stylesheet churn.
//
// body::after is in here for a reason that is easy to miss: it is the app's
// paper-grain overlay, and it is `position: fixed`. Fixed elements are NOT
// clipped by an ancestor's overflow/border-radius, so without its own radius it
// would paint the one square thing left in each corner.
// The non-obvious part is which element carries the cream.
//
// CSS propagates the ROOT background to the canvas: when html has no background
// of its own the browser takes BODY's and paints it across the entire window,
// and that painting is not clipped by anyone's border-radius. So making only
// html transparent achieves exactly nothing — body's cream still fills all four
// corners, which is precisely what a pixel probe of the running window showed
// (corner read 240,234,222 = the canvas colour, not the desktop behind it).
//
// Both html and body therefore go transparent, and the cream moves to #root —
// the first element in the tree that is actually clipped by its own radius.
const CORNER_CSS = `
  html.amagra-round, html.amagra-round body, html.amagra-round #root {
    border-radius: ${CORNER_RADIUS}px;
    overflow: hidden;
  }
  html.amagra-round, html.amagra-round body { background: transparent !important; }
  html.amagra-round #root { background: var(--app-bg, #F0E9DF); }
  html.amagra-round body::after { border-radius: ${CORNER_RADIUS}px; }
`;

// Window controls for the frameless Linux window, injected from the shell rather
// than added to the React UI — same rule as the drag region below: the browser
// and dev-server builds must not grow a set of buttons that do nothing there.
//
// Drawn, not glyphs: ─ □ ✕ as characters come from whatever font the machine has,
// so each one lands on its own baseline at its own weight. These are three tiny
// SVGs on one 10px grid with one 1.3px stroke, which is the same argument the UI
// makes for its own icon set (components/ui/Icon.jsx).
//
// Idempotent: re-running removes the old bar first, so a reload cannot stack two.
const CONTROLS_JS = `(() => {
  const OLD = document.getElementById("amagra-winctl");
  if (OLD) OLD.remove();
  if (!window.amagra || !window.amagra.window) return "no-bridge";

  const svg = (d) =>
    '<svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" ' +
    'stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>';
  const MIN  = svg('<path d="M1.5 5h7"/>');
  const MAX  = svg('<rect x="1.6" y="1.6" width="6.8" height="6.8" rx="1.4"/>');
  const REST = svg('<rect x="1.4" y="3.1" width="5.5" height="5.5" rx="1.2"/><path d="M3.4 3.1V2.3a.9.9 0 0 1 .9-.9h3.4a.9.9 0 0 1 .9.9v3.4a.9.9 0 0 1-.9.9h-.8"/>');
  const CLOSE = svg('<path d="M2 2l6 6M8 2l-6 6"/>');

  const bar = document.createElement("div");
  bar.id = "amagra-winctl";
  bar.style.cssText = [
    "position:fixed", "top:7px", "right:9px", "z-index:2147483646",
    "display:flex", "gap:2px", "-webkit-app-region:no-drag",
    "font-family:inherit",
  ].join(";");

  const mk = (html, label, onClick, danger) => {
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = html;
    b.setAttribute("aria-label", label);
    b.title = label;
    b.style.cssText = [
      "width:26px", "height:26px", "display:inline-flex",
      "align-items:center", "justify-content:center",
      "border:none", "border-radius:8px", "background:transparent",
      "color:#8A5A00", "cursor:pointer", "padding:0",
      "-webkit-app-region:no-drag",
      "transition:background 150ms ease-out, color 150ms ease-out",
    ].join(";");
    // Hover: the same gold tint the app uses for a soft hover, and the one red
    // in the palette (T.error) for close — the single control you cannot undo.
    b.addEventListener("mouseenter", () => {
      b.style.background = danger ? "#B4231814" : "rgba(196,136,8,0.12)";
      b.style.color = danger ? "#B42318" : "#6C4C00";
    });
    b.addEventListener("mouseleave", () => {
      b.style.background = "transparent";
      b.style.color = "#8A5A00";
    });
    b.addEventListener("click", onClick);
    return b;
  };

  const w = window.amagra.window;
  const minBtn = mk(MIN, "Minimize", () => w.minimize());
  const maxBtn = mk(MAX, "Maximize", () => w.toggleMaximize());
  const clsBtn = mk(CLOSE, "Close", () => w.close(), true);

  const paint = (maximized) => {
    maxBtn.innerHTML = maximized ? REST : MAX;
    const label = maximized ? "Restore" : "Maximize";
    maxBtn.setAttribute("aria-label", label);
    maxBtn.title = label;
  };
  w.isMaximized().then(paint).catch(() => {});
  w.onMaximizeChange(paint);

  bar.append(minBtn, maxBtn, clsBtn);
  document.body.appendChild(bar);
  return "ok";
})()`;

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: "AMAGRA",
    // Cream so there is no white flash on load (see DESIGN_PRINCIPLES.md). When
    // the window is transparent that job moves to the page's own background: an
    // opaque backgroundColor here would paint a square cream rect behind the
    // rounded page and put the sharp corners straight back.
    ...(ROUND_CORNERS
      ? { transparent: true, backgroundColor: "#00000000" }
      : { backgroundColor: "#F0E9DF" }),
    icon: path.join(REPO_ROOT, "ui", "public", "logo512.png"),
    // Branded top bar. Three different answers, one per platform:
    //
    //  · macOS — native inset bar. The traffic lights sit top-left, exactly where
    //    the ☰ launcher lives (App.jsx: top 13 / left 15), so leave it alone.
    //  · Windows — hidden title bar + the native Window Controls Overlay painted
    //    in Gilded Calm. The overlay is drawn by Chromium OUTSIDE the page, which
    //    is fine here because DWM is rounding the window for us anyway.
    //  · Linux — fully frameless, and the app draws its own controls (CONTROLS_JS).
    //    It has to: that same native overlay is an opaque rectangle no CSS can
    //    clip, so with it enabled the top-right corner stayed square while the
    //    other three rounded. Owning the buttons is the price of four corners.
    ...(process.platform === "darwin" ? {}
      : ROUND_CORNERS
        ? { frame: false }
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
  // Round only when the window is floating. A maximized or fullscreen window is
  // flush against the screen edge, and a radius there just carves four notches
  // out of the desktop — every polished app squares off at that point.
  if (ROUND_CORNERS) {
    // Latched, so "resize" can be in the listener list below without firing an
    // executeJavaScript on every pixel of a drag — the round/square state changes
    // a handful of times in a session, not a thousand.
    let lastRound = null;
    const syncCorners = () => {
      if (!win || win.isDestroyed()) return;
      const round = !win.isMaximized() && !win.isFullScreen();
      if (round === lastRound) return;
      lastRound = round;
      win.webContents
        .executeJavaScript(`document.documentElement.classList.toggle("amagra-round", ${round})`)
        .catch(() => {});
    };
    win.webContents.on("did-finish-load", () => {
      lastRound = null;   // a reload drops the class, so re-assert it
      win.webContents.insertCSS(CORNER_CSS).then(syncCorners).catch(() => {});
    });
    // "resize" is in here deliberately. Electron documents enter/leave-full-screen
    // as macOS+Windows, and on Linux a tiling WM or a keyboard maximize often
    // changes the window state without emitting the specific event — but it always
    // resizes. The latch above makes the extra firings free.
    for (const ev of ["maximize", "unmaximize", "restore", "resize",
                      "enter-full-screen", "leave-full-screen"]) {
      win.on(ev, syncCorners);
    }

    // The window is frameless on this path, so the page owns min/max/close.
    win.webContents.on("did-finish-load", () => {
      win.webContents.executeJavaScript(CONTROLS_JS).catch(() => {});
    });
    // Keep the maximize glyph honest when the state changes from outside the
    // buttons — a double-clicked drag region, a WM keybinding, a tiling snap.
    const pushMaxState = () => {
      if (!win || win.isDestroyed()) return;
      win.webContents.send("amagra:win-maximized", win.isMaximized());
    };
    for (const ev of ["maximize", "unmaximize", "restore"]) win.on(ev, pushMaxState);
  }

  win.loadURL(UI_URL);
  win.on("closed", () => { win = null; });
}

// Window-control IPC for the frameless Linux window. Registered once, and every
// handler resolves the window from the SENDER rather than the module-level `win`,
// so a control can never act on a window other than the one it was clicked in.
ipcMain.on("amagra:win-minimize", (e) => BrowserWindow.fromWebContents(e.sender)?.minimize());
ipcMain.on("amagra:win-close",    (e) => BrowserWindow.fromWebContents(e.sender)?.close());
ipcMain.on("amagra:win-toggle-maximize", (e) => {
  const w = BrowserWindow.fromWebContents(e.sender);
  if (!w) return;
  if (w.isMaximized()) w.unmaximize(); else w.maximize();
});
ipcMain.handle("amagra:win-is-maximized", (e) =>
  BrowserWindow.fromWebContents(e.sender)?.isMaximized() ?? false);

async function startup() {
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
}

// Single-instance guard: a second double-click must NOT spawn a competing
// backend — that's the port-8000 bind conflict ("only one usage of each socket
// address is normally permitted"). Bounce the duplicate and just focus the
// window the first instance already opened.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
  app.whenReady().then(startup);
}

function shutdown() {
  if (backend && backend.exitCode === null) {
    // A PyInstaller onefile exe runs a bootloader parent that unpacks and spawns
    // the real Python child; on Windows `backend.kill()` reaps only the parent,
    // leaving the child holding port 8000 (→ EADDRINUSE on the next launch). Kill
    // the whole tree so the port is actually released.
    if (process.platform === "win32") {
      try {
        spawn("taskkill", ["/pid", String(backend.pid), "/T", "/F"], { stdio: "ignore" });
      } catch {
        backend.kill();
      }
    } else {
      backend.kill();
    }
  }
  if (ollama && ollama.exitCode === null) ollama.kill(); // leave pre-existing ollama alone (spawn no-ops if already up)
}
app.on("window-all-closed", () => { shutdown(); if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", shutdown);
process.on("exit", shutdown);
// A terminal Ctrl+C or an OS-delivered SIGTERM/SIGHUP can kill the shell WITHOUT
// firing Electron's before-quit / window-all-closed — orphaning the spawned
// backend, which keeps holding port 8000 so the NEXT launch dies with EADDRINUSE
// (the recurring "port already in use" failure). Reap the child on these signals
// too, then quit through Electron's normal path so the taskkill/kill completes.
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => { shutdown(); app.quit(); });
}
