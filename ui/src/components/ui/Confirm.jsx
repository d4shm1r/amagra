// Confirm.jsx — the app's own "are you sure?".
//
// Deleting used to go through window.confirm(): a native OS dialog. Every other
// pixel here is warm cream, gold and DM Sans — and then, at the one moment a
// user is asked to be certain about destroying something, they got grey system
// chrome in a system font, with buttons the design system has never seen and
// copy it cannot set. The material broke at exactly the moment trust mattered
// most, which is the worst possible place to put the seam.
//
// It is also the app's only dialog, so it owns the pattern: one scrim, one card,
// Escape to cancel, focus moved in and handed back.
//
// PROMISE-BASED ON PURPOSE. window.confirm() is synchronous, so call sites read
// `if (!confirm("…")) return;`. A React dialog is state, which normally drags
// every call site into a rewrite — a hook, a piece of state, a JSX branch, and
// the delete logic torn in half around a callback. Returning a promise keeps the
// original shape and the original reading order:
//
//     const confirm = useConfirm();
//     ...
//     if (!(await confirm({ title: "Delete this goal?", danger: true }))) return;
//     await fetch(…);
//
// The dialog is rendered once, by the provider at the app root, instead of once
// per caller.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { T, LUX, TYPE, SPACE, DUR, EASE, FONT_DISPLAY, Z } from "@/styles/theme";
import { Button } from "./Button";
import { Row, Spacer } from "./Layout";

const ConfirmCtx = createContext(null);

/** Ask the user to confirm. Returns a Promise<boolean>.
 *
 *  Pass a string for the simple case, or { title, body, confirmLabel,
 *  cancelLabel, danger } when the action deserves a sentence of explanation. */
export function useConfirm() {
  const confirm = useContext(ConfirmCtx);
  if (!confirm) throw new Error("useConfirm() needs a <ConfirmProvider> above it");
  return confirm;
}

export function ConfirmProvider({ children }) {
  const [req, setReq] = useState(null);

  // The pending promise's resolve lives in a ref, not in state: settling is a
  // side effect, and a state updater must stay pure (StrictMode double-invokes
  // it, which would resolve twice).
  const resolveRef = useRef(null);
  const dialogRef  = useRef(null);
  const restoreRef = useRef(null);

  const confirm = useCallback((opts) => new Promise((resolve) => {
    resolveRef.current = resolve;
    setReq(typeof opts === "string" ? { title: opts } : opts);
  }), []);

  const settle = useCallback((ok) => {
    const resolve = resolveRef.current;
    resolveRef.current = null;
    setReq(null);
    resolve?.(ok);
  }, []);

  useEffect(() => {
    if (!req) return;

    // Remember where focus came from, move it into the dialog, hand it back on
    // close. Without the hand-back, dismissing the dialog drops a keyboard user
    // at the top of the document, having lost the row they were working on.
    restoreRef.current = document.activeElement;

    // The first button in the dialog is Cancel, and that is the one that gets
    // focus: the safe choice should be the one you can confirm by reflex. A
    // focused "Delete" is a trap for anyone who hits Enter to dismiss a surprise.
    // (Queried rather than passed by ref because Button is not a forwardRef —
    // adding that is a wider change than this dialog should make.)
    dialogRef.current?.querySelector("button")?.focus();

    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); settle(false); return; }

      // Contain Tab. `aria-modal` tells a screen reader the rest of the page is
      // inert, but it does not stop the browser tabbing into it — so without
      // this, the third Tab lands on a button behind the scrim that the user
      // cannot see and we have told their AT does not exist. The dialog's only
      // focusables are its two buttons, so containment is a wrap between them.
      if (e.key === "Tab") {
        const f = dialogRef.current?.querySelectorAll("button");
        if (!f?.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    // Capture: the app's global shortcut handler is also on window, and Escape
    // must mean "close this", never reach a tab behind the scrim.
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      restoreRef.current?.focus?.();
    };
  }, [req, settle]);

  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      {req && (
        <div
          // Clicking the scrim cancels — mousedown, not click, so a drag that
          // STARTED inside the dialog and released on the scrim doesn't dismiss
          // the thing you were interacting with (selecting the title, say).
          onMouseDown={(e) => { if (e.target === e.currentTarget) settle(false); }}
          style={{
            position: "fixed", inset: 0, zIndex: Z.modal,
            background: LUX.scrim,
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: SPACE[4],
            animation: `fadeIn ${DUR.fast} ${EASE.out}`,
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            className="lux-card"
            style={{
              width: "100%", maxWidth: 400,
              padding: `${SPACE[5]}px ${SPACE[6]}px`,
              animation: `modalIn ${DUR.base} ${EASE.out}`,
            }}
          >
            <div id="confirm-title" style={{ ...TYPE.subtitle, fontFamily: FONT_DISPLAY, color: T.text }}>
              {req.title}
            </div>
            {req.body && (
              <div style={{ ...TYPE.small, color: T.muted, marginTop: SPACE[2], lineHeight: 1.55 }}>
                {req.body}
              </div>
            )}
            <div style={{ marginTop: SPACE[5] }}>
              <Row gap="sm">
                <Spacer />
                <Button variant="quiet" onClick={() => settle(false)}>
                  {req.cancelLabel || "Cancel"}
                </Button>
                <Button variant={req.danger ? "danger" : "gold"} onClick={() => settle(true)}>
                  {req.confirmLabel || "Confirm"}
                </Button>
              </Row>
            </div>
          </div>
        </div>
      )}
    </ConfirmCtx.Provider>
  );
}
