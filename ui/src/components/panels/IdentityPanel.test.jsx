// IdentityPanel.test.jsx — the identity contract, after rehoming from CogOS.
//
// The contract's whole point is the SPLIT: intrinsic state is yours and moves
// only when you move it; learned state is earned. A panel that blurs the two
// misrepresents what the system claims about itself, so the split is what gets
// pinned here.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import IdentityPanel from "./IdentityPanel";
import { __resetPollCache } from "@/lib/usePoll";

const IDENTITY = {
  intrinsic: {
    profile: {},
    goals: { count: 0 },
    permissions: { active_keys: 3 },
  },
  learned: {
    decision_weights: { python_dev: 0.9411, terse: 0.7656 },
    memory: { total: 106 },
  },
};
const FINGERPRINT = { fingerprint: "23847d6b8d75bd6705cb26b149066338", schema_version: 1 };

function stub(identity = IDENTITY, fp = FINGERPRINT) {
  vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve(String(url).includes("fingerprint") ? fp : identity),
  })));
}

beforeEach(() => { __resetPollCache(); stub(); });
afterEach(() => { vi.unstubAllGlobals(); __resetPollCache(); });

describe("IdentityPanel", () => {
  it("separates what you declared from what the system earned", async () => {
    render(<IdentityPanel />);
    await waitFor(() => expect(screen.getByText(/Intrinsic — yours/)).toBeInTheDocument());
    expect(screen.getByText(/Learned — earned per agent/)).toBeInTheDocument();
  });

  it("shows intrinsic state as declared, including 'not set'", async () => {
    render(<IdentityPanel />);
    // An empty profile is a fact about the contract, not a missing value to hide.
    await waitFor(() => expect(screen.getByText("not set")).toBeInTheDocument());
    expect(screen.getByText("3")).toBeInTheDocument();       // active keys
  });

  it("renders a learned weight per agent", async () => {
    render(<IdentityPanel />);
    await waitFor(() => expect(screen.getByText("python dev")).toBeInTheDocument());
    expect(screen.getByText("terse")).toBeInTheDocument();
  });

  it("truncates the fingerprint but keeps the whole hash reachable", async () => {
    render(<IdentityPanel />);
    // It identifies durable state, so the full value has to be recoverable —
    // truncation is for the layout, not for the reader.
    await waitFor(() => expect(screen.getByText(/23847d6b8d75…/)).toBeInTheDocument());
    expect(screen.getByTitle(FINGERPRINT.fingerprint)).toBeInTheDocument();
  });

  it("says so when nothing has been learned yet", async () => {
    stub({ intrinsic: IDENTITY.intrinsic, learned: { decision_weights: {} } });
    render(<IdentityPanel />);
    await waitFor(() => expect(screen.getByText(/No learned weights yet/)).toBeInTheDocument());
  });

  it("renders nothing at all when identity is unavailable", () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
    const { container } = render(<IdentityPanel />);
    // About must not grow an empty "Identity" shell when the endpoint is down.
    expect(container).toBeEmptyDOMElement();
  });
});
