// DiagnosticsTab.test.jsx — the section contract.
//
// Every section used to carry its own PageHeader, so the page retitled itself
// under the nav on each switch ("Diagnostics" → "Step Verifier" → "Risk
// Observatory"), and VerifierPanel returned its own <Page> nested inside the
// tab's. Both were invisible to the build and to every existing test. These
// pin the rule that replaced them: the TAB owns the chrome, a section renders
// content only.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DiagnosticsTab from "./DiagnosticsTab";
import { __resetPollCache } from "@/lib/usePoll";

// The section nav, by its group name. Scoped on purpose: the Events section
// renders its own filter with a "Risk" and a "Plan" too, so an unscoped
// getByRole("button", { name: "Risk" }) is ambiguous the moment Events is open.
const nav = () => screen.getByRole("group", { name: "Diagnostics section" });

beforeEach(() => {
  __resetPollCache();
  vi.stubGlobal("fetch", vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })));
});

afterEach(() => {
  vi.unstubAllGlobals();
  __resetPollCache();
});

const sections = ["Intelligence", "Coherence", "Risk", "Verifier", "Events", "Plan", "Policy", "Feedback"];

describe("DiagnosticsTab", () => {
  it("shows exactly one page title, and it says Diagnostics", async () => {
    render(<DiagnosticsTab />);
    const headings = await screen.findAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent("Diagnostics");
  });

  it("keeps one title across every section, changing only the subtitle", async () => {
    const user = userEvent.setup();
    render(<DiagnosticsTab />);

    for (const label of sections) {
      await user.click(within(nav()).getByRole("button", { name: label }));

      // The failure this guards: the page renaming itself to the section you
      // clicked, so the tab you are on and the title you read disagree.
      await waitFor(() => {
        const headings = screen.getAllByRole("heading", { level: 1 });
        expect(headings).toHaveLength(1);
        expect(headings[0]).toHaveTextContent("Diagnostics");
      });
    }
  });

  it("describes the active section in the subtitle", async () => {
    const user = userEvent.setup();
    render(<DiagnosticsTab />);

    expect(await screen.findByText(/Unified Cognitive Index/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Verifier" }));
    await waitFor(() =>
      expect(screen.getByText(/pass, retry, replan, or abort/)).toBeInTheDocument());
    expect(screen.queryByText(/Unified Cognitive Index/)).not.toBeInTheDocument();
  });

  it("opens on the section a deep link asked for", async () => {
    render(<DiagnosticsTab initialSection="policy" />);
    expect(await screen.findByText(/Escalation thresholds/)).toBeInTheDocument();
  });

  it("falls back to Intelligence for an unknown section id", async () => {
    render(<DiagnosticsTab initialSection="not-a-section" />);
    expect(await screen.findByText(/Unified Cognitive Index/)).toBeInTheDocument();
  });
});
