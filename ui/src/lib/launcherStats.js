// ── launcherStats ─────────────────────────────────────────────────────────────
// The contextual line at the foot of each launcher tile — "18 prompts",
// "3 running", "used 2h ago". It is what turns the menu from a list of
// destinations into a command center: the grid reports the state of the system
// instead of just naming its rooms.
//
// Two independent sources, and the split is the whole design:
//
//   · LIVE COUNTS come from the API — one batched fan-out per launcher open,
//     cached for CACHE_MS so re-opening the menu twice in a row doesn't re-hit
//     six endpoints. Only a handful of tabs have a number worth showing.
//   · LAST USED is local (localStorage) and needs no network at all. It covers
//     every tile, including the ~20 with nothing countable behind them, and it
//     is what makes the rest of the grid feel lived-in rather than inert.
//
// Live wins where both exist: "3 running" says more than "used 2h ago".
//
// Nothing here may throw into the launcher, and nothing here may delay it. The
// metadata is decoration — a menu that failed to open because a stats call 500'd
// would be a bad trade for a subtitle. Every probe swallows its own errors and
// contributes nothing on failure, so an offline backend degrades to a grid that
// shows only last-used, which is exactly the graceful floor we want.
import { API } from "@/lib/api";

const LS_USED  = "launcher_last_used_v1";
const CACHE_MS = 30_000;

// ── last used (local, no network) ─────────────────────────────────────────────

function readUsed() {
  try { return JSON.parse(localStorage.getItem(LS_USED) || "{}"); }
  catch { return {}; }
}

// Called on every navigation out of the launcher. Cheap enough to do inline.
export function markTabUsed(tabId) {
  if (!tabId) return;
  try {
    const used = readUsed();
    used[tabId] = Date.now();
    localStorage.setItem(LS_USED, JSON.stringify(used));
  } catch { /* private mode / quota — last-used is a nicety, never a dependency */ }
}

// Deliberately coarse: "2h ago" is the useful resolution for "was I just here?".
// Anything under a minute reads as the current session and says nothing, so it
// is dropped rather than rendered as "used 0m ago".
function agoLabel(ts) {
  const s = (Date.now() - ts) / 1000;
  if (!isFinite(s) || s < 0) return null;
  if (s < 90) return null;
  if (s < 3600)    return `used ${Math.floor(s / 60)}m ago`;
  if (s < 86400)   return `used ${Math.floor(s / 3600)}h ago`;
  if (s < 7 * 864e2) return `used ${Math.floor(s / 86400)}d ago`;
  return null;   // older than a week is not "recent" — say nothing
}

// ── live counts ───────────────────────────────────────────────────────────────

const compact = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
const plural  = (n, one, many = `${one}s`) => `${compact(n)} ${n === 1 ? one : many}`;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

// One probe per tab that has something countable behind it, keyed by the tab id
// from navConfig. Each resolves to { label, live? } or null, where `live: true`
// marks a number that is currently in motion (a pulsing dot rides alongside it).
// A null, a throw, a 404 and a zero all mean the same thing: this tile has
// nothing to say right now, so it says nothing.
const PROBES = {
  prompt: async () => {
    const d = await getJSON(`${API}/workspace/list?path=prompts`);
    const n = (d?.entries || []).filter((e) => e.type === "dir").length;
    return n ? { label: plural(n, "prompt") } : null;
  },
  tasks: async () => {
    const d = await getJSON(`${API}/tasks/status`);
    const rows    = d?.tasks || [];
    const running = rows.filter((t) => t.status === "running").length;
    // Running is the live fact; a queue with nothing running falls back to depth.
    if (running) return { label: `${running} running`, live: true };
    const pending = d?.queue_depth ?? rows.filter((t) => t.status === "pending").length;
    if (pending) return { label: `${pending} queued` };
    return rows.length ? { label: plural(rows.length, "task") } : null;
  },
  goals: async () => {
    const d = await getJSON(`${API}/goals?limit=30`);
    const n = (d?.goals || []).length;
    return n ? { label: plural(n, "goal") } : null;
  },
  runs: async () => {
    const d = await getJSON(`${API}/runs?limit=50`);
    const n = (d?.runs || []).length;
    // The endpoint is capped, so a full page means "at least this many".
    return n ? { label: `${n >= 50 ? "50+" : n} runs` } : null;
  },
  memory: async () => {
    const d = await getJSON(`${API}/memory/stats`);
    const n = d?.total ?? 0;
    return n ? { label: plural(n, "memory", "memories") } : null;
  },
  library: async () => {
    const d = await getJSON(`${API}/documents`);
    const n = (d?.documents || []).length;
    return n ? { label: plural(n, "document") } : null;
  },
};

let cache    = { at: 0, data: null };
let inflight = null;

// Fan out every probe at once and keep whatever comes back. `allSettled`, not
// `all` — one dead endpoint must not blank the other five.
async function fetchLive() {
  const keys    = Object.keys(PROBES);
  const settled = await Promise.allSettled(keys.map((k) => PROBES[k]()));
  const out = {};
  settled.forEach((r, i) => {
    if (r.status === "fulfilled" && r.value) out[keys[i]] = r.value;
  });
  return out;
}

// Returns { [tabId]: { label, live? } } for every tile that has something to
// report. Resolves from cache when fresh, and coalesces concurrent callers onto
// a single fan-out so a double-open doesn't double the traffic.
export async function loadTileMeta({ online = true } = {}) {
  const used = readUsed();
  const base = {};
  for (const [tabId, ts] of Object.entries(used)) {
    const label = agoLabel(ts);
    if (label) base[tabId] = { label };
  }
  if (!online) return base;

  let live = {};
  try {
    if (cache.data && Date.now() - cache.at < CACHE_MS) {
      live = cache.data;
    } else {
      inflight = inflight || fetchLive().finally(() => { inflight = null; });
      live = await inflight;
      // An empty fan-out is the signature of a backend that is down or still
      // booting, not of a genuinely empty install — memoizing it would blank the
      // grid for a further CACHE_MS after the API comes up. Cache only a result
      // that actually said something.
      if (Object.keys(live).length) cache = { at: Date.now(), data: live };
    }
  } catch { /* keep the last-used floor */ }

  return { ...base, ...live };
}

// Test seam / manual refresh: drop the memo so the next open re-probes.
export function resetTileMetaCache() {
  cache = { at: 0, data: null };
  inflight = null;
}
