// a11y.test.jsx — the accessibility contracts of the kit.
//
// These are the rules most likely to be "cleaned up" by someone who cannot see
// why they are there: an empty <Toast> layer looks like dead markup, an
// aria-hidden dot looks like an oversight, a minWidth on an icon button looks
// arbitrary. Each of those is load-bearing, and each reason is a sentence long,
// so the reasons live here next to the assertion that enforces them.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Toast, Loading, Notice } from "./Feedback";
import { Dot } from "./Pill";
import { IconButton } from "./Button";

describe("Toast — the app's live region", () => {
  // THE structural rule. A screen reader only reliably announces content
  // inserted into a region that was ALREADY in the document, so the layer must
  // outlive its message. Mounting it conditionally — `{offline && <Toast>…}` —
  // is the classic way to ship an alert that is silent for exactly the people
  // who need it read aloud. If someone deletes the empty layer as dead markup,
  // this fails.
  it("renders its region even with nothing in it", () => {
    render(<Toast>{false}</Toast>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("is a polite live region", () => {
    render(<Toast>hi</Toast>);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });
});

describe("Loading / Notice", () => {
  it("Loading announces the wait", () => {
    render(<Loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading…");
  });

  // Urgency matches tone: a failure interrupts, anything else waits its turn.
  // Backwards, and either a dead upload passes silently or every routine
  // success barges into what the user was doing.
  it("Notice is an alert when it carries a failure", () => {
    render(<Notice tone="error">upload died</Notice>);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("Notice is merely a status otherwise", () => {
    render(<Notice tone="success">saved</Notice>);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("Dot — never colour alone", () => {
  // A bare dot says everything in hue: the one channel a colour-blind user does
  // not have and a screen reader cannot see. Unlabelled it must be decoration
  // (text beside it does the work); labelled it must have a name.
  it("is invisible to assistive tech when text beside it carries the meaning", () => {
    const { container } = render(<Dot tone="success" />);
    const dot = container.querySelector("span");
    expect(dot).toHaveAttribute("aria-hidden");
    expect(dot).not.toHaveAttribute("role", "img");
  });

  it("names itself when it stands alone", () => {
    render(<Dot tone="success" label="Engine online" />);
    expect(screen.getByRole("img", { name: "Engine online" })).toBeInTheDocument();
  });
});

describe("IconButton — the hit-target floor", () => {
  // WCAG 2.2 SC 2.5.8 is 24×24. jsdom does no layout, so the box cannot be
  // measured here — asserting the declaration is the most this environment can
  // honestly do. It still catches the regression that matters (someone dropping
  // the floor); it would not catch a parent that squashes the button.
  it("declares at least 24×24", () => {
    render(<IconButton title="Close">✕</IconButton>);
    const btn = screen.getByRole("button", { name: "Close" });
    expect(btn).toHaveStyle({ minWidth: "24px", minHeight: "24px" });
  });

  it("is named for assistive tech even though its label is a glyph", () => {
    render(<IconButton title="Refresh">↻</IconButton>);
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
