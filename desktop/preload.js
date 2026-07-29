// Minimal, safe preload. contextIsolation is on, so nothing from Node leaks into
// the page. Exposed only as a hook for desktop-only affordances (native menus,
// file dialogs, tray) without opening the whole ipc surface.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("amagra", {
  desktop: true,
  platform: process.platform,

  // Window controls. Linux only in practice: macOS keeps its native traffic
  // lights and Windows keeps the native overlay, so only the Linux window is
  // fully frameless and has to draw its own buttons (see main.js CONTROLS_JS).
  //
  // Three one-way sends and one query — deliberately not a general "call any
  // window method" bridge, which would hand the page control of the shell.
  // `onMaximizeChange` lets the injected buttons swap the maximize glyph for a
  // restore glyph without polling.
  window: {
    minimize: () => ipcRenderer.send("amagra:win-minimize"),
    toggleMaximize: () => ipcRenderer.send("amagra:win-toggle-maximize"),
    close: () => ipcRenderer.send("amagra:win-close"),
    isMaximized: () => ipcRenderer.invoke("amagra:win-is-maximized"),
    onMaximizeChange: (fn) => {
      // Wrap so the page never receives the IpcRendererEvent itself.
      ipcRenderer.on("amagra:win-maximized", (_e, maximized) => fn(maximized));
    },
  },
});
