// usePoll — one fetch per endpoint, however many panels ask for it.
//
// The Cognition surface used to mount ~11 endpoints across five independent
// `setInterval`s, and two panels polled `/cos/events` concurrently on different
// cadences. Every tab switch remounted the lot and refetched everything, so the
// backend saw a burst on each nav and the panels disagreed about what "now" was.
//
// This is the shared subscription layer that fixes all three:
//
//   · ONE request per URL. Panels subscribe; the first mount starts the timer,
//     the last unmount stops it. Ten subscribers to `/cos/events` = one fetch.
//   · ONE cadence per URL — the shortest any live subscriber asked for, so a
//     10s feed stays live even when a 30s panel shares its data.
//   · Data OUTLIVES the unmount. Remounting shows the last snapshot instantly
//     and revalidates in the background, so switching tabs is not a refetch
//     storm and never flashes an empty panel.
//   · A failed poll KEEPS the previous data and surfaces `error` alongside it.
//     One flaky request should annotate a dashboard, not blank it.
//
// Paths are relative to the API base — `usePoll("/cos/events?n=200")`.
import { useCallback, useSyncExternalStore } from "react";
import { API } from "./api";

// url → entry. Module-level on purpose: the cache is the point, so it must
// outlive every component that reads it.
const cache = new Map();

const EMPTY = Object.freeze({ data: null, error: null, loading: true, fetchedAt: 0 });

// Long enough that a slow-but-working backend is not called dead, short enough
// that a hang is reported while the reader still connects it to what they did.
const DEFAULT_TIMEOUT = 10_000;

function entryFor(url) {
  let e = cache.get(url);
  if (!e) {
    e = { url, snap: EMPTY, subs: new Map(), timer: null, inflight: null, timeout: DEFAULT_TIMEOUT };
    cache.set(url, e);
  }
  return e;
}

// Snapshots are replaced, never mutated: useSyncExternalStore compares by
// identity, so an in-place edit would render stale forever.
function publish(e, next) {
  e.snap = { ...e.snap, ...next };
  e.subs.forEach((_, notify) => notify());
}

function fetchNow(e, timeout = DEFAULT_TIMEOUT) {
  // Coalesce: a refresh during an in-flight request joins it rather than
  // stacking a second identical call.
  if (e.inflight) return e.inflight;

  // A request that never settles would otherwise pin `loading` true forever —
  // a panel stuck on its spinner with no way to find out why, which is exactly
  // what a backend that has hung rather than crashed looks like. Bounded, so a
  // hang surfaces as an error the caller can render.
  e.inflight = fetch(`${API}${e.url}`, { signal: AbortSignal.timeout(timeout) })
    .then(r => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.json();
    })
    .then(data => publish(e, { data, error: null, loading: false, fetchedAt: Date.now() }))
    // Keep `data` as-is — a transient failure annotates the panel, it doesn't
    // empty it. `loading` clears either way so spinners always resolve.
    .catch(err => publish(e, { error: err.message, loading: false, fetchedAt: Date.now() }))
    .finally(() => { e.inflight = null; });

  return e.inflight;
}

// The live cadence is the shortest any current subscriber wants. Recomputed on
// every subscribe/unsubscribe so a 10s panel unmounting relaxes the shared
// timer back to the 30s its neighbours asked for.
function retime(e) {
  if (e.timer) { clearInterval(e.timer); e.timer = null; }
  if (e.subs.size === 0) return;
  const ms = Math.min(...e.subs.values());
  if (Number.isFinite(ms) && ms > 0) e.timer = setInterval(() => fetchNow(e, e.timeout), ms);
}

/** Subscribe to a polled endpoint.
 *
 *  @param path     API-relative path, e.g. "/cos/uci/hierarchical". Falsy skips
 *                  the fetch entirely (for conditional panels).
 *  @param interval poll period in ms. `0` fetches once and never repeats.
 *  @param timeout  abort and report an error after this many ms.
 *  @returns { data, error, loading, refresh } */
export function usePoll(path, { interval = 30_000, timeout = DEFAULT_TIMEOUT } = {}) {
  const subscribe = useCallback((notify) => {
    if (!path) return () => {};
    const e = entryFor(path);
    e.timeout = timeout;
    e.subs.set(notify, interval);
    retime(e);

    // Revalidate on mount only if the cached snapshot is older than this
    // subscriber's cadence — an immediate remount reuses what's already there.
    const age = Date.now() - e.snap.fetchedAt;
    if (!e.snap.fetchedAt || age > interval) fetchNow(e, timeout);

    return () => {
      e.subs.delete(notify);
      retime(e);
    };
  }, [path, interval, timeout]);

  const getSnapshot = useCallback(
    () => (path ? entryFor(path).snap : EMPTY),
    [path],
  );

  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  const refresh = useCallback(() => {
    if (path) fetchNow(entryFor(path), timeout);
  }, [path, timeout]);

  return { ...snap, refresh };
}

/** Refetch every endpoint that currently has a subscriber — what a page-level
 *  "Refresh" button calls. Endpoints nobody is watching stay untouched. */
export function refreshAll() {
  cache.forEach(e => { if (e.subs.size > 0) fetchNow(e, e.timeout); });
}

/** Test seam: drop all cached data and timers. */
export function __resetPollCache() {
  cache.forEach(e => { if (e.timer) clearInterval(e.timer); });
  cache.clear();
}
