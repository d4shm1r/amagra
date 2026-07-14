// Single source for the backend base URL.
//
// Every tab used to hardcode `http://localhost:8000`. Centralizing it here lets
// the dashboard point at a non-local host (a deployed workspace, a tunnel) via
// the `VITE_API_BASE` build-time env, and gives v1.6 one chokepoint to thread a
// per-workspace namespace through (see docs/design/PROMPT_ARTIFACT_CONTRACT.md, #69).
//
// Packaged shells (Electron, AppImage, Docker single-process) serve the built UI
// FROM the backend on one port, so a relative base ("") is same-origin by
// construction — no CORS, and immune to localhost-vs-127.0.0.1 host mismatches
// (the v1.7.x Windows launcher bug class). Only the Vite dev server (:3000)
// runs the UI on a different origin than the API.
const isViteDev = typeof window !== "undefined" && window.location.port === "3000";
export const API = import.meta.env?.VITE_API_BASE || (isViteDev ? "http://localhost:8000" : "");

// Alias for the couple of call sites that named it API_BASE.
export const API_BASE = API;
