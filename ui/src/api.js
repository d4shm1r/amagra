// Single source for the backend base URL.
//
// Every tab used to hardcode `http://localhost:8000`. Centralizing it here lets
// the dashboard point at a non-local host (a deployed workspace, a tunnel) via
// the `VITE_API_BASE` build-time env, and gives v1.6 one chokepoint to thread a
// per-workspace namespace through (see docs/PROMPT_ARTIFACT_CONTRACT.md, #69).
export const API = import.meta.env?.VITE_API_BASE || "http://localhost:8000";

// Alias for the couple of call sites that named it API_BASE.
export const API_BASE = API;
