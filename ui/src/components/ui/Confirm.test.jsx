// Confirm.test.jsx — the dialog's behaviour, which a build cannot prove.
//
// This file exists because the PR that added <Confirm> could only say "it
// compiles and the attributes are in the bundle". The interesting parts — does
// the promise resolve with the right answer, does focus come back, does Tab stay
// inside — are all runtime, and every one of them is the kind of thing that
// silently rots. So they get exercised.
import { useState } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmProvider, useConfirm } from "./Confirm";

/** A caller. Records what the promise resolved to, exactly as a real tab would:
 *  `if (!(await confirm(...))) return;` */
function Harness({ opts = "Delete this?" }) {
  const confirm = useConfirm();
  const [result, setResult] = useState("pending");
  return (
    <>
      <button onClick={async () => setResult(String(await confirm(opts)))}>open</button>
      <span data-testid="result">{result}</span>
    </>
  );
}

const mount = (opts) =>
  render(<ConfirmProvider><Harness opts={opts} /></ConfirmProvider>);

const openIt = async (user) => {
  await user.click(screen.getByRole("button", { name: "open" }));
  return screen.getByRole("dialog");
};

describe("useConfirm", () => {
  it("resolves true when confirmed", async () => {
    const user = userEvent.setup();
    mount();
    await openIt(user);
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("true"));
  });

  it("resolves false when cancelled", async () => {
    const user = userEvent.setup();
    mount();
    await openIt(user);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
  });

  // The promise MUST settle on Escape. If it only closed the dialog, the caller
  // would await forever and the delete path would hang with no UI to show for it.
  it("resolves false on Escape, and closes", async () => {
    const user = userEvent.setup();
    mount();
    await openIt(user);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes when the scrim is clicked, but not the dialog itself", async () => {
    const user = userEvent.setup();
    mount();
    const dialog = await openIt(user);

    // Clicking inside must NOT dismiss — otherwise selecting the title kills it.
    await user.click(screen.getByText("Delete this?"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.click(dialog.parentElement);
    await waitFor(() => expect(screen.getByTestId("result")).toHaveTextContent("false"));
  });

  it("throws a useful error when used without a provider", () => {
    const quiet = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Harness />)).toThrow(/ConfirmProvider/);
    quiet.mockRestore();
  });

  it("renders a string shorthand as the title", async () => {
    const user = userEvent.setup();
    mount("Clear all messages?");
    await openIt(user);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Clear all messages?")).toBeInTheDocument();
  });

  it("uses the given labels and marks the destructive action", async () => {
    const user = userEvent.setup();
    mount({ title: "Delete this goal?", confirmLabel: "Delete", danger: true });
    await openIt(user);
    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass("btn-danger");
  });
});

describe("Confirm focus handling", () => {
  // The safe choice is the one you can confirm by reflex. A focused "Delete" is
  // a trap for anyone who hits Enter to dismiss a surprise.
  it("focuses Cancel, not the destructive action", async () => {
    const user = userEvent.setup();
    mount({ title: "Delete this goal?", confirmLabel: "Delete", danger: true });
    await openIt(user);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus());
  });

  it("hands focus back to where it came from", async () => {
    const user = userEvent.setup();
    mount();
    const trigger = screen.getByRole("button", { name: "open" });
    await openIt(user);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  // aria-modal tells a screen reader the page behind is inert; it does NOT stop
  // the browser tabbing into it. Without containment, focus lands on a control
  // we have just told their AT does not exist.
  it("contains Tab inside the dialog", async () => {
    const user = userEvent.setup();
    mount();
    await openIt(user);
    const cancel  = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Confirm" });

    await waitFor(() => expect(cancel).toHaveFocus());
    await user.tab();
    expect(confirm).toHaveFocus();
    await user.tab();                 // past the last one — must wrap, not escape
    expect(cancel).toHaveFocus();
    await user.tab({ shift: true });  // and back again
    expect(confirm).toHaveFocus();
  });
});
