// constants.js mirrors two facts out of history.js as plain literals so that
// eager tabs never import the release record. Mirrors rot. These tests are the
// thing that stops them rotting: add a build phase or move the roadmap's "next"
// marker without updating constants.js and the suite goes red here.
import { describe, it, expect } from "vitest";
import { PHASE_COUNT, CURRENT_FOCUS } from "./constants";
import { BUILD_PHASES, ROADMAP } from "./history";

describe("constants mirrors history", () => {
  it("PHASE_COUNT matches the number of build phases", () => {
    expect(PHASE_COUNT).toBe(BUILD_PHASES.length);
  });

  it("CURRENT_FOCUS matches the roadmap item marked next", () => {
    const next = ROADMAP.find(p => p.status === "next");
    expect(CURRENT_FOCUS).toBe(next ? next.title : null);
  });

  it("marks exactly one roadmap item as next", () => {
    expect(ROADMAP.filter(p => p.status === "next")).toHaveLength(1);
  });
});

// The whole point of the split: if an eagerly-loaded module imports the release
// record again, the first-paint chunk silently regains ~1,200 lines of prose.
describe("history.js stays out of the eager path", () => {
  const EAGER = ["../tabs/HomeTab.jsx", "../tabs/ChatTab.jsx", "../App.jsx"];

  it.each(EAGER)("%s does not import config/history", async (path) => {
    const fs = await import("node:fs");
    const url = new URL(path, import.meta.url);
    expect(fs.readFileSync(url, "utf8")).not.toMatch(/from ["']@\/config\/history["']/);
  });
});
