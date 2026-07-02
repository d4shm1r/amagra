// promptStore.js — file-backed persistence for the Prompt editor (#69).
//
// Prompts used to live only in browser localStorage (`prompt_editor_v1`), so they
// were neither first-class, versioned, nor portable. This module persists them as
// real files under the workspace via the jailed /workspace/* write API (#68),
// giving the layout from docs/design/PROMPT_ARTIFACT_CONTRACT.md:
//
//   prompts/<slug>/
//     prompt.json            { slug, title, head, current_version, updated }
//     versions/vN.prompt     snapshot text for version N
//     versions/vN.meta.json  { version, variables, parent, created }
//     runs/                  (responses land here in #70)
//
// Save model: autosave keeps the working `head` in prompt.json (debounced by the
// caller); an explicit save commits a new immutable version under versions/.
//
// Every call degrades gracefully — if the backend is unreachable the editor keeps
// working off localStorage, so a down API never costs the user their draft.

import { API } from "./api";

const PROMPTS_DIR = "prompts";
export const LS_KEY = "prompt_editor_v1";
const MIGRATED_FLAG = "prompt_editor_migrated_v1";

// ── /workspace/* helpers ─────────────────────────────────────────────────────

async function wsRead(path) {
  const r = await fetch(`${API}/workspace/read?path=${encodeURIComponent(path)}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`read ${path}: ${r.status}`);
  return (await r.json()).content;
}

async function wsList(path = "") {
  const r = await fetch(`${API}/workspace/list?path=${encodeURIComponent(path)}`);
  if (r.status === 404) return [];
  if (!r.ok) throw new Error(`list ${path}: ${r.status}`);
  return (await r.json()).entries || [];
}

async function wsWrite(path, content) {
  const r = await fetch(`${API}/workspace/write`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
  if (!r.ok) throw new Error(`write ${path}: ${r.status}`);
  return r.json();
}

// ── pure helpers (also reused by the AST/variables work in #71) ───────────────

export function slugify(title) {
  const base = String(title || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return base || "untitled";
}

// Extract distinct {{variable}} names, in first-seen order.
export function extractVariables(content) {
  const seen = [];
  const re = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_.-]*)\s*\}\}/g;
  let m;
  while ((m = re.exec(String(content || ""))) !== null) {
    if (!seen.includes(m[1])) seen.push(m[1]);
  }
  return seen;
}

function descriptorPath(slug) { return `${PROMPTS_DIR}/${slug}/prompt.json`; }

// ── prompt-project CRUD ───────────────────────────────────────────────────────

// List every prompt project as { slug, title, head, current_version }.
export async function listPrompts() {
  const dirs = (await wsList(PROMPTS_DIR)).filter((e) => e.type === "dir");
  const out = [];
  for (const d of dirs) {
    try {
      const raw = await wsRead(descriptorPath(d.name));
      if (!raw) continue;
      const meta = JSON.parse(raw);
      out.push({
        slug: d.name,
        title: meta.title || d.name,
        head: meta.head ?? "",
        current_version: meta.current_version ?? 0,
      });
    } catch { /* skip a malformed project rather than break the whole load */ }
  }
  return out;
}

// Persist the working copy (autosave). Creates the project on first write.
export async function saveHead(slug, { title, content }) {
  const prev = await readDescriptor(slug);
  const descriptor = {
    slug,
    title: title ?? prev?.title ?? slug,
    head: content ?? "",
    current_version: prev?.current_version ?? 0,
    updated: stamp(),
  };
  await wsWrite(descriptorPath(slug), JSON.stringify(descriptor, null, 2));
  return descriptor;
}

// Commit an immutable snapshot: versions/vN.prompt + vN.meta.json, bump pointer.
export async function saveVersion(slug, { title, content }) {
  const prev = await readDescriptor(slug);
  const n = (prev?.current_version ?? 0) + 1;
  const vars = extractVariables(content);
  await wsWrite(`${PROMPTS_DIR}/${slug}/versions/v${n}.prompt`, content ?? "");
  await wsWrite(
    `${PROMPTS_DIR}/${slug}/versions/v${n}.meta.json`,
    JSON.stringify(
      { version: n, variables: vars, parent: prev?.current_version ?? null, created: stamp() },
      null, 2,
    ),
  );
  const descriptor = {
    slug,
    title: title ?? prev?.title ?? slug,
    head: content ?? "",
    current_version: n,
    updated: stamp(),
  };
  await wsWrite(descriptorPath(slug), JSON.stringify(descriptor, null, 2));
  return { version: n, variables: vars, descriptor };
}

// List committed version numbers for a prompt, ascending. [] if none / backend down.
export async function listVersions(slug) {
  try {
    const entries = await wsList(`${PROMPTS_DIR}/${slug}/versions`);
    const nums = [];
    for (const e of entries) {
      const m = /^v(\d+)\.prompt$/.exec(e.name);
      if (m) nums.push(Number(m[1]));
    }
    return nums.sort((a, b) => a - b);
  } catch { return []; }
}

// Read the text of one committed version (null if missing / backend down).
export async function readVersion(slug, n) {
  try { return await wsRead(`${PROMPTS_DIR}/${slug}/versions/v${n}.prompt`); }
  catch { return null; }
}

// The committed version number this prompt currently points at (0 = none yet).
export async function currentVersion(slug) {
  const d = await readDescriptor(slug);
  return d?.current_version ?? 0;
}

// Stable id linking a run/decision to the PromptVersion that produced it (#70).
// "<slug>@vN", or "<slug>@head" when nothing has been committed yet.
export function promptVersionId(slug, n) {
  return `${slug}@${n ? `v${n}` : "head"}`;
}

// Persist a model run's chosen output next to its prompt (#70):
//   prompts/<slug>/runs/R<ts>.response.json = { prompt_version_id, output, model, metrics, trace_ref }
// Best-effort; returns the file path or null if the backend is unreachable.
export async function saveRun(slug, { prompt_version_id, output, model, metrics, trace_ref }) {
  try {
    const id = `R${Date.now()}`;
    const path = `${PROMPTS_DIR}/${slug}/runs/${id}.response.json`;
    await wsWrite(path, JSON.stringify(
      { id, prompt_version_id: prompt_version_id ?? null, output: output ?? "",
        model: model ?? "", metrics: metrics ?? null, trace_ref: trace_ref ?? null,
        created: stamp() },
      null, 2,
    ));
    return path;
  } catch { return null; }
}

async function readDescriptor(slug) {
  try {
    const raw = await wsRead(descriptorPath(slug));
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function stamp() { return new Date().toISOString(); }

// ── one-time migration: localStorage tabs → prompt files ──────────────────────

// Imports existing `prompt_editor_v1` tabs into prompt projects, once. Returns the
// number imported (0 if already migrated, nothing to import, or the backend is down).
// Idempotent: guarded by a localStorage flag and never throws into the caller.
export async function importFromLocalStorage() {
  try {
    if (localStorage.getItem(MIGRATED_FLAG)) return 0;
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) { localStorage.setItem(MIGRATED_FLAG, "1"); return 0; }
    const { tabs } = JSON.parse(raw);
    if (!Array.isArray(tabs) || tabs.length === 0) {
      localStorage.setItem(MIGRATED_FLAG, "1");
      return 0;
    }
    const used = new Set();
    let count = 0;
    for (const t of tabs) {
      const content = t.content ?? "";
      if (!content.trim()) continue;          // don't import empty scratch tabs
      let slug = slugify(t.title);
      while (used.has(slug)) slug = `${slug}-1`;
      used.add(slug);
      await saveHead(slug, { title: t.title, content });
      await saveVersion(slug, { title: t.title, content });
      count += 1;
    }
    localStorage.setItem(MIGRATED_FLAG, "1");   // only set on full success
    return count;
  } catch {
    return 0;   // backend down / parse error — try again next load, editor unaffected
  }
}
