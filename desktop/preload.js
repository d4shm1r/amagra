// Minimal, safe preload. contextIsolation is on, so nothing from Node leaks into
// the page. Exposed only as a hook for future desktop-only affordances (native
// menus, file dialogs, tray) without opening the whole ipc surface.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("amagra", {
  desktop: true,
  platform: process.platform,
});
