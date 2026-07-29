// The contract that matters here is not "the numbers are right" — it is that the
// launcher can never be harmed by them. These tests pin the failure floor: an
// offline backend, a 500, a malformed payload and a full outage must all still
// produce a usable meta map (or an empty one), never a throw.
import { describe, it, expect, beforeEach, vi } from "vitest";
import { loadTileMeta, markTabUsed, resetTileMetaCache } from "./launcherStats";

const ok = (body) => ({ ok: true, json: async () => body });

// A backend where every probe succeeds with a non-empty result.
function happyFetch() {
  return vi.fn(async (url) => {
    if (url.includes("/workspace/list")) return ok({ entries: [
      { name: "a", type: "dir" }, { name: "b", type: "dir" }, { name: "x.md", type: "file" },
    ]});
    if (url.includes("/tasks/status")) return ok({ queue_depth: 2, tasks: [
      { status: "running" }, { status: "pending" }, { status: "pending" },
    ]});
    if (url.includes("/goals"))      return ok({ goals: [{ id: 1 }] });
    if (url.includes("/runs"))       return ok({ runs: new Array(50).fill({}) });
    if (url.includes("/memory/stats")) return ok({ total: 1240 });
    if (url.includes("/documents"))  return ok({ documents: [{}, {}, {}] });
    return ok({});
  });
}

beforeEach(() => {
  localStorage.clear();
  resetTileMetaCache();
  vi.useRealTimers();
});

describe("live counts", () => {
  it("labels each countable tab, pluralising and compacting", async () => {
    global.fetch = happyFetch();
    const m = await loadTileMeta();

    expect(m.prompt.label).toBe("2 prompts");
    expect(m.goals.label).toBe("1 goal");          // singular, not "1 goals"
    expect(m.memory.label).toBe("1.2k memories");  // compacted + irregular plural
    expect(m.library.label).toBe("3 documents");
  });

  it("marks an in-flight count as live and prefers it over the queue", async () => {
    global.fetch = happyFetch();
    const m = await loadTileMeta();
    expect(m.tasks).toEqual({ label: "1 running", live: true });
  });

  it("reports a capped page as a floor, not an exact count", async () => {
    global.fetch = happyFetch();
    const m = await loadTileMeta();
    expect(m.runs.label).toBe("50+ runs");
  });

  it("omits a tab whose count is zero rather than printing '0'", async () => {
    global.fetch = vi.fn(async () => ok({ entries: [], tasks: [], goals: [], runs: [], documents: [], total: 0 }));
    const m = await loadTileMeta();
    expect(m).toEqual({});
  });
});

describe("failure tolerance", () => {
  it("keeps the surviving probes when one endpoint dies", async () => {
    const base = happyFetch();
    global.fetch = vi.fn(async (url) => {
      if (url.includes("/memory/stats")) throw new Error("ECONNREFUSED");
      if (url.includes("/documents")) return { ok: false, status: 500 };
      return base(url);
    });
    const m = await loadTileMeta();

    expect(m.memory).toBeUndefined();
    expect(m.library).toBeUndefined();
    expect(m.prompt.label).toBe("2 prompts");   // unaffected neighbours survive
  });

  it("resolves rather than throws when every probe fails", async () => {
    global.fetch = vi.fn(async () => { throw new Error("offline"); });
    await expect(loadTileMeta()).resolves.toEqual({});
  });

  it("survives a malformed payload", async () => {
    global.fetch = vi.fn(async () => ok(null));
    await expect(loadTileMeta()).resolves.toEqual({});
  });

  it("skips the network when offline but still reports last-used", async () => {
    global.fetch = vi.fn();
    localStorage.setItem("launcher_last_used_v1", JSON.stringify({ skills: Date.now() - 7200_000 }));
    const m = await loadTileMeta({ online: false });
    expect(global.fetch).not.toHaveBeenCalled();
    expect(m.skills.label).toBe("used 2h ago");
  });
});

describe("last used", () => {
  it("renders a coarse age and drops anything under a minute", async () => {
    global.fetch = vi.fn(async () => ok({}));
    const now = Date.now();
    localStorage.setItem("launcher_last_used_v1", JSON.stringify({
      skills:   now - 10_000,        // just now → says nothing
      timeline: now - 3 * 3600_000,  // 3h
      concepts: now - 2 * 864e5,     // 2d
      about:    now - 30 * 864e5,    // a month → no longer "recent"
    }));
    const m = await loadTileMeta();

    expect(m.skills).toBeUndefined();
    expect(m.timeline.label).toBe("used 3h ago");
    expect(m.concepts.label).toBe("used 2d ago");
    expect(m.about).toBeUndefined();
  });

  it("yields to a live count on the same tile", async () => {
    global.fetch = happyFetch();
    localStorage.setItem("launcher_last_used_v1", JSON.stringify({ tasks: Date.now() - 7200_000 }));
    const m = await loadTileMeta();
    expect(m.tasks.label).toBe("1 running");
  });

  it("never throws when storage is unavailable", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => markTabUsed("chat")).not.toThrow();
    spy.mockRestore();
  });
});

describe("caching", () => {
  it("serves a second open from cache instead of re-probing", async () => {
    global.fetch = happyFetch();
    await loadTileMeta();
    const first = global.fetch.mock.calls.length;
    await loadTileMeta();
    expect(global.fetch.mock.calls.length).toBe(first);
  });

  it("does not memoize a failed fan-out, so the grid fills once the API is up", async () => {
    global.fetch = vi.fn(async () => { throw new Error("still booting"); });
    expect(await loadTileMeta()).toEqual({});

    global.fetch = happyFetch();
    const m = await loadTileMeta();   // same 30s window, but the miss wasn't cached
    expect(m.prompt.label).toBe("2 prompts");
  });

  it("coalesces concurrent opens onto one fan-out", async () => {
    global.fetch = happyFetch();
    await Promise.all([loadTileMeta(), loadTileMeta(), loadTileMeta()]);
    // One probe per countable tab, not three.
    expect(global.fetch.mock.calls.length).toBe(6);
  });
});
