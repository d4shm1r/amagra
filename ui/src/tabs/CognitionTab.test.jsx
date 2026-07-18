// CognitionTab.test.jsx — the dashboard's one promise.
//
// A glance surface is only useful if the tile that looks wrong is also the way
// in to why. These pin that wiring (every tile routes to the section that
// explains its number) and the summary behaviours that are easy to regress
// back into "a grid of shrunken pages".
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CognitionTab from "./CognitionTab";
import { __resetPollCache } from "@/lib/usePoll";

// Enough of each payload for the tiles to render real numbers.
const FIXTURES = {
  "/cos/uci/hierarchical": {
    h_uci: 91.6,
    layers: { reliability: { score: 99.8 }, intelligence: { score: 88.8 },
              adaptation: { score: 81.2 }, productivity: { score: 98.2 } },
  },
  "/cos/uci/trajectory": { history: [{ uci: 90 }, { uci: 91 }, { uci: 91.6 }],
                           curvature: { n: 4, peak_abs_curvature: 0.4, bending: false } },
  "/health": { ollama: "online", memory: { backend: "FAISSBackend", total: 106 } },
  "/coherence/dynamics": [{ C: 0.97, window_idx: 0 }, { C: 0.973, window_idx: 1 }],
  "/coherence": { C: 0.973, conflict_rate: 0, G_r_mean: 0 },
  "/risk/history": [{ total_risk: 0.2, reflect_level: "none" }, { total_risk: 0.19, reflect_level: "light" }],
  "/risk/stats": { n: 160, mean_risk: 0.19, by_level: { none: 0.94, light: 0.06 } },
  "/verify/stats": { n: 200, pass_rate: 1.0 },
  "/plan/graph": { nodes: [] },
  "/policy/health": { total: 200, acceptance_rate: 0.99, marginal_value: 0.0035, mean_uplift: 0.35 },
  "/runs/cost": { runs: 12, total_cost_usd: 0, escalated_runs: 0, escalation_rate: 0 },
  "/feedback": [{ rating: 1, agent: "terse" }, { rating: 1, agent: "terse" }, { rating: -1, agent: "terse" }],
  "/cos/events": { events: [
    { event_type: "uci.computed", payload: {} }, { event_type: "risk.scored", payload: {} },
  ], counts: { "uci.computed": 40 } },
};

// Longest prefix wins, so "/coherence/dynamics" is not shadowed by "/coherence".
function payloadFor(url) {
  const key = Object.keys(FIXTURES)
    .filter(k => url.includes(k))
    .sort((a, b) => b.length - a.length)[0];
  return key ? FIXTURES[key] : {};
}

let onOpen;

beforeEach(() => {
  __resetPollCache();
  onOpen = vi.fn();
  vi.stubGlobal("fetch", vi.fn((url) =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(payloadFor(String(url))) })));
});

afterEach(() => { vi.unstubAllGlobals(); __resetPollCache(); });

const mount = () => render(<CognitionTab onOpenSection={onOpen} />);
const tile = (name) => screen.getByRole("button", { name: new RegExp(`^${name}`, "i") });

describe("Cognition dashboard", () => {
  it("leads with one health number, not two competing ones", async () => {
    mount();
    // h_UCI is THE headline; C(t) appears as an input beside it, never as a
    // rival hero on its own scale.
    await waitFor(() => expect(screen.getAllByText("91.6").length).toBeGreaterThan(0));
    expect(screen.getByText(/h_UCI/)).toBeInTheDocument();
    expect(screen.getByText(/C\(t\) coherence/)).toBeInTheDocument();
  });

  it("shows the four layers behind the composite", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Reliability")).toBeInTheDocument());
    ["Intelligence", "Adaptation", "Productivity"].forEach(l =>
      expect(screen.getAllByText(l).length).toBeGreaterThan(0));
    expect(screen.getByText("99.8")).toBeInTheDocument();
  });

  it("routes every tile to the section that explains its number", async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText("Verifier")).toBeInTheDocument());

    // The whole point of the redesign: a worrying tile is also the way in.
    const routes = [
      ["Intelligence", "uci"], ["Coherence", "coherence"], ["Risk", "risk"],
      ["Verifier", "verifier"], ["Plan", "plan"], ["Policy", "policy"],
      ["Feedback", "feedback"],
    ];
    for (const [label, section] of routes) {
      onOpen.mockClear();
      await user.click(tile(label));
      expect(onOpen, `${label} tile`).toHaveBeenCalledWith(section);
    }
  });

  it("opens the event log from the activity preview", async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText(/Open event log/)).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /Open event log/ }));
    expect(onOpen).toHaveBeenCalledWith("events");
  });

  it("previews only the newest events — the full log lives in Diagnostics", async () => {
    const many = { events: Array.from({ length: 40 }, (_, i) => ({ event_type: `e.${i}`, payload: {} })), counts: {} };
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve(String(url).includes("/cos/events") ? many : payloadFor(String(url))),
    })));
    mount();
    // A preview, not a second copy of the feed: no filters, no search, capped
    // at 8. (EventRow renders "e.0" as "e 0" — dots read as separators.)
    await waitFor(() => expect(screen.getByText("e 0")).toBeInTheDocument());
    expect(screen.getByText("e 7")).toBeInTheDocument();
    expect(screen.queryByText("e 8")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Search events/)).not.toBeInTheDocument();
  });

  it("reads a tile by keyboard, not just by mouse", async () => {
    const user = userEvent.setup();
    mount();
    await waitFor(() => expect(screen.getByText("Verifier")).toBeInTheDocument());
    tile("Verifier").focus();
    await user.keyboard("{Enter}");
    expect(onOpen).toHaveBeenCalledWith("verifier");
  });

  it("names each tile for a screen reader, value included", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Verifier")).toBeInTheDocument());
    // "Verifier: 100% — open details" beats "button" with the number in a
    // separate unlabelled div.
    expect(tile("Verifier")).toHaveAccessibleName(/Verifier: 100% — open details/);
  });

  it("says Idle rather than 0/0 when no plan is running", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("Idle")).toBeInTheDocument());
    expect(screen.getByText(/no execution plan active/)).toBeInTheDocument();
  });

  it("colours the policy tile by the number it is actually showing", async () => {
    mount();
    // 99% acceptance used to render RED, because the tone came from
    // marginal_value while the figure came from acceptance_rate — a tile
    // arguing with itself, with nothing on screen to explain it.
    await waitFor(() => expect(screen.getByText("99%")).toBeInTheDocument());
    expect(screen.getByText(/accepts nearly everything/)).toBeInTheDocument();
  });

  it("reports a fully local posture honestly", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("$0.0000")).toBeInTheDocument());
    expect(screen.getByText(/fully local — no cloud spend/)).toBeInTheDocument();
  });
});
