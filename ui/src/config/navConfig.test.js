// navConfig.test.js — the menu's structural invariants.
//
// Written when CogOS was dissolved: a removed tab leaves several places it can
// still be referenced from (the surface list, the alias table, the launcher,
// the tab registry), and a stale reference there fails at NAVIGATION time, in
// front of the user, not at build time.
import { describe, it, expect } from "vitest";
import {
  SURFACES, NAV, TABS_BY_SURFACE, SURFACE_BY_TAB, DEFAULT_TAB,
  TAB_ALIASES, VALID_TABS, surfaceOf, firstVisibleTab,
} from "./navConfig";

const allTabs = SURFACES.flatMap(s => s.tabs);

describe("navConfig", () => {
  it("resolves every alias to a tab that exists", () => {
    // The failure this catches: retiring a tab and leaving an alias pointing at
    // it, so an old shortcut or deep link silently falls back to Chat.
    for (const [from, to] of Object.entries(TAB_ALIASES)) {
      expect(VALID_TABS.has(to), `alias ${from} → ${to}`).toBe(true);
    }
  });

  it("sends the retired CogOS ids to Diagnostics", () => {
    // Its coherence view, Δ²C indicator and health prediction became the
    // Coherence section, so that is where its links must land.
    expect(TAB_ALIASES.cognitive).toBe("diagnostics");
    expect(VALID_TABS.has("cognitive")).toBe(false);
    expect(surfaceOf("diagnostics")).toBe("cognition");
  });

  it("no longer lists CogOS as a destination", () => {
    expect(allTabs.find(t => t.id === "cognitive")).toBeUndefined();
    expect(allTabs.find(t => t.label === "CogOS")).toBeUndefined();
  });

  it("keeps tab ids unique across every surface", () => {
    const ids = allTabs.map(t => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("gives every surface a landing tab that exists", () => {
    for (const s of SURFACES) {
      expect(s.tabs.length).toBeGreaterThan(0);
      expect(VALID_TABS.has(DEFAULT_TAB[s.id])).toBe(true);
      expect(VALID_TABS.has(firstVisibleTab(s.id, "advanced"))).toBe(true);
    }
  });

  it("maps every tab back to the surface that owns it", () => {
    for (const s of SURFACES) {
      for (const t of s.tabs) expect(SURFACE_BY_TAB[t.id]).toBe(s.id);
    }
  });

  it("holds the menu's one voice rule — an icon name and a short noun phrase", () => {
    for (const item of [...NAV, ...allTabs]) {
      expect(typeof item.icon, `${item.id} icon`).toBe("string");
      // A character, not an icon name — the drift the drawn-icon pass removed.
      expect(item.icon.length, `${item.id} icon is a glyph`).toBeGreaterThan(1);
      expect(item.desc, `${item.id} desc`).toBeTruthy();
      expect(item.desc.length, `${item.id} desc too long`).toBeLessThanOrEqual(34);
      expect(item.desc, `${item.id} uses "&"`).not.toMatch(/&/);
      expect(item.desc[0], `${item.id} desc capitalised`).toBe(item.desc[0].toLowerCase());
    }
  });
});
